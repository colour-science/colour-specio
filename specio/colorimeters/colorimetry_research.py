"""
Implement support for operations with CR300
"""

import logging
import platform
import re
import textwrap
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from types import MappingProxyType
from typing import cast, final

import numpy as np
import serial.tools.list_ports
from aenum import MultiValueEnum

from specio.colorimeters.common import Colorimeter, RawColorimeterMeasurement
from specio.spectrometers.colorimetry_research import InstrumentType

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"
__all__ = []


class Model(Enum):
    """
    Identifies the CR model
    =====
    Values are based on the response to "RC Model" command.
    """

    CR100 = "CR-100"
    CR120 = "CR-120"


class ResponseType(bytes, Enum):
    """
    Identifies the success / failure of any CR command.
    """

    ERROR = b"ER"
    OK = b"OK"


class ResponseCode(int, MultiValueEnum):
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
    def _missing_(cls, _: object):
        """
        Set the default error code to RESERVED
        =======================================
        """
        return cls.RESERVED


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


@final
class CRColorimeter(Colorimeter):
    """Interface with a colorimetry research brand CR-250 or CR-300. Implements
    the `specio.spectrometers.SpecRadiometer`

    Raises
    ------
    serial.SerialException
        if `CRSpectrometer.discovery` fails or there are other serial port issues.
    CommandError
        A error was encountered in parsing the result of the serial command to
        the hardware device.
    """

    DEFAULT_TIMEOUT = 0.01

    CR_SERIAL_KWARGS: Mapping = MappingProxyType(
        {
            "baudrate": 115200,
            "bytesize": 8,
            "parity": "N",
            "rtscts": True,
            "timeout": 0.01,
        }
    )

    @classmethod
    def discover(cls) -> "CRColorimeter":
        """Attempt automatic discovery of the CR serial port and return the
        CR spectrometer object.

        Returns
        -------
        CRSpectrometer
            A successfully automatic CS2000 object.

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
            raise NotImplementedError(
                "CR discovery is not implemented for Unix"
            )
        elif platform.system() == "Linux":
            port_list = list(serial.tools.list_ports.grep("ACM"))
        else:
            port_list = serial.tools.list_ports.comports()

        if len(port_list) == 0:
            raise serial.SerialException("No serial ports found on machine")

        for p in port_list:
            try:
                device = p.device  # type: ignore
                sp = serial.Serial(device, **cls.CR_SERIAL_KWARGS)
                sp.read_all()
                sp.write(b"RC InstrumentType\n")

                response = sp.readline()
                if response.startswith(b"OK:0:RC InstrumentType:1"):
                    sp.close()
                    cr = CRColorimeter(device)
                    return cr
            except:  # noqa: S112,E722
                continue

        raise serial.SerialException(
            textwrap.dedent(
                """Could not connect to any colorimetry research colorimeter.
                Check connection and device power."""
            )
        )

    def __init__(
        self,
        port: str,
    ):
        """
        Construct CR Controller Obj
        """
        self.__last_cmd_time: float = 0
        if isinstance(port, str):
            self._port = serial.Serial(port, **self.CR_SERIAL_KWARGS)

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
            response = self.__write_cmd("RC Firmware")
            self._firmware = response.arguments[0]
        return self._firmware

    @property
    def aperture(self):
        """
        Get spectrometer aperture value
        """
        if not hasattr(self, "_aperture") or self._aperture is None:
            response = self.__write_cmd("RS Aperture")
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
            response = self.__write_cmd("RC ID")
            self._sn = response.arguments[0]
        return self._sn

    @cached_property
    def filters_list(self) -> dict[int, str]:
        response = self.__write_cmd("RC Filter")
        filters = {}
        for arg in response.arguments:
            arg = cast(bytes, arg)
            items = arg.decode().strip().split(",")
            filters[int(items[0])] = items[1]
        return filters

    @property
    def current_filters(self):
        available_filters = self.filters_list
        response = self.__write_cmd("RS Filter")
        arguments = response.arguments[0].split(",")

    @cached_property
    def model(self) -> str:
        """The model name

        Returns
        -------
        str
        """
        response = self.__write_cmd("RC Model")
        return response.arguments[0]

    @property
    def instrument_type(self):
        """
        Check that the connected device is a spectrometer
        """
        if (
            not hasattr(self, "_instrument_type")
            or self._instrument_type is None
        ):
            response = self.__write_cmd("RC InstrumentType")
            i_type = InstrumentType(response.arguments[0])
            self._instrument_type = i_type

        return self._instrument_type

    def __clear_buffer(self):
        """
        Clear input buffer
        """
        self._port.readall()

    def __write_cmd(self, command: str) -> CommandResponse:
        """
        Write cmd to serial port
        """
        log = logging.getLogger("specio.CR")
        log.debug("Sending CMD: %s", command)

        enc_command: bytes = (command + "\n").encode()
        self.__clear_buffer()
        if self.__last_cmd_time + self.DEFAULT_TIMEOUT > time.time():
            time.sleep(
                max(
                    self.__last_cmd_time
                    + self.DEFAULT_TIMEOUT
                    + 0.001
                    - time.time(),
                    0,
                )
            )

        self._port.write(enc_command)
        self.__last_cmd_time = time.time()

        while self._port.in_waiting < 1:
            time.sleep(0.01)

        response = self._port.readline()

        response = self._parse_response(response)

        if response.type == ResponseType.ERROR:
            raise CommandError(response, response.arguments[0])
        else:
            return response

    def _parse_response(self, data: bytes) -> CommandResponse:
        """
        Parse CR response string
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

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """
        Make spectral measurement with CR
        """
        response = self.__write_cmd("M")
        response = self.__write_cmd("RM XYZ")
        XYZ = np.asarray([float(s) for s in response.arguments[0].split(",")])
        exposure = self.__write_cmd("RM Exposure").arguments[0]
        exMatch = re.match(r"\d*\.?\d*", exposure)
        exposure = float(exMatch.group()) / 1000 if exMatch else -1

        return RawColorimeterMeasurement(
            XYZ=XYZ,
            device_id=self.readable_id,
            exposure=exposure,
        )
