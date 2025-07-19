"""
Common base classes and utilities for Colorimetry Research devices.
"""

import logging
import platform
import textwrap
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from types import MappingProxyType
from typing import Self

import serial
import serial.tools.list_ports
from aenum import MultiValueEnum

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CRDeviceBase",
    "CommandError",
    "CommandResponse",
    "InstrumentType",
    "Model",
    "ResponseCode",
    "ResponseType",
]


_COMMAND_TIMEOUT = 0.05
_DEFAULT_SERIAL_TIMEOUT = 0.025
_CR_SERIAL_KWARGS: Mapping = MappingProxyType(
    {
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "N",
        "rtscts": True,
        "timeout": _DEFAULT_SERIAL_TIMEOUT,
    }
)


class InstrumentType(MultiValueEnum):
    """
    Identifies the type of instrument
    =====
    0: Photometer
    1: Colorimeter
    2: Spectroradiometer
    """

    PHOTOMETER = 0, "0"
    COLORIMETER = 1, "1"
    SPECTRORADIOMETER = 2, "2"


class Model(Enum):
    """
    Identifies the CR model
    =====
    Values are based on the response to "RC Model" command.
    """

    CR300 = "CR-300"
    CR250 = "CR-250"


class ResponseType(bytes, Enum):
    """
    Identifies the success / failure of any CR command.
    """

    ERROR = b"ER"
    OK = b"OK"


class ResponseCode(int, Enum):
    """
    Error codes for Colorimetry Research CR-300 and other model spectrometers
    =====
    """

    OK = 0
    INVALID_COMMAND = -500

    TOO_DARK = 100
    CANT_SYNC_CONST = 101
    CANT_SYNC_AUTO = 102
    SYNC_TOO_LOW = 103

    INVALID_SYNC_MODE = -300, -521
    INVALID_SYNC_PERIOD = -301
    CANT_SYNC_TO_LIGHT = -302

    LIGHT_INTENSITY_FLUCTUATION = -303
    LIGHT_INTENSITY_TOO_LOW = -304
    LIGHT_INTENSITY_UNMEASURABLE = -305
    LIGHT_INTENSITY_TOO_HIGH = -306

    HARDWARE_MALFUNCTION = -331
    MATRIX_VERSION_MISMATCH = -332
    INVALID_MATRIX_INDEX = -333

    NO_CIE_TABLES = -334
    NO_CMF_TABLES = -335

    NO_MATRIX_FOR_ID = -336

    DUPLICATE_FILTER_SELECTION = -505
    NO_ACCESSORY_FOR_INDEX = -506
    NO_FILTER_FOR_INDEX = -507
    INDEX_NOT_VALID_ACCESSORY = -508
    INDEX_NOT_VALID_FILTER = -509, -510, -511

    INVALID_RANGE_MODE = -512
    INVALID_RANGE_INDEX = -513
    INVALID_EXPOSURE_MULTIPLIER = -514

    INDEX_DOESNT_SELECT_APERTURE = -515

    INVALID_EXPOSURE_MODE = -518
    INVALID_EXPOSURE_VALUE = -519

    INVALID_SYNC_FREQUENCY = -522

    INVALID_MATRIX_MODE = -552
    INVALID_MATRIX_ID = -553
    INVALID_MATRIX_NAME = -555

    ERRROR_SAVING_MATRIX_FLASH = -559
    INVALID_USER_CALIBRATION_MODE = -560

    RESERVED = -999

    @classmethod
    def _missing_(cls, value: object) -> "ResponseCode":
        """
        Set the default error code to RESERVED when an unknown code is encountered.

        Parameters
        ----------
        _ : object
            The unknown value that was not found in the enum.

        Returns
        -------
        ResponseCode
            The RESERVED error code as a fallback.
        """
        return ResponseCode.RESERVED


@dataclass
class CommandResponse:
    """
    Response data from Colorimetry Research
    """

    type: ResponseType
    code: ResponseCode
    description: str
    arguments: list[str]


class CommandError(Exception):
    """
    Describes an issue with sending a command to CR
    """

    def __init__(self, response: CommandResponse, *args: object) -> None:
        self.response = response
        super().__init__(*args)


