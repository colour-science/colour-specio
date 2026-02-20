"""Hardware integration tests for the Photo Research PR spectrometer."""

import pytest
import serial

from specio.common import SPDMeasurement
from specio.spectrometers import PRSpectrometer


@pytest.fixture(scope="session")
def pr() -> PRSpectrometer:
    """Discover a connected PR spectrometer or skip the entire module."""
    try:
        return PRSpectrometer.discover()
    except serial.SerialException:
        pytest.skip("No PR spectrometer connected")


# -- Identity ----------------------------------------------------------------


class TestIdentity:
    """Verify basic device identity properties."""

    def test_model_starts_with_pr(self, pr: PRSpectrometer) -> None:
        """Model string should start with 'PR-'."""
        assert pr.model.startswith("PR-")

    def test_serial_number_non_empty(self, pr: PRSpectrometer) -> None:
        """Serial number must be a non-empty string."""
        assert pr.serial_number
        assert pr.serial_number != "unknown"


# -- Exposure -----------------------------------------------------------------


class TestExposure:
    """Verify the exposure (integration time) setter and getter."""

    def test_adaptive_mode(self, pr: PRSpectrometer) -> None:
        """SE0 should set adaptive exposure mode."""
        pr.exposure = 0
        assert pr.exposure == "Adaptive"

    def test_fixed_exposure(self, pr: PRSpectrometer) -> None:
        """SE100 should report '100 ms'."""
        pr.exposure = 100
        assert pr.exposure == "100 ms"

    def test_clamp_to_minimum(self, pr: PRSpectrometer) -> None:
        """SE1 should clamp to the model's minimum exposure time."""
        pr.exposure = 1
        value = pr.exposure
        # PR-655 min is 3 ms, PR-670 min is 6 ms — either way, not '1 ms'
        assert value != "1 ms"
        assert "ms" in value

    def test_restore_adaptive(self, pr: PRSpectrometer) -> None:
        """Restore adaptive mode after exposure tests."""
        pr.exposure = 0
        assert pr.exposure == "Adaptive"


# -- Averaging samples --------------------------------------------------------


class TestAveragingSamples:
    """Verify the averaging-samples (SN) setter and getter."""

    def test_set_averaging(self, pr: PRSpectrometer) -> None:
        """SN3 should report 3 cycles."""
        pr.averaging_samples = 3
        assert pr.averaging_samples == 3

    def test_clamp_to_one(self, pr: PRSpectrometer) -> None:
        """SN0 should clamp to 1 cycle."""
        pr.averaging_samples = 0
        assert pr.averaging_samples == 1

    def test_restore_default(self, pr: PRSpectrometer) -> None:
        """SN1 should restore the default single-cycle averaging."""
        pr.averaging_samples = 1
        assert pr.averaging_samples == 1


# -- Measure ------------------------------------------------------------------


class TestMeasure:
    """Verify that a measurement can be taken and returns valid data."""

    def test_single_measurement(self, pr: PRSpectrometer) -> None:
        """A single measurement should return a valid SPDMeasurement."""
        # Ensure adaptive mode and single averaging for fastest measurement
        pr.exposure = 0
        pr.averaging_samples = 1

        measurement = pr.measure()

        assert isinstance(measurement, SPDMeasurement)
        assert measurement.spd is not None
        assert len(measurement.spd.values) > 0
        assert measurement.XYZ is not None
        assert measurement.XYZ.shape == (3,)
