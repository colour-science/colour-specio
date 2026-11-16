"""
Photo Research spectrometer implementation.
"""

# cspell:ignore msec

from __future__ import annotations

import logging
import re
from functools import cached_property
from typing import ClassVar, final

import serial
from colour import SpectralDistribution

from specio.common import RawSPDMeasurement, SpecRadiometer
from specio.common.exceptions import DeviceError

from ._common import MeasurementOutOfRange, PRDeviceBase, PRIncompleteReplyError

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "FLOOR_SOURCE_NOMINAL",
    "PRSpectrometer",
]

_MEASUREMENT_TIMEOUT = 60.0
_DATA_LINE_TIMEOUT = 2.0
_MS_PER_SECOND = 1000.0
_MIN_AVERAGE_SAMPLES = 1
_MAX_AVERAGE_SAMPLES = 99

# Field positions in the D602 verbose setup report, counted after the
# error code (PR-655/670 User Manual, p.148).
_D602_PRIMARY_ACCESSORY_FIELD = 0
_D602_ADDON_FIELDS = (1, 2, 3)
_D602_APERTURE_FIELD = 4
_D602_EXPOSURE_TIME_FIELD = 7
_D602_CYCLES_FIELD = 9

# The lowest luminance each optical setup reports, in cd/m², from the
# PR-655/670 User Manual's "PR-655 Sensitivity Chart" (Table 12). Keyed
# by (primary accessory, aperture) with no add-on fitted; only the rows
# that read unambiguously off the chart are carried. Any other setup
# states no floor rather than a guess.
_NOMINAL_FLOORS: dict[tuple[str, str], float] = {
    ("MS-75", "1 deg"): 3.4,
}

FLOOR_SOURCE_NOMINAL = "nominal: PR-655/670 User Manual, Table 12"

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

        If a line is missing or malformed, the remaining input is drained
        before the error is raised.

        Parameters
        ----------
        points : int
            Number of lines to read.

        Returns
        -------
        tuple[list[float], list[float]]
            Wavelengths in nanometers and the spectral value at each.

        Raises
        ------
        PRIncompleteReplyError
            If fewer lines arrive than expected.
        DeviceError
            If a line is malformed.
        """
        wavelengths: list[float] = []
        values: list[float] = []
        try:
            with self._port_timeout(_DATA_LINE_TIMEOUT):
                for index in range(points):
                    try:
                        line = self._read_response()
                    except PRIncompleteReplyError as error:
                        raise PRIncompleteReplyError(
                            f"D5 returned {index} of {points} spectral lines",
                            error.received,
                        ) from error
                    try:
                        wavelength, value = (float(part) for part in line.split(","))
                    except ValueError as error:
                        raise DeviceError(
                            f"Malformed D5 spectral line: {line!r}"
                        ) from error
                    wavelengths.append(wavelength)
                    values.append(value)
        except DeviceError:
            # The rest of the spectrum may still be arriving. Drain it now,
            # so the caller's next command starts on a quiet line.
            self._drain_input()
            raise
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

    @property
    def floor(self) -> float | None:
        """
        The lowest luminance the current optical setup reports, in cd/m².

        Read from the verbose setup report (D602: primary accessory,
        add-ons, aperture) and looked up in the manual's sensitivity
        chart. The device can return readings below it: it is the
        manufacturer's stated range, not where this unit refuses. Each
        access reads D602 again, because a change of aperture or accessory
        changes the floor.

        Returns
        -------
        float | None
            The stated floor, or None when the setup is not one the chart
            states unambiguously.

        Raises
        ------
        PRCommandError
            If the setup query fails.
        PRIncompleteReplyError
            If the setup report is cut short.
        """
        fields = self._write_cmd("D602").raw_data.split(",")
        if len(fields) <= _D602_APERTURE_FIELD:
            return None
        if any(fields[i].strip() != "None" for i in _D602_ADDON_FIELDS):
            return None
        primary = fields[_D602_PRIMARY_ACCESSORY_FIELD].strip()
        aperture = fields[_D602_APERTURE_FIELD].strip()
        return _NOMINAL_FLOORS.get((primary, aperture))

    @property
    def floor_source(self) -> str | None:
        """Where :attr:`floor` comes from, or None when there is no floor."""
        return FLOOR_SOURCE_NOMINAL if self.floor is not None else None

    def _attach_floor(self, refusal: MeasurementOutOfRange) -> None:
        """
        Record the stated floor on a too-dark refusal.

        The floor is read when the refusal is raised, so it describes the
        setup that refused. If the read fails, the refusal keeps no floor,
        and the caller still sees the refusal rather than the failed read.

        Parameters
        ----------
        refusal : MeasurementOutOfRange
            The too-dark refusal to annotate.
        """
        try:
            floor = self.floor
        except (DeviceError, serial.SerialException) as error:
            logging.getLogger("specio.PR").debug(
                "No floor for the refusal, the setup read failed: %s", error
            )
            return
        refusal.floor = floor
        refusal.floor_source = FLOOR_SOURCE_NOMINAL if floor is not None else None

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
        MeasurementOutOfRange
            If the light is outside the device's range; a too-dark refusal
            carries the floor the device states for its setup.
        PRCommandError
            If the measurement or data retrieval command returns an error.
        DeviceError
            If the spectral data is short or malformed.
        """
        log = logging.getLogger("specio.PR")
        points = self._spectral_points
        spectrometer_id = self.readable_id

        log.debug("Triggering spectral measurement (M0)")
        try:
            self._write_cmd("M0", timeout=_MEASUREMENT_TIMEOUT)
        except MeasurementOutOfRange as refusal:
            if refusal.too_dark:
                self._attach_floor(refusal)
            raise

        # Some firmware may stream the spectrum after the M0 code. The drain
        # before D5 discards that stream, so D5 reads its own header and
        # spectrum either way.
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
