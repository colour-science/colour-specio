"""
Colorimetry Research spectrometer implementation.
"""

import re
import time
from typing import Self, final

from aenum import MultiValueEnum
from colour import SpectralDistribution, SpectralShape

from specio.common import RawSPDMeasurement, SpecRadiometer

from ._common import CRDeviceBase, InstrumentType


@final
class CRSpectrometer(CRDeviceBase, SpecRadiometer):
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
        return super().discover(
            expected_instrument_type=InstrumentType.SPECTRORADIOMETER
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
        super().__init__(port)
        self.measurement_speed = speed

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
