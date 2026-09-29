"""
Photo Research spectrometer implementation.
"""

from __future__ import annotations

import logging
import re
from functools import cached_property
from typing import ClassVar, final

from colour import SpectralDistribution

from specio.common import RawSPDMeasurement, SpecRadiometer
from specio.common.exceptions import DeviceError

from ._common import PRDeviceBase

_MEASUREMENT_TIMEOUT = 60.0
_DATA_LINE_TIMEOUT = 2.0
_MS_PER_SECOND = 1000.0
_MIN_AVERAGE_SAMPLES = 1
_MAX_AVERAGE_SAMPLES = 99

# Field positions in the D602 verbose setup report, counted after the
# error code (PR-655/670 User Manual, p.148).
_D602_EXPOSURE_TIME_FIELD = 7
_D602_CYCLES_FIELD = 9

_LEADING_NUMBER = re.compile(r"\s*(\d+(?:\.\d+)?)")
_MSEC_VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*msec")


def _leading_number(field: str, report: str) -> float:
    """
    Parse the number at the start of a setup-report field such as ``0 msec``.

    Parameters
    ----------
    field : str
        The field text.
    report : str
        The whole report, quoted in the error message.

    Returns
    -------
    float
        The leading number.

    Raises
    ------
    DeviceError
        If the field does not start with a number.
    """
    match = _LEADING_NUMBER.match(field)
    if match is None:
        raise DeviceError(f"Malformed Photo Research setup report: {report!r}")
    return float(match.group(1))


