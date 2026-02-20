"""
Common base classes and utilities for Photo Research devices.
"""

from __future__ import annotations

import logging
import platform
import textwrap
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import serial
import serial.tools.list_ports

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "PRCommandError",
    "PRCommandResponse",
    "PRDeviceBase",
    "PRResponseCode",
]

_COMMAND_DELAY = 0.05
_CHAR_WRITE_DELAY = 0.01
_DEFAULT_SERIAL_TIMEOUT = 5.0
_REMOTE_MODE_TIMEOUT = 10.0
_PR_SERIAL_KWARGS: Mapping = MappingProxyType(
    {
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "rtscts": False,
        "timeout": _DEFAULT_SERIAL_TIMEOUT,
    }
)


class PRResponseCode(int, Enum):
    """
    Response codes for Photo Research SpectraScan devices.

    The device returns a 5-digit status string (e.g., "00000"). The first
    two digits represent the primary error code. Code 0 indicates success.
    """

    OK = 0
    INSUFFICIENT_LIGHT = 1
    SYNC_ERROR = 3
    OVER_RANGE = 5
    COMMAND_ERROR = 8

    @classmethod
    def _missing_(cls, value: object) -> PRResponseCode:
        """
        Return a dynamic enum member for unknown response codes.

        Parameters
        ----------
        value : object
            The unknown value that was not found in the enum.

        Returns
        -------
        PRResponseCode
            A new enum member with the unknown value.
        """
        obj = int.__new__(cls, value)  # type: ignore[arg-type]
        obj._name_ = f"UNKNOWN_{value}"
        obj._value_ = value
        return obj


@dataclass
class PRCommandResponse:
    """Response data from a Photo Research device command."""

    code: PRResponseCode
    raw_data: str


class PRCommandError(Exception):
    """Describes an error from a Photo Research device command."""

    def __init__(self, response: PRCommandResponse, *args: object) -> None:
        self.response = response
        super().__init__(
            f"PR command error: code={response.code}, data={response.raw_data!r}",
            *args,
        )


