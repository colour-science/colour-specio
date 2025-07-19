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
from typing import Self, cast, final

from aenum import MultiValueEnum
import bidict
import numpy as np
import serial
import serial.tools.list_ports
from colour import SpectralDistribution, SpectralShape

from specio.common import RawSPDMeasurement, SpecRadiometer
from specio.common.colorimeters import Colorimeter, RawColorimeterMeasurement
from specio.common.utility import specio_warning

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CRColorimeter",
    "CRSpectrometer",
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
    def _missing_(cls, _: object) -> "ResponseCode":
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

    class MeasurementSpeed(MultiValueEnum):
        """
        Controls the measurement speed when the CR Exposure Mode is set to "auto"
        """

        SLOW: Self = 0, "0", "slow"  # type: ignore
        NORMAL: Self = 1, "1", "normal"  # type: ignore
        FAST: Self = 2, "2", "fast"  # type: ignore
        FAST_2X: Self = 3, "3", "2x fast"  # type: ignore

    @classmethod
    def discover(cls) -> "CRSpectrometer":
        """Attempt automatic discovery of the CR serial port and return the
        CR spectrometer object.

        Returns
        -------
        CRSpectrometer
            A successfully discovered CR spectrometer object.

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
            except:  # noqa: E722
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
    ) -> None:
        """
        Initialize a CR spectrometer controller.

        Parameters
        ----------
        port : str
            The serial port device path (e.g., '/dev/ttyUSB0', 'COM3').
        speed : MeasurementSpeed, optional
            The measurement speed setting for automatic exposure mode.
            Default is MeasurementSpeed.NORMAL.

        Raises
        ------
        serial.SerialException
            If the serial port cannot be opened or configured.
        """
        self.__last_cmd_time: float = 0
        if isinstance(port, str):
            self._port = serial.Serial(port, **_CR_SERIAL_KWARGS)

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
            response = self._write_cmd("RC Firmware")
            self._firmware = response.arguments[0]
        return self._firmware

    @property
    def measurement_speed(self) -> MeasurementSpeed:
        """The automatic measurement speed of the hardware when in "auto" timing

        Returns
        -------
        MeasurementSpeed
        """
        response = self._write_cmd("SM ExposureMode 0")
        response = self._write_cmd("RS Speed")
        self._measurement_speed = CRSpectrometer.MeasurementSpeed(
            response.arguments[0].lower()
        )
        return self._measurement_speed

    @measurement_speed.setter
    def measurement_speed(self, speed: MeasurementSpeed) -> None:
        """
        Set the automatic measurement speed of the hardware.

        Parameters
        ----------
        speed : MeasurementSpeed
            The desired measurement speed setting.

        Raises
        ------
        CommandError
            If the speed setting command fails.
        """
        _ = self._write_cmd(f"SM Speed {speed.values[0]}")
        self._measurement_speed = speed

    @property
    def aperture(self) -> str:
        """
        Get the current aperture setting of the spectrometer.

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

    @property
    def average_samples(self) -> int:
        response = self._write_cmd("RS ExposureX")
        return int(response.arguments[0])

    @average_samples.setter
    def average_samples(self, num: int) -> None:
        num = num if num > 0 else 1
        num = num if num < 50 else 50
        self._write_cmd(f"SM ExposureX {num:d}")

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
    def instrument_type(self) -> InstrumentType:
        """
        Get the instrument type of the connected device.

        Returns
        -------
        InstrumentType
            The type of the connected instrument (should be SPECTRORADIOMETER).

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
        Send a command to the CR spectrometer and parse the response.

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

    def _apply_measurementspeed_timeout(self) -> None:
        """
        Apply appropriate serial timeout based on current measurement speed and averaging.

        Sets the serial port timeout to accommodate the expected measurement duration
        based on the measurement speed setting and number of averaged samples.
        """
        if self.measurement_speed is CRSpectrometer.MeasurementSpeed.SLOW:
            t = 70
        elif self.measurement_speed is CRSpectrometer.MeasurementSpeed.NORMAL:
            t = 21
        elif self.measurement_speed is CRSpectrometer.MeasurementSpeed.FAST:
            t = 14
        else:
            t = 7
        t *= self.average_samples
        self._port.apply_settings({"timeout": t})

    def _raw_measure(self) -> RawSPDMeasurement:
        """
        Perform a spectral measurement and return raw spectral power distribution.

        Returns
        -------
        RawSPDMeasurement
            Raw measurement data containing spectral power distribution, spectrometer ID, and exposure time.

        Raises
        ------
        CommandError
            If the measurement command fails or times out.
        """
        t = self._port.timeout

        self._apply_measurementspeed_timeout()
        response = self._write_cmd("M")
        self._port.apply_settings({"timeout": t})

        self._port.apply_settings({"timeout": 0.31})
        response = self._write_cmd("RM Spectrum")
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

        exposure = self._write_cmd("RM Exposure").arguments[0]
        exMatch = re.match(r"\d*\.?\d*", exposure)
        exposure = float(exMatch.group()) / 1000 if exMatch else -1

        return RawSPDMeasurement(
            spd=SpectralDistribution(data=data, domain=shape),
            spectrometer_id=self.readable_id,
            exposure=exposure,
        )


@final
class CRColorimeter(Colorimeter):
    """Interface with a colorimetry research brand CR-250 or CR-300 in colorimeter mode.
    
    Implements the `specio.colorimeters.Colorimeter` interface for direct XYZ measurements.

    Raises
    ------
    serial.SerialException
        if `CRColorimeter.discover` fails or there are other serial port issues.
    CommandError
        A error was encountered in parsing the result of the serial command to
        the hardware device.
    """

    @classmethod
    def discover(cls) -> "CRColorimeter":
        """Attempt automatic discovery of the CR serial port and return the
        CR colorimeter object.

        Returns
        -------
        CRColorimeter
            A successfully discovered CR colorimeter object.

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
                sp = serial.Serial(device, **_CR_SERIAL_KWARGS)
                sp.readall()
                sp.write(b"RC InstrumentType\n")

                response = sp.readline()
                if response.startswith(b"OK:0:RC InstrumentType:1"):
                    sp.close()
                    cr = CRColorimeter(device)
                    return cr
            except:  # noqa: E722
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
    ) -> None:
        """
        Initialize a CR colorimeter controller.

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

        self._warn_filter_selection()

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
        Get the current aperture setting of the colorimeter.

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
    def available_filters(self) -> bidict.bidict[int, str]:
        """
        Get the mapping of available optical filters for the colorimeter.

        Returns
        -------
        bidict.bidict[int, str]
            Bidirectional dictionary mapping filter IDs to filter names.
            ID 0 always maps to "None" for no filter selection.

        Raises
        ------
        CommandError
            If the filter query command fails.
        """
        response = self._write_cmd("RC Filter")
        filters = bidict.bidict()
        for arg in response.arguments:
            arg = cast("bytes", arg)
            items = arg.decode().strip().split(",")
            filters[int(items[0])] = items[1]
        filters[0] = "None"
        return filters

    @property
    def current_filters(self) -> tuple[int, int, int]:
        """
        Get the currently selected filter IDs for all three filter positions.

        Returns
        -------
        tuple[int, int, int]
            Tuple of three filter IDs representing the current filter selection
            for positions 1, 2, and 3.

        Raises
        ------
        CommandError
            If the filter status query command fails.
        """
        response = self._write_cmd("RS Filter")
        arguments = response.arguments[0].split(",")

        out = []
        for f in arguments:
            out += [self.available_filters.inverse[f]]
        return tuple(out)

    @current_filters.setter
    def current_filters(self, filters: tuple[int, ...]) -> None:
        """
        Set the current filter selection for all three filter positions.

        Parameters
        ----------
        filters : tuple[int, ...]
            Tuple of filter IDs to set. Maximum 3 filters supported.
            Use -1 or omit positions to deselect filters.

        Raises
        ------
        RuntimeError
            If more than 3 filters are specified.
        CommandError
            If any filter setting command fails.
        """
        if len(filters) > 3:
            RuntimeError("CR-100/120 only supports up to 3 filter selectons!")
        for i in range(1, 4):
            cur_filter_id = filters[i - 1] if i <= len(filters) else -1
            self._write_cmd(f"SM Filter{i:.0f} {cur_filter_id:.0f}")

        self._warn_filter_selection()

    @property
    def current_filters_names(self) -> tuple[str, str, str]:
        """
        Get the names of the currently selected filters.

        Returns
        -------
        tuple[str, str, str]
            Tuple of three filter names corresponding to the current filter selection.

        Raises
        ------
        CommandError
            If the filter status query command fails.
        """
        # ignore type error. Cannot interpret list builder size.
        return tuple([self.available_filters[k] for k in self.current_filters])  # type: ignore

    def _warn_filter_selection(self) -> None:
        """
        Issue warnings about the current filter configuration.

        Emits warnings when no filters are selected, only one filter is selected,
        or multiple filters are stacked, as these configurations may affect
        measurement accuracy and should be verified by the user.
        """
        cur = self.current_filters
        if len(cur) == 0:
            specio_warning("Check colorimeter has no active filters.")
        elif len(cur) == 1:
            specio_warning(
                f"Check colorimeter has one filter: {self.available_filters[cur[0]]}"
            )
        else:
            filters_string = ", ".join([self.available_filters[f] for f in cur])
            specio_warning(f"Check colorimeter has stacked filters: {filters_string}.")

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
            The type of the connected instrument (should be COLORIMETER).

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
        Send a command to the CR colorimeter and parse the response.

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

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """
        Perform a colorimetric measurement and return raw XYZ values.

        Returns
        -------
        RawColorimeterMeasurement
            Raw measurement data containing XYZ values, device ID, and exposure time.

        Raises
        ------
        CommandError
            If the measurement command fails or times out.
        """
        t = self._port.timeout

        self._port.apply_settings({"timeout": 10 + 0.5 * self.average_samples})
        response = self._write_cmd("M")

        self._port.apply_settings({"timeout": 0.21})
        response = self._write_cmd("RM XYZ")

        XYZ = np.asarray([float(s) for s in response.arguments[0].split(",")])

        exposure = self._write_cmd("RM Exposure").arguments[0]
        exMatch = re.match(r"\d*\.?\d*", exposure)
        exposure = float(exMatch.group()) / 1000 if exMatch else -1

        self._port.apply_settings({"timeout": t})

        return RawColorimeterMeasurement(
            XYZ=XYZ,
            device_id=self.readable_id,
            exposure=exposure,
        )