class CRDeviceBase(ABC):
    """
    Abstract base class for Colorimetry Research devices.

    Provides common functionality shared between spectrometers and colorimeters,
    including serial communication, command parsing, and device properties.
    """

    def __init__(self, port: str) -> None:
        """
        Initialize base CR device with serial port.

        Parameters
        ----------
        port : str
            The serial port device path (e.g., '/dev/ttyUSB0', 'COM3').

        Raises
        ------
        serial.SerialException
            If the serial port cannot be opened or configured.
        """
        self.__last_cmd_time: float = 0
        if isinstance(port, str):
            self._port = serial.Serial(port, **_CR_SERIAL_KWARGS)

    @classmethod
    def discover(cls, expected_instrument_type: InstrumentType) -> Self:
        """
        Attempt automatic discovery of the CR serial port and return the device object.

        Parameters
        ----------
        expected_instrument_type : InstrumentType
            The expected instrument type to discover (COLORIMETER or SPECTRORADIOMETER).

        Returns
        -------
        Self
            A successfully discovered CR device object.

        Raises
        ------
        serial.SerialException
            If no serial port can be automatically linked.
        """
        if platform.system() == "Darwin":
            port_list = list(serial.tools.list_ports.grep("usbmodem"))
        elif platform.system() == "Windows":
            port_list = list(serial.tools.list_ports.grep("Colorimetry"))
        elif platform.system() == "Unix":
            raise NotImplementedError("CR discovery is not implemented for Unix")
        elif platform.system() == "Linux":
            port_list = list(serial.tools.list_ports.grep("ACM"))
        else:
            port_list = serial.tools.list_ports.comports()

        if len(port_list) == 0:
            raise serial.SerialException("No serial ports found on machine")

        device_type_name = expected_instrument_type.name.lower()

        for p in port_list:
            try:
                device = p.device  # type: ignore
                sp = serial.Serial(device, **_CR_SERIAL_KWARGS)
                sp.readall()
                sp.write(b"RC InstrumentType\n")

                response = sp.readline()
                expected_response = (
                    f"OK:0:RC InstrumentType:{expected_instrument_type.value}".encode()
                )
                if response.startswith(expected_response):
                    sp.close()
                    return cls(device)
            except:  # noqa: E722
                continue

        raise serial.SerialException(
            textwrap.dedent(
                f"""Could not connect to any colorimetry research {device_type_name}.
                Check connection and device power."""
            )
        )

    @property
    def manufacturer(self) -> str:
        """Return mfr name"""
        return "Colorimetry Research"

    @property
    def firmware(self) -> str:
        """The firmware version on the hardware

        Returns
        -------
        str
        """
        if not hasattr(self, "_firmware") or self._firmware is None:
            response = self._write_cmd("RC Firmware")
            self._firmware = response.arguments[0]
        return self._firmware

    @property
    def aperture(self) -> str:
        """
        Get the current aperture setting of the device.

        Returns
        -------
        str
            The aperture identifier or description from the hardware.

        Raises
        ------
        CommandError
            If the aperture query command fails.
        """
        if not hasattr(self, "_aperture") or self._aperture is None:
            response = self._write_cmd("RS Aperture")
            self._aperture = response.arguments[0]
        return self._aperture

    @property
    def serial_number(self) -> str:
        """The hardware serial number

        Returns
        -------
        str
        """
        if not hasattr(self, "_sn") or self._sn is None:
            response = self._write_cmd("RC ID")
            self._sn = response.arguments[0]
        return self._sn

    @cached_property
    def model(self) -> str:
        """The model name

        Returns
        -------
        str
        """
        response = self._write_cmd("RC Model")
        return response.arguments[0]

    @property
    def average_samples(self) -> int:
        """
        Get the number of samples to average for each measurement.

        Returns
        -------
        int
            Number of samples averaged per measurement (1-50).

        Raises
        ------
        CommandError
            If the exposure multiplier query command fails.
        """
        response = self._write_cmd("RS ExposureX")
        return int(response.arguments[0])

    @average_samples.setter
    def average_samples(self, num: int) -> None:
        """
        Set the number of samples to average for each measurement.

        Parameters
        ----------
        num : int
            Number of samples to average (will be clamped to 1-50 range).

        Raises
        ------
        CommandError
            If the exposure multiplier setting command fails.
        """
        num = num if num > 0 else 1
        num = num if num < 50 else 50
        self._write_cmd(f"SM ExposureX {num:d}")

    @property
    def instrument_type(self) -> InstrumentType:
        """
        Get the instrument type of the connected device.

        Returns
        -------
        InstrumentType
            The type of the connected instrument.

        Raises
        ------
        CommandError
            If the instrument type query command fails.
        """
        if not hasattr(self, "_instrument_type") or self._instrument_type is None:
            response = self._write_cmd("RC InstrumentType")
            i_type = InstrumentType(response.arguments[0])
            self._instrument_type = i_type

        return self._instrument_type

    def __clear_buffer(self) -> None:
        """
        Clear the serial port input buffer to remove any pending data.

        This method temporarily sets a short timeout, reads all pending data,
        then restores the original timeout. Used to ensure clean communication
        before sending new commands.
        """
        t = self._port.timeout
        self._port.apply_settings({"timeout": _DEFAULT_SERIAL_TIMEOUT})
        self._port.readall()
        self._port.apply_settings({"timeout": t})

    def _write_cmd(self, command: str) -> CommandResponse:
        """
        Send a command to the CR device and parse the response.

        Parameters
        ----------
        command : str
            The command string to send to the device (without newline terminator).

        Returns
        -------
        CommandResponse
            Parsed response from the device containing type, code, description and arguments.

        Raises
        ------
        CommandError
            If the device returns an error response.
        """
        log = logging.getLogger("specio.CR")
        log.debug("Sending CMD: %s", command)

        enc_command: bytes = (command + "\n").encode()
        if self.__last_cmd_time + _COMMAND_TIMEOUT > time.time():
            time.sleep(
                max(
                    self.__last_cmd_time + _COMMAND_TIMEOUT + 0.001 - time.time(),
                    0,
                )
            )

        self.__clear_buffer()
        self._port.write(enc_command)
        self.__last_cmd_time = time.time()

        response = self._port.readline()

        response = self._parse_response(response)

        if response.type == ResponseType.ERROR:
            raise CommandError(response, response.arguments[0])
        else:
            return response

    def _parse_response(self, data: bytes) -> CommandResponse:
        """
        Parse the raw response bytes from the CR device into a structured format.

        Parameters
        ----------
        data : bytes
            Raw response data from the serial port.

        Returns
        -------
        CommandResponse
            Structured response containing parsed type, code, description and arguments.
        """
        response = data.strip().split(b":")

        args = []
        if (
            response[3].decode().isnumeric()
            and int(response[3]) > 0
            and self._port.in_waiting
        ):
            for _ in range(int(response[3])):
                n_response = self._port.readline()
                args.append(n_response)
        else:
            args = [r.decode() for r in response[3:]]

        return CommandResponse(
            type=ResponseType(response[0]),
            code=ResponseCode(int(response[1].decode())),
            description=response[2].decode(),
            arguments=args,
        )

    @abstractmethod
    def _raw_measure(self):
        """
        Perform a raw measurement and return device-specific measurement data.

        This method must be implemented by concrete device classes.
        """
        ...
