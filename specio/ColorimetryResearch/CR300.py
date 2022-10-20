"""
Implement support for operations with CR300
"""
import logging
import platform
import time

import serial.tools.list_ports
from colour import SpectralDistribution, SpectralShape

from specio.common import RawMeasurement
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

DEFAULT_TIMEOUT = 0.05


class CR300(SpecRadiometer):
    """
    RAII CR300 Implementation.
    """

    def __darwin_find_port(self):
        """
        Auto search for CR on Darwin
        """
        for port in serial.tools.list_ports.grep("usbmodem"):
            if port.manufacturer != "Colorimetry Research, Inc.":
                continue
            try:
                self.__port = serial.Serial(port.device, timeout=DEFAULT_TIMEOUT)
                self.__check_instrument_type()
            except Exception as err:
                continue
            else:
                return
        else:
            raise OSError("Could not automatically find CR device.")

    def __win_find_port(self):
        raise NotImplementedError("CR discovery is not implemented for Windows")

    def __unix_find_port(self):
        raise NotImplementedError("CR discovery is not implemented for Unix")

    def __linux_find_port(self):
        """_summary_"""
        for port in serial.tools.list_ports.grep("ACM"):
            if port.manufacturer != "Colorimetry Research, Inc.":
                continue
            try:
                self.__port = serial.Serial(port.device, timeout=DEFAULT_TIMEOUT)
                self.__check_instrument_type()
            except Exception as err:
                continue
            else:
                return
        else:
            raise OSError("Could not automatically find CR device.")

        pass

    def __initialize_connection__(self, device: str | None = None) -> str:
        if device is None:
            if platform.system() == "Darwin":
                self.__darwin_find_port()
            elif platform.system() == "Windows":
                self.__win_find_port()
            elif platform.system() == "Unix":
                self.__unix_find_port()
            elif platform.system() == "Linux":
                self.__linux_find_port()
        else:
            self.__port = serial.Serial(device, timeout=DEFAULT_TIMEOUT)
            self.__check_instrument_type()

        return self.__port.portstr

    def __init__(
        self,
        device: str | None = None,
        speed: MeasurementSpeed = MeasurementSpeed.NORMAL,
    ):
        """
        Construct CR Controller Obj
        """
        self.__last_cmd_time = 0
        device = self.__initialize_connection__(device=device)

        try:

            response = self.__write_cmd("RC ID")
            _sn = response.arguments[0]

            response = self.__write_cmd("RC Model")
            _model = Model(response.arguments[0])

            self.__check_aperture()

            response = self.__write_cmd("RC Firmware")
            self.firmware = response.arguments[0]

            self.set_measurement_speed(speed)

            super().__init__(
                manufacturer="Colorimetry Research", model=_model, serial_num=_sn
            )

        except Exception as err:
            raise OSError(f"Could not initailize CR300 on port {device}") from err

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

        return RawMeasurement(
            spd=SpectralDistribution(data=data, domain=shape),
            spectrometer_id=self.readable_id,
            exposure=0.1,
        )

    def set_measurement_speed(self, speed: MeasurementSpeed) -> ResponseCode:
        """
        Set measurement speed mode for auto exposure
        """
        response = self.__write_cmd(f"SM Speed {speed.values[0]}")
        self.__check_measurement_speed()
        return response

    def __check_measurement_speed(self) -> MeasurementSpeed:
        """
        Get measurement speed mode for auto exposure
        """
        response = self.__write_cmd("RS Speed")
        self.measurement_speed = MeasurementSpeed(response.arguments[0].lower())
        return self.measurement_speed

    def __check_aperture(self):
        """
        Get spectrometer aperture value
        """
        response = self.__write_cmd("RS Aperture")
        self.aperture = response.arguments[0]

    def __check_instrument_type(self):
        """
        Check that the connected device is a spectrometer
        """
        response = self.__write_cmd("RC InstrumentType")
        self.instrument_type = InstrumentType(response.arguments[0])
        if self.instrument_type != InstrumentType.SPECTRORADIOMETER:
            raise OSError(
                f"Instrument on {self.__port.port} is not type: spectroradiometer"
            )

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
        if self.__last_cmd_time + 0.25 > time.time():
            time.sleep(max(self.__last_cmd_time + 0.255 - time.time(), 0))

        self.__port.write(command)
        self.__last_cmd_time = time.time()

        while self.__port.in_waiting < 1:
            time.sleep(0.05)

        response = self.__port.readline()

        response = CR300.__parse_response(response)

        if response.type == ResponseType.error:
            raise CommandError(response, response.arguments[0])
        else:
            return response

    def __parse_response(response: str | bytes) -> CommandResponse:
        """
        Parse CR response string
        """
        if type(response) is bytes:
            response = response.decode()
        response = response.strip().split(":")

        return CommandResponse(
            type=ResponseType(response[0]),
            code=ResponseCode(int(response[1])),
            description=response[2],
            arguments=response[3:],
        )


if __name__ == "__main__":
    cr = CR300()
    pass
    cr.measure()
