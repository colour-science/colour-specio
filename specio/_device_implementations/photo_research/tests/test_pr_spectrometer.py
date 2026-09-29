"""
Hardware integration tests for the Photo Research PR spectrometer.

Every test skips unless discovery finds a connected Photo Research device.
Discovery never opens a port that identifies as another vendor's device.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import serial

from specio._device_implementations.photo_research import (
    PRCommandError,
    PRResponseCode,
)
from specio.common import SPDMeasurement
from specio.spectrometers import PRSpectrometer

if TYPE_CHECKING:
    from collections.abc import Iterator

# Below the PR-655 (3 ms) and PR-670 (6 ms) minimum exposure, per the
# PR-655/670 User Manual, p.136.
_TOO_SHORT_EXPOSURE = 0.001
_FIXED_EXPOSURE = 0.1
_START_NM = 380
_END_NM = 780


@pytest.fixture(scope="module")
def pr() -> Iterator[PRSpectrometer]:
    """Discover a connected PR spectrometer, or skip the entire module."""
    try:
        device = PRSpectrometer.discover()
    except serial.SerialException:
        pytest.skip("No PR spectrometer connected")
    with device:
        yield device


class TestIdentity:
    """Verify basic device identity properties."""

    def test_model_starts_with_pr(self, pr: PRSpectrometer) -> None:
        """Model string should start with 'PR-'."""
        assert pr.model.startswith("PR-")

    def test_serial_number_non_empty(self, pr: PRSpectrometer) -> None:
        """Serial number must be a non-empty string."""
        assert pr.serial_number
        assert pr.serial_number != "unknown"


class TestExposure:
    """Verify the exposure (integration time) setter and getter."""

    def test_adaptive_mode(self, pr: PRSpectrometer) -> None:
        """SE0 selects adaptive exposure, which reads back as adaptive."""
        pr.exposure = PRSpectrometer.ADAPTIVE_EXPOSURE
        assert pr.exposure == PRSpectrometer.ADAPTIVE_EXPOSURE

    def test_fixed_exposure(self, pr: PRSpectrometer) -> None:
        """A fixed exposure reads back in seconds."""
        pr.exposure = _FIXED_EXPOSURE
        assert pr.exposure == pytest.approx(_FIXED_EXPOSURE)

    def test_out_of_range_is_rejected(self, pr: PRSpectrometer) -> None:
        """The device rejects an exposure below its minimum."""
        with pytest.raises(PRCommandError) as info:
            pr.exposure = _TOO_SHORT_EXPOSURE
        assert info.value.response.code is PRResponseCode.INVALID_EXPOSURE_VALUE

    def test_restore_adaptive(self, pr: PRSpectrometer) -> None:
        """Restore adaptive mode after exposure tests."""
        pr.exposure = PRSpectrometer.ADAPTIVE_EXPOSURE
        assert pr.exposure == PRSpectrometer.ADAPTIVE_EXPOSURE


class TestAverageSamples:
    """Verify the average-samples (SN) setter and getter."""

    def test_set_average(self, pr: PRSpectrometer) -> None:
        """SN3 should report 3 cycles."""
        pr.average_samples = 3
        assert pr.average_samples == 3

    def test_clamp_to_one(self, pr: PRSpectrometer) -> None:
        """A count of 0 clamps to 1 cycle."""
        pr.average_samples = 0
        assert pr.average_samples == 1

    def test_restore_default(self, pr: PRSpectrometer) -> None:
        """SN1 should restore the default single-cycle averaging."""
        pr.average_samples = 1
        assert pr.average_samples == 1


class TestMeasure:
    """Verify that a measurement returns a complete, correctly placed SPD."""

    def test_single_measurement(self, pr: PRSpectrometer) -> None:
        """A measurement spans 380-780 nm and reports its exposure."""
        pr.exposure = PRSpectrometer.ADAPTIVE_EXPOSURE
        pr.average_samples = 1

        measurement = pr.measure()

        assert isinstance(measurement, SPDMeasurement)
        assert measurement.spd.shape.start == _START_NM
        assert measurement.spd.shape.end == _END_NM
        assert measurement.exposure > 0
        assert measurement.XYZ.shape == (3,)
