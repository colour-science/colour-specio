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
from typing import Self, final

import serial.tools.list_ports
from aenum import MultiValueEnum
from colour import SpectralDistribution, SpectralShape

from specio.spectrometers.common import RawSPDMeasurement, SpecRadiometer

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"
__all__ = []


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


class MeasurementSpeed(MultiValueEnum):
    """
    Controls the measurement speed when the CR Exposure Mode is set to "auto"
    """

    SLOW: Self = 0, "0", "slow"  # type: ignore
    NORMAL: Self = 1, "1", "normal"  # type: ignore
    FAST: Self = 2, "2", "fast"  # type: ignore
    FAST_2X: Self = 3, "3", "2x fast"  # type: ignore


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
class CRSpectrometer(SpecRadiometer):
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

    COMMAND_TIMEOUT = 0.1

    CR300_SERIAL_KWARGS: Mapping = MappingProxyType(
        {
            "baudrate": 115200,
            "bytesize": 8,
            "parity": "N",
            "rtscts": True,
            "timeout": 0.05,
        }
    )

    @classmethod
    def discover(cls) -> "CRSpectrometer":
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
            raise NotImplementedError("CR discovery is not implemented for Unix")
        elif platform.system() == "Linux":
            port_list = list(serial.tools.list_ports.grep("ACM"))
        else:
            port_list = serial.tools.list_ports.comports()

        if len(port_list) == 0:
            raise serial.SerialException("No serial ports found on machine")

        for p in port_list:
            try:
                device = p.device  # type: ignore
                sp = serial.Serial(
                    device,
                    **{
                        "baudrate": 115200,
                        "bytesize": 8,
                        "parity": "N",
                        "rtscts": True,
                        "timeout": 0.1,
                    },
                )
                sp.read_all()
                sp.write(b"RC InstrumentType\n")

                response = sp.readline()
                if response.startswith(b"OK:0:RC InstrumentType:2"):
                    sp.close()
                    cr = CRSpectrometer(device)
                    return cr
            except:  # noqa: S112,E722
                continue

        raise serial.SerialException(
            textwrap.dedent(
                """Could not connect to any colorimetry research spectrometer.
                Check connection and device power."""
            )
        )

    def __init__(
        self,
        port: str,
        speed: MeasurementSpeed = MeasurementSpeed.NORMAL,
    ):
        """
        Construct CR Controller Obj
        """
        self.__last_cmd_time: float = 0
        if isinstance(port, str):
            self._port = serial.Serial(port, **self.CR300_SERIAL_KWARGS)

        self.measurement_speed = speed

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
    def measurement_speed(self) -> MeasurementSpeed:
        """The automatic measurement speed of the hardware when in "auto" timing

        Returns
        -------
        MeasurementSpeed
        """
        response = self.__write_cmd("SM ExposureMode 0")
        response = self.__write_cmd("RS Speed")
        self._measurement_speed = MeasurementSpeed(response.arguments[0].lower())
        return self._measurement_speed

    @measurement_speed.setter
    def measurement_speed(self, speed: MeasurementSpeed):
        _ = self.__write_cmd(f"SM Speed {speed.values[0]}")
        self._measurement_speed = speed

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

    @property
    def ExposureMultiplier(self) -> int:
        if not hasattr(self, "_ExposureX"):
            response = self.__write_cmd("RM ExposureX")
            self._ExposureX = int(response.arguments[0])
        return self._ExposureX

    @ExposureMultiplier.setter
    def ExposureMultiplier(self, multiplier: int) -> None:
        self.__write_cmd(f"SM ExposureX {multiplier:d}")
        del self._ExposureX

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
        if not hasattr(self, "_instrument_type") or self._instrument_type is None:
            response = self.__write_cmd("RC InstrumentType")
            i_type = InstrumentType(response.arguments[0])
            self._instrument_type = i_type

        return self._instrument_type

    def __clear_buffer(self):
        """
        Clear input buffer
        """
        t = self._port.timeout
        self._port.apply_settings({"timeout": 0.05})
        self._port.read_all()
        self._port.apply_settings({"timeout": t})

    def __write_cmd(self, command: str) -> CommandResponse:
        """
        Write cmd to serial port
        """
        log = logging.getLogger("specio.CR")
        log.debug("Sending CMD: %s", command)

        enc_command: bytes = (command + "\n").encode()
        if self.__last_cmd_time + self.COMMAND_TIMEOUT > time.time():
            time.sleep(
                max(
                    self.__last_cmd_time + self.COMMAND_TIMEOUT + 0.001 - time.time(),
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

    def _raw_measure(self) -> RawSPDMeasurement:
        """
        Make spectral measurement with CR
        """
        t = self._port.timeout
        self._port.apply_settings({"timeout": 31})
        response = self.__write_cmd("M")
        self._port.apply_settings({"timeout": t})

        self._port.apply_settings({"timeout": 1.5})
        response = self.__write_cmd("RM Spectrum")
        self._port.apply_settings({"timeout": t})

        args = response.arguments[0].split(",")
        if float(args[1]) != 0:
            shape = SpectralShape(
                start=float(args[0]),
                end=float(args[1]),
                interval=float(args[2]),
            )
        elif self.model == "CR-300":
            shape = SpectralShape(380, 780, 1)
        elif self.model == "CR-250":
            shape = SpectralShape(380, 780, 4)

        time.sleep(0.01)
        data = [self._port.readline() for _ in range(len(shape.wavelengths))]
        data = [float(d.decode()) for d in data]

        exposure = self.__write_cmd("RM Exposure").arguments[0]
        exMatch = re.match(r"\d*\.?\d*", exposure)
        exposure = float(exMatch.group()) / 1000 if exMatch else -1

        return RawSPDMeasurement(
            spd=SpectralDistribution(data=data, domain=shape),
            spectrometer_id=self.readable_id,
            exposure=exposure,
        )