class PRDeviceBase(ABC):
    """
    Abstract base class for Photo Research devices.

    Provides common functionality shared between device types, including
    serial communication, remote mode handshake, and device properties.

    The PR-655 (and related models) require character-by-character serial
    writes with flush after each byte for reliable communication over USB.
    """

    def __init__(self, port: str) -> None:
        """
        Initialize base Photo Research device with serial port.

        Opens the serial connection and enters remote mode via the PHOTO
        handshake protocol.

        Parameters
        ----------
        port : str
            The serial port device path (e.g., '/dev/tty.usbmodem1101').

        Raises
        ------
        serial.SerialException
            If the serial port cannot be opened or configured.
        PRCommandError
            If the remote mode handshake fails.
        """
        self._last_cmd_time: float = 0
        self._port = serial.Serial(port, **_PR_SERIAL_KWARGS)
        self._enter_remote_mode()

    def _write_serial(self, message: str) -> None:
        """
        Write a message to the serial port character-by-character with flush.

        The PR-655 USB CDC interface requires individual character writes
        with a flush after each byte for reliable communication.

        Parameters
        ----------
        message : str
            The message to send (should include terminator).
        """
        for ch in message:
            self._port.write(ch.encode("utf-8"))
            self._port.flush()
            time.sleep(_CHAR_WRITE_DELAY)

    def _enter_remote_mode(self) -> None:
        """
        Enter remote control mode via PHOTO handshake.

        Sends the "PHOTO" command character-by-character. The device
        responds with "REMOTE MODE" on success.

        Raises
        ------
        PRCommandError
            If the device does not respond to the handshake.
        """
        log = logging.getLogger("specio.PR")
        log.debug("Entering remote mode")

        self._port.reset_input_buffer()
        self._write_serial("PHOTO\r")
        response = self._read_response(timeout=_REMOTE_MODE_TIMEOUT)

        if "REMOTE MODE" not in response:
            raise PRCommandError(
                PRCommandResponse(
                    code=PRResponseCode.COMMAND_ERROR,
                    raw_data=response,
                ),
                f"Unexpected handshake response: {response!r}",
            )

        log.debug("Remote mode entered successfully")

    def _exit_remote_mode(self) -> None:
        """
        Exit remote control mode by sending the quit command.

        Sends "Q" to return the device to local control.
        """
        log = logging.getLogger("specio.PR")
        log.debug("Exiting remote mode")
        self._write_serial("Q\r")

    def _read_response(self, timeout: float | None = None) -> str:
        """
        Read a response line from the device with configurable timeout.

        Parameters
        ----------
        timeout : float | None, optional
            Read timeout in seconds. If None, uses the current port timeout.

        Returns
        -------
        str
            The decoded response string with whitespace stripped.
        """
        if timeout is not None:
            original_timeout = self._port.timeout
            self._port.apply_settings({"timeout": timeout})

        response = self._port.readline()

        if timeout is not None:
            self._port.apply_settings({"timeout": original_timeout})

        return response.decode("ascii", errors="replace").strip()

    def _write_cmd(self, command: str) -> PRCommandResponse:
        """
        Send a command to the device and parse the response.

        Enforces a minimum inter-command delay, sends the command
        character-by-character, and parses the 5-digit response code.

        Parameters
        ----------
        command : str
            The command string to send (without terminator).

        Returns
        -------
        PRCommandResponse
            Parsed response containing status code and data payload.

        Raises
        ------
        PRCommandError
            If the device returns a non-OK response code.
        """
        log = logging.getLogger("specio.PR")
        log.debug("Sending CMD: %s", command)

        if self._last_cmd_time + _COMMAND_DELAY > time.time():
            time.sleep(
                max(
                    self._last_cmd_time + _COMMAND_DELAY + 0.001 - time.time(),
                    0,
                )
            )

        self._port.reset_input_buffer()
        self._write_serial(command + "\r")
        self._last_cmd_time = time.time()

        raw_response = self._read_response()

        response = self._parse_response(raw_response)

        if response.code != PRResponseCode.OK:
            raise PRCommandError(response)

        return response

    def _parse_response(self, raw: str) -> PRCommandResponse:
        """
        Parse a raw response string into a structured command response.

        The PR-655 response format is a 5-digit status code followed by
        a comma and the data payload (e.g., "00000,PR-655"). The first
        two digits of the status code are the primary error code.

        Parameters
        ----------
        raw : str
            Raw response string from the device.

        Returns
        -------
        PRCommandResponse
            Structured response with parsed status code and data.
        """
        stripped = raw.strip()
        if len(stripped) >= 5 and stripped[:5].isdigit():
            code = PRResponseCode(int(stripped[:2]))
            data = stripped[5:].lstrip(",").strip()
            return PRCommandResponse(code=code, raw_data=data)

        return PRCommandResponse(code=PRResponseCode.OK, raw_data=stripped)

    @classmethod
    def discover(cls) -> Self:
        """
        Attempt automatic discovery of a Photo Research device serial port.

        Scans platform-appropriate serial ports and attempts the PHOTO
        handshake on each candidate.

        Returns
        -------
        Self
            A successfully discovered Photo Research device object.

        Raises
        ------
        serial.SerialException
            If no Photo Research device can be found.
        """
        if platform.system() == "Darwin":
            port_list = list(serial.tools.list_ports.grep("usbserial")) + list(
                serial.tools.list_ports.grep("usbmodem")
            )
        elif platform.system() == "Windows":
            port_list = list(serial.tools.list_ports.grep("Photo Research"))
        elif platform.system() == "Linux":
            port_list = list(serial.tools.list_ports.grep("ttyUSB"))
        else:
            port_list = list(serial.tools.list_ports.comports())

        if len(port_list) == 0:
            raise serial.SerialException(
                "No serial ports found for Photo Research device"
            )

        for p in port_list:
            try:
                device = cls(p.device)
                return device
            except Exception:
                continue

        raise serial.SerialException(
            textwrap.dedent(
                """Could not connect to any Photo Research device.
                Check connection and device power."""
            )
        )

    @property
    def serial_number(self) -> str:
        """
        The hardware serial number, queried via D110 command.

        Returns
        -------
        str
            The device serial number.
        """
        if not hasattr(self, "_serial_number") or self._serial_number is None:
            response = self._write_cmd("D110")
            self._serial_number: str | None = response.raw_data
        return self._serial_number or "unknown"

    @property
    def manufacturer(self) -> str:
        """
        The device manufacturer name.

        Returns
        -------
        str
            Always returns "Photo Research".
        """
        return "Photo Research"

    @cached_property
    def model(self) -> str:
        """
        The model name, queried via D111 command.

        Returns
        -------
        str
            The device model name (e.g., "PR-655").
        """
        response = self._write_cmd("D111")
        return response.raw_data

    @abstractmethod
    def _raw_measure(self) -> Any:
        """
        Perform a raw measurement and return device-specific measurement data.

        This method must be implemented by concrete device classes.
        """
        ...
