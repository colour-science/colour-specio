"""
Colorimetry Research spectrometer implementation.
"""

from __future__ import annotations

import re
import time
from typing import Self, final

from aenum import MultiValueEnum
from colour import SpectralDistribution, SpectralShape

from specio.common import RawSPDMeasurement, SpecRadiometer
from specio.common.exceptions import DeviceError

from ._common import (
    CRDeviceBase,
    InstrumentType,
)


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
    def discover(
        cls, expected_instrument_type: InstrumentType | None = None
    ) -> CRSpectrometer:
        """Attempt automatic discovery of the CR serial port and return the
        CR spectrometer object.

        Parameters
        ----------
        expected_instrument_type : InstrumentType | None, optional
            The expected instrument type, defaults to SPECTRORADIOMETER.

        Returns
        -------
        CRSpectrometer
            A successfully discovered CR spectrometer object.

        Raises
        ------
        serial.SerialException
            If no serial port can be automatically linked.
        """
        if expected_instrument_type is None:
            expected_instrument_type = InstrumentType(2)
        return super().discover(expected_instrument_type=expected_instrument_type)

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
        """The measurement speed the instrument uses in auto exposure mode.

        Reading it queries the instrument and changes nothing. Setting it also
        selects auto exposure mode, because the speed applies only there.
        The CR Protocol Manual 1.36 does not say whether the instrument keeps
        its speed across power cycles, so constructing a
        :class:`CRSpectrometer` sets it.

        Returns
        -------
        MeasurementSpeed
        """
        response = self._write_cmd("RS Speed")
        return CRSpectrometer.MeasurementSpeed(response.arguments[0].lower())

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
        self._write_cmd("SM ExposureMode 0")
        self._write_cmd(f"SM Speed {speed.values[0]}")

    def _apply_measurementspeed_timeout(
        self, speed: MeasurementSpeed, samples: int
    ) -> None:
        """
        Apply appropriate serial timeout based on measurement speed and averaging.

        Sets the serial port timeout to accommodate the expected measurement duration
        based on the measurement speed setting and number of averaged samples.

        Parameters
        ----------
        speed : MeasurementSpeed
            The speed the instrument measures at. The caller reads it once per
            measurement, so sizing the window adds no serial exchange.
        samples : int
            The number of averaged samples the window is sized for.
        """
        if speed is CRSpectrometer.MeasurementSpeed.SLOW:
            t = 70
        elif speed is CRSpectrometer.MeasurementSpeed.NORMAL:
            t = 21
        elif speed is CRSpectrometer.MeasurementSpeed.FAST:
            t = 14
        else:
            t = 7
        t *= samples
        self._port.apply_settings({"timeout": t})

    def _raw_measure(self) -> RawSPDMeasurement:
        """
        Perform a spectral measurement and return raw spectral power distribution.

        The reading records the settings it was taken under: ``exposure_mode``
        is ``"auto"`` because the driver forces it, ``speed`` is the lowercase
        speed name, and ``average_samples`` is the value the read window was
        sized from. The speed and the samples are read once and reused for both
        read windows, so recording them adds no serial exchange. If the link
        can't report the average samples, the window and the record both use
        the widest value (see ``_samples_for_timeout``).

        Returns
        -------
        RawSPDMeasurement
            Raw measurement data containing spectral power distribution,
            spectrometer ID, exposure time and settings.

        Raises
        ------
        CommandError
            If the measurement command fails or times out.
        """
        t = self._port.timeout

        # The driver measures in auto exposure mode, where the speed applies
        self._write_cmd("SM ExposureMode 0")
        speed = self.measurement_speed
        samples = self._samples_for_timeout()
        self._apply_measurementspeed_timeout(speed, samples)
        response = self._write_cmd("M")
        self._port.apply_settings({"timeout": t})

        # The spectrum fetch follows a measurement the device has already
        # taken, but it answers on the device's schedule, not ours. The
        # budget here was 0.31 s, which a dark patch outruns: auto-exposure
        # stretches the integration and the fetch waits behind it. Give it
        # the measurement's own budget rather than a constant.
        # Read before the spectrum: asked while its lines are arriving, the
        # model query would take one of them as its answer. It is cached.
        model = self.model
        self._apply_measurementspeed_timeout(speed, samples)
        response = self._write_cmd("RM Spectrum")
        self._port.apply_settings({"timeout": t})

        args = response.arguments[0].split(",")
        if float(args[1]) != 0:
            shape = SpectralShape(
                start=float(args[0]),
                end=float(args[1]),
                interval=float(args[2]),
            )
        elif model == "CR-300":
            shape = SpectralShape(380, 780, 1)
        elif model == "CR-250":
            shape = SpectralShape(380, 780, 4)
        else:
            # The spectrum's lines are still arriving; drain them, or they
            # answer the next command.
            self.resync()
            raise DeviceError(
                f"The {model} reported no spectral range "
                f"({response.arguments[0]!r}), and the driver has no default "
                "range for it"
            )

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
            settings={
                "exposure_mode": "auto",
                "speed": speed.name.lower(),
                "average_samples": str(samples),
            },
        )