@final
class PRSpectrometer(PRDeviceBase, SpecRadiometer):
    """
    Interface with a Photo Research SpectraScan PR-655 spectroradiometer.

    Implements the `specio.common.SpecRadiometer` interface for the
    Photo Research PR-655. The PR-670 uses the same remote protocol.

    Raises
    ------
    serial.SerialException
        If discovery fails or there are serial port issues.
    PRCommandError
        If a command to the hardware device returns an error code.
    DeviceError
        If the device returns a reply the driver cannot parse.
    """

    ADAPTIVE_EXPOSURE: ClassVar[float] = 0.0
    """Exposure value that selects, and reports, adaptive exposure mode."""

    @property
    def exposure(self) -> float:
        """
        Get the exposure (integration) time setting in seconds.

        Reads the verbose setup report (D602). In adaptive mode the report
        gives an exposure time of 0, so the getter returns
        :attr:`ADAPTIVE_EXPOSURE`. The integration time that adaptive mode
        chose for a measurement is in that measurement's ``exposure``.

        Returns
        -------
        float
            Fixed exposure time in seconds, or :attr:`ADAPTIVE_EXPOSURE`.

        Raises
        ------
        PRCommandError
            If the configuration query fails.
        DeviceError
            If the report has no readable exposure time.
        """
        report = self._write_cmd("D602").raw_data
        fields = report.split(",")
        if len(fields) <= _D602_EXPOSURE_TIME_FIELD:
            raise DeviceError(f"Malformed Photo Research setup report: {report!r}")
        milliseconds = _leading_number(fields[_D602_EXPOSURE_TIME_FIELD], report)
        return milliseconds / _MS_PER_SECOND

    @exposure.setter
    def exposure(self, seconds: float) -> None:
        """
        Set the detector exposure (integration) time.

        Sends the ``SE`` command, which takes whole milliseconds. The PR-655
        accepts 3 ms to 6 s and the PR-670 6 ms to 30 s. The device rejects
        other values with ``INVALID_EXPOSURE_VALUE``.

        Parameters
        ----------
        seconds : float
            Exposure time in seconds, or :attr:`ADAPTIVE_EXPOSURE` to select
            adaptive mode.

        Raises
        ------
        ValueError
            If ``seconds`` is negative.
        PRCommandError
            If the device rejects the exposure time.
        """
        if seconds < 0:
            raise ValueError(f"exposure must not be negative, got {seconds!r}")
        milliseconds = 0
        if seconds != self.ADAPTIVE_EXPOSURE:
            milliseconds = max(1, round(seconds * _MS_PER_SECOND))
        self._write_cmd(f"SE{milliseconds:d}")

    @property
    def average_samples(self) -> int:
        """
        Get the number of measurement cycles averaged per reading.

        Returns
        -------
        int
            Number of averaged cycles.

        Raises
        ------
        PRCommandError
            If the configuration query fails.
        DeviceError
            If the report has no readable cycle count.
        """
        report = self._write_cmd("D602").raw_data
        fields = report.split(",")
        if len(fields) <= _D602_CYCLES_FIELD:
            raise DeviceError(f"Malformed Photo Research setup report: {report!r}")
        return int(_leading_number(fields[_D602_CYCLES_FIELD], report))

    @average_samples.setter
    def average_samples(self, count: int) -> None:
        """
        Set the number of measurement cycles to average per reading.

        Sends the ``SN`` command.

        Parameters
        ----------
        count : int
            Number of measurements to average, clamped to 1-99.

        Raises
        ------
        PRCommandError
            If the setup command fails.
        """
        count = max(_MIN_AVERAGE_SAMPLES, min(count, _MAX_AVERAGE_SAMPLES))
        self._write_cmd(f"SN{count:d}")

    @cached_property
    def _spectral_points(self) -> int:
        """
        The number of spectral data points, from the D120 hardware report.

        Returns
        -------
        int
            Number of ``wl,value`` lines that D5 returns.

        Raises
        ------
        DeviceError
            If the report has no readable point count.
        """
        report = self._write_cmd("D120").raw_data
        points = report.split(",")[0].strip()
        if not points.isdigit():
            raise DeviceError(f"Malformed Photo Research D120 report: {report!r}")
        return int(points)

    def _read_spectrum(self, points: int) -> tuple[list[float], list[float]]:
        """
        Read the ``wl,value`` lines that follow a D5 header.

        Parameters
        ----------
        points : int
            Number of lines to read.

        Returns
        -------
        tuple[list[float], list[float]]
            Wavelengths in nanometres and the spectral value at each.

        Raises
        ------
        DeviceError
            If fewer lines arrive than expected, or a line is malformed.
        """
        wavelengths: list[float] = []
        values: list[float] = []
        with self._port_timeout(_DATA_LINE_TIMEOUT):
            for index in range(points):
                line = self._read_response()
                if not line:
                    raise DeviceError(f"D5 returned {index} of {points} spectral lines")
                try:
                    wavelength, value = (float(part) for part in line.split(","))
                except ValueError as error:
                    raise DeviceError(
                        f"Malformed D5 spectral line: {line!r}"
                    ) from error
                wavelengths.append(wavelength)
                values.append(value)
        return wavelengths, values

    def _last_exposure(self) -> float:
        """
        Return the exposure time of the last measurement, from D13.

        Returns
        -------
        float
            Exposure time in seconds.

        Raises
        ------
        DeviceError
            If the report has no readable exposure time.
        """
        report = self._write_cmd("D13").raw_data
        match = _MSEC_VALUE.search(report)
        if match is None:
            raise DeviceError(f"Malformed Photo Research D13 report: {report!r}")
        return float(match.group(1)) / _MS_PER_SECOND

    def _raw_measure(self) -> RawSPDMeasurement:
        """
        Perform a spectral measurement and return raw spectral data.

        Triggers a measurement (M0), then retrieves the spectrum (D5). D5
        returns a header line, then one ``wavelength,value`` line per
        spectral point. The spectral domain comes from those wavelengths,
        and D13 supplies the exposure time the measurement used.

        Returns
        -------
        RawSPDMeasurement
            Raw measurement data containing spectral power distribution,
            spectrometer ID, and exposure time in seconds.

        Raises
        ------
        PRCommandError
            If the measurement or data retrieval command returns an error.
        DeviceError
            If the spectral data is short or malformed.
        """
        log = logging.getLogger("specio.PR")
        points = self._spectral_points
        spectrometer_id = self.readable_id

        log.debug("Triggering spectral measurement (M0)")
        self._write_cmd("M0", timeout=_MEASUREMENT_TIMEOUT)

        log.debug("Retrieving spectral data (D5)")
        self._write_cmd("D5")
        wavelengths, values = self._read_spectrum(points)
        exposure = self._last_exposure()

        log.debug("Measurement complete: %d spectral points", len(values))

        return RawSPDMeasurement(
            spd=SpectralDistribution(data=values, domain=wavelengths),
            spectrometer_id=spectrometer_id,
            exposure=exposure,
        )
