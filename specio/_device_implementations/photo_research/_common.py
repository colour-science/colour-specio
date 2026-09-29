"""
Common base classes and utilities for Photo Research devices.
"""

from __future__ import annotations

import logging
import platform
import re
import textwrap
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import serial
import serial.tools.list_ports

from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from serial.tools.list_ports_common import ListPortInfo

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

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
_CODE_PATTERN = re.compile(r"[+-]?\d+")
_REMOTE_MODE_COMMAND = "PHOTO"
_REMOTE_MODE_REPLY = b"REMOTE MODE"
_QUIT_COMMAND = "Q"
_COMMAND_TERMINATOR = "\r"
_PHOTO_RESEARCH_NAMES = ("photo research", "photoresearch")
# USB vendor IDs of other instrument makers, from the linux-usb.org usb.ids
# list. Discovery never opens these ports.
_OTHER_VENDOR_VIDS: Mapping[int, str] = MappingProxyType({0x132B: "Konica Minolta"})
# Device-name fragments of USB serial ports on each platform. The PR-655's
# USB CDC interface appears as usbmodem on macOS and ttyACM on Linux; the
# others cover USB-to-serial adapters. Windows ports are COM<n>, so there a
# port must name Photo Research. An unlisted platform tries every port.
_PORT_NAME_PATTERNS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "Darwin": ("usbmodem", "usbserial"),
        "Linux": ("ttyACM", "ttyUSB"),
        "Windows": (),
    }
)
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
    Error codes returned by Photo Research PR-655 and PR-670 devices.

    Every reply starts with a signed code, ``00000`` on success. Any other
    value is an error. The values and meanings follow the "Remote Control
    Error Codes" tables of the PR-655/670 User Manual. The manual marks none
    of them as warnings. A code outside the tables becomes an ``UNKNOWN_<n>``
    member that keeps its value.
    """

    OK = 0

    # Measurement errors
    LIGHT_SOURCE_NOT_CONSTANT = -1
    LIGHT_OVERLOAD = -2
    CANNOT_SYNC = -3
    ADAPTIVE_MODE_ERROR = -4
    WEAK_LIGHT = -8
    SYNC_ERROR = -9
    CANNOT_AUTO_SYNC = -10
    ADAPTIVE_MODE_TIMEOUT = -12

    # Parsing errors
    ILLEGAL_COMMAND = -1000
    TOO_MANY_FIELDS = -1001
    INVALID_PRIMARY_ACCESSORY = -1002
    INVALID_ADDON_1_ACCESSORY = -1003
    INVALID_ADDON_2_ACCESSORY = -1004
    NOT_A_PRIMARY_ACCESSORY = -1005
    NOT_AN_ADDON_ACCESSORY = -1006
    ACCESSORY_ALREADY_SELECTED = -1007
    INVALID_APERTURE_INDEX = -1008
    INVALID_UNITS_CODE = -1009
    INVALID_EXPOSURE_VALUE = -1010
    INVALID_GAIN_CODE = -1011
    INVALID_AVERAGE_CYCLES = -1012
    INVALID_CIE_OBSERVER = -1015
    INVALID_DARK_MODE = -1017
    INVALID_SYNC_MODE = -1019
    TITLE_TOO_LONG = -1021
    TITLE_EMPTY = -1022
    INVALID_USER_SYNC_PERIOD = -1023
    INVALID_RECALL_COMMAND = -1024
    INVALID_ADDON_3_ACCESSORY = -1025
    INVALID_SENSITIVITY_MODE = -1026
    PARAMETER_NOT_APPLICABLE = -1035
    INVALID_DATA_REQUEST = -2000

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


class PRCommandError(DeviceError):
    """Describes an error code returned by a Photo Research device command."""

    def __init__(self, response: PRCommandResponse, *args: object) -> None:
        """
        Initialize the error from the parsed device response.

        Parameters
        ----------
        response : PRCommandResponse
            The response that carried the error code.
        *args : object
            Additional context passed to ``Exception``.
        """
        self.response = response
        super().__init__(
            f"PR command error: {response.code.name} ({response.code.value}), "
            f"data={response.raw_data!r}",
            *args,
        )


def _names_photo_research(text: str | None) -> bool:
    """
    Report whether a USB metadata string names Photo Research.

    Parameters
    ----------
    text : str | None
        A manufacturer, product or description string.

    Returns
    -------
    bool
        True if the string contains a Photo Research name.
    """
    normalized = (text or "").lower()
    return any(name in normalized for name in _PHOTO_RESEARCH_NAMES)


def _is_candidate_port(port: ListPortInfo, system: str) -> bool:
    """
    Decide from USB metadata alone whether discovery may open a port.

    A port that names Photo Research is a candidate. A port whose VID
    belongs to another instrument vendor, or whose manufacturer string names
    anyone else, is not. Any other port is a candidate when its device name
    matches the platform's USB serial naming.

    Parameters
    ----------
    port : ListPortInfo
        A port from ``serial.tools.list_ports.comports()``.
    system : str
        The result of ``platform.system()``.

    Returns
    -------
    bool
        True if discovery may open the port and send the handshake.
    """
    if any(
        _names_photo_research(text)
        for text in (port.manufacturer, port.product, port.description)
    ):
        return True
    if port.vid in _OTHER_VENDOR_VIDS or port.manufacturer:
        return False
    patterns = _PORT_NAME_PATTERNS.get(system)
    if patterns is None:
        return True
    return any(pattern in port.device for pattern in patterns)


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
        DeviceError
            If the remote mode handshake fails. The port is closed first.
        """
        self._last_cmd_time: float = 0
        self._port = serial.Serial(port, **_PR_SERIAL_KWARGS)
        try:
            self._enter_remote_mode()
        except BaseException:
            self._port.close()
            raise

    def __enter__(self) -> Self:
        """
        Return the device for use in a ``with`` block.

        Returns
        -------
        Self
            This device, already in remote mode.
        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """
        Exit remote mode and close the port when the ``with`` block ends.

        Parameters
        ----------
        *exc_info : object
            The exception type, value and traceback, if any.
        """
        self.close()

    def close(self) -> None:
        """
        Exit remote mode and close the serial port.

        Returns the instrument to local (front panel) control. Calling
        ``close`` on a closed device does nothing.
        """
        if not self._port.is_open:
            return
        try:
            self._exit_remote_mode()
        finally:
            self._port.close()

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

        Sends the five characters ``PHOTO`` one at a time with no
        terminator. The device responds with ``REMOTE MODE`` on success.

        Raises
        ------
        DeviceError
            If the device does not respond to the handshake.
        """
        log = logging.getLogger("specio.PR")
        log.debug("Entering remote mode")

        self._port.reset_input_buffer()
        self._write_serial(_REMOTE_MODE_COMMAND)
        with self._port_timeout(_REMOTE_MODE_TIMEOUT):
            reply = self._port.read_until(_REMOTE_MODE_REPLY)

        if _REMOTE_MODE_REPLY not in reply:
            raise DeviceError(f"Unexpected handshake response: {reply!r}")

        log.debug("Remote mode entered successfully")

    def _exit_remote_mode(self) -> None:
        """
        Exit remote control mode by sending the quit command.

        Sends ``Q`` with no terminator to return the device to local
        control. The device sends no reply.
        """
        log = logging.getLogger("specio.PR")
        log.debug("Exiting remote mode")
        self._write_serial(_QUIT_COMMAND)

    @contextmanager
    def _port_timeout(self, timeout: float | None) -> Iterator[None]:
        """
        Apply a temporary serial timeout and restore the previous one on exit.

        Parameters
        ----------
        timeout : float | None
            Timeout in seconds for the duration of the block. If None, the
            current timeout stays in force.

        Yields
        ------
        None
            Control returns to the block with the timeout applied.
        """
        if timeout is None:
            yield
            return

        original_timeout = self._port.timeout
        self._port.timeout = timeout
        try:
            yield
        finally:
            self._port.timeout = original_timeout

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
        with self._port_timeout(timeout):
            response = self._port.readline()

        return response.decode("ascii", errors="replace").strip()

    def _write_cmd(
        self, command: str, timeout: float | None = None
    ) -> PRCommandResponse:
        """
        Send a command to the device and parse the response.

        Enforces a minimum inter-command delay, sends the command
        character-by-character with a CR terminator, and parses the signed
        response code.

        Parameters
        ----------
        command : str
            The command string to send (without terminator).
        timeout : float | None, optional
            Timeout in seconds for the response. If None, uses the current
            port timeout.

        Returns
        -------
        PRCommandResponse
            Parsed response containing status code and data payload.

        Raises
        ------
        PRCommandError
            If the device returns a non-OK response code.
        DeviceError
            If the response is missing or has no numeric code.
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
        self._write_serial(command + _COMMAND_TERMINATOR)
        self._last_cmd_time = time.time()

        raw_response = self._read_response(timeout=timeout)

        response = self._parse_response(raw_response)

        if response.code != PRResponseCode.OK:
            raise PRCommandError(response)

        return response

    def _parse_response(self, raw: str) -> PRCommandResponse:
        """
        Parse a raw response string into a structured command response.

        A response is a signed error code, then optionally a comma and the
        data payload (e.g., ``"00000,PR-655"`` or ``"-1000"``). The whole
        code field is the error code.

        Parameters
        ----------
        raw : str
            Raw response string from the device.

        Returns
        -------
        PRCommandResponse
            Structured response with parsed status code and data.

        Raises
        ------
        DeviceError
            If the response is empty or does not start with a numeric code.
        """
        code_field, _, data = raw.strip().partition(",")
        code_field = code_field.strip()
        if not _CODE_PATTERN.fullmatch(code_field):
            raise DeviceError(f"Malformed Photo Research response: {raw!r}")

        return PRCommandResponse(
            code=PRResponseCode(int(code_field)), raw_data=data.strip()
        )

    @classmethod
    def discover(cls) -> Self:
        """
        Attempt automatic discovery of a Photo Research device serial port.

        Filters the serial ports by USB metadata before opening any, then
        attempts the PHOTO handshake on each candidate. A port whose VID or
        manufacturer string names another vendor is never opened. Every
        candidate that fails the handshake is closed.

        Returns
        -------
        Self
            A successfully discovered Photo Research device object.

        Raises
        ------
        serial.SerialException
            If no Photo Research device can be found.
        """
        log = logging.getLogger("specio.PR")
        system = platform.system()
        candidates = [
            port
            for port in serial.tools.list_ports.comports()
            if _is_candidate_port(port, system)
        ]

        if not candidates:
            raise serial.SerialException(
                "No candidate serial ports found for a Photo Research device"
            )

        for port in candidates:
            try:
                return cls(port.device)
            except (serial.SerialException, DeviceError) as error:
                log.debug("No Photo Research device on %s: %s", port.device, error)

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
