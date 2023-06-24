"""
Implement support for operations with CR300
"""
import logging
import platform
import re
import time

import serial.tools.list_ports
from colour import SpectralDistribution, SpectralShape

from specio.measurement import RawMeasurement
from specio.spectrometer import SpecRadiometer

from specio.ColorimetryResearch.CR_Definitions import (
    CommandError,
    CommandResponse,
    InstrumentType,
    MeasurementSpeed,
    Model,
    ResponseCode,
    ResponseType,
)

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"

DEFAULT_TIMEOUT = 0.01


class CRSpectrometer(SpecRadiometer):
    """
    RAII Colorimetry Research Spectroradiometers.

    In particular this implementation was developed and tested with the CR300,
    but it should work for CR250 or other spectrometers from CR.
    """

    def __initialize_connection__(self, device: str | None = None) -> str:
        if device is None:
            if platform.system() == "Darwin":
                port_list = list(serial.tools.list_ports.grep("usbmodem"))
            elif platform.system() == "Windows":
                port_list = list(serial.tools.list_ports.grep("Colorimetry"))
            elif platform.system() == "Unix":
                raise NotImplementedError("CR discovery is not implemented for Unix")
            elif platform.system() == "Linux":
                port_list = list(serial.tools.list_ports.grep("ACM"))
            else:
                raise OSError("Could not find any candidates for ColorimetryResearch")

            if len(port_list) > 1:
                raise NotImplementedError(
                    "Too many port candidates found, only a single port may be auto discovered."
                )

            device = port_list[0].device

        self.__port = serial.Serial(device, timeout=DEFAULT_TIMEOUT, baudrate=115200)

    def __init__(
        self,
        device: str | None = None,
        speed: MeasurementSpeed = MeasurementSpeed.NORMAL,
    ):
        """
        Construct CR Controller Obj
        """
        self.__last_cmd_time: float = 0
        self.__initialize_connection__(device=device)

        if self.instrument_type is not InstrumentType.SPECTRORADIOMETER:
            raise RuntimeError("The connected-to device was not a spectroradiometer.")

        self.measurement_speed = speed

        super().__init__(
            manufacturer="Colorimetry Research",
            model=self.model,
            serial_num=self.serial_number,
        )

    @property
    def firmware(self):
        if not hasattr(self, "_firmware") or self._firmware is None:
            response = self.__write_cmd("RC Firmware")
            self._firmware = response.arguments[0]
        return self._firmware

    @property
    def measurement_speed(self) -> MeasurementSpeed:
        response = self.__write_cmd("SM ExposureMode 0")
        response = self.__write_cmd("RS Speed")
        self._measurement_speed = MeasurementSpeed(response.arguments[0].lower())
        return self._measurement_speed

    @measurement_speed.setter
    def measurement_speed(self, speed: MeasurementSpeed):
        t = self.__write_cmd(f"SM Speed {speed.values[0]}")
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
    def serial_number(self):
        if not hasattr(self, "_sn") or self._sn is None:
            response = self.__write_cmd("RC ID")
            self._sn = response.arguments[0]
        return self._sn

    @property
    def model(self):
        if not hasattr(self, "_model") or self._model is None:
            response = self.__write_cmd("RC Model")
            self._model = response.arguments[0]
        return self._model

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
        self.__port.readall()

    def __write_cmd(self, command: str) -> CommandResponse:
        """
        Write cmd to serial port
        """
        log = logging.getLogger("specio.CR")
        log.debug(f"Sending CMD: {command}")

        command = (command + "\n").encode()
        self.__clear_buffer()
        if self.__last_cmd_time + DEFAULT_TIMEOUT > time.time():
            time.sleep(
                max(self.__last_cmd_time + DEFAULT_TIMEOUT + 0.001 - time.time(), 0)
            )

        self.__port.write(command)
        self.__last_cmd_time = time.time()

        while self.__port.in_waiting < 1:
            time.sleep(0.01)

        response = self.__port.readline()

        response = self.__parse_response(response)

        if response.type == ResponseType.error:
            raise CommandError(response, response.arguments[0])
        else:
            return response

    def __parse_response(self, response: str | bytes) -> CommandResponse:
        """
        Parse CR response string
        """
        if type(response) is bytes:
            response = response.decode()
        response = response.strip().split(":")

        args = []
        if response[3].isnumeric() and int(response[3]) > 0 and self.__port.inWaiting():
            for line_num in range(int(response[3])):
                response = self.__port.readline()
                args.append(response)
        else:
            args = response[3:]

        return CommandResponse(
            type=ResponseType(response[0]),
            code=ResponseCode(int(response[1])),
            description=response[2],
            arguments=args,
        )

    def _raw_measure(self) -> SpectralDistribution:
        """
        Make spectral measurement with CR
        """
        response = self.__write_cmd("M")
        response = self.__write_cmd("RM Spectrum")

        args = response.arguments[0].split(",")
        shape = SpectralShape(
            start=float(args[0]), end=float(args[1]), interval=float(args[2])
        )

        data = self.__port.readall()
        data = [float(d) for d in data.decode().splitlines()]

        exposure = self.__write_cmd("RM Exposure").arguments[0]
        exMatch = re.match("\d*\.?\d*", exposure)
        if exMatch:
            exposure = float(exMatch.group()) / 1000
        else:
            exposure = -1

        return RawMeasurement(
            spd=SpectralDistribution(data=data, domain=shape),
            spectrometer_id=self.readable_id,
            exposure=exposure,
        )


if __name__ == "__main__":
    cr = CRSpectrometer()

    print(f"Aperture: {cr.aperture}")
    print(f"Firmware: {cr.firmware}")

    print(f"Measurement Speed: {cr.measurement_speed}")
    cr.measurement_speed = MeasurementSpeed.FAST_2X
    print(f"Measurement Speed: {cr.measurement_speed}")

    print(f"Instrument Type: {cr.instrument_type}")

    pass
