"""
Out-of-range measurements, the stated floor, and recorded bench replies.

Weak light and overload are results the device stands behind, not failed
exchanges, so they raise ``MeasurementOutOfRange``; a too-dark refusal
carries the floor the device states for its optical setup (PR-655/670
User Manual, Table 12) so a caller can record it as a bound below that
floor.
"""

# cspell:ignore msec

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specio._device_implementations.photo_research import (
    FLOOR_SOURCE_NOMINAL,
    OUT_OF_RANGE_CODES,
    MeasurementOutOfRange,
    PRCommandError,
    PRResponseCode,
)
from specio._device_implementations.photo_research.tests.fakes import Reply

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research import PRSpectrometer
    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
        ScriptedReply,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]

# Replies recorded from a PR-655 (software 2.51) reading a near-neutral
# source at about 1195 cd/m². The serial number in D110 is invented. M5 and
# D5 share one reply format.
RECORDED = Path(__file__).parent / "data"


def _setup(
    primary: str = "MS-75", addon: str = "None", aperture: str = "1 deg"
) -> bytes:
    return (
        f"00000,{primary},{addon},None,None,{aperture},English,Adaptive,0 msec,"
        "Normal,1 cycles,2 deg,No Smart Dark,No Sync,Standard Sensitivity,"
        "60.00 Hertz\r\n"
    ).encode()


class TestOutOfRangeIsItsOwnType:
    def test_the_codes_that_report_the_light(self) -> None:
        assert {
            PRResponseCode.WEAK_LIGHT,
            PRResponseCode.LIGHT_OVERLOAD,
        } == OUT_OF_RANGE_CODES

    def test_it_is_still_a_command_error(self) -> None:
        """Callers that only knew PRCommandError keep working."""
        assert issubclass(MeasurementOutOfRange, PRCommandError)


class TestARefusalCarriesItsBound:
    def test_weak_light_carries_the_stated_floor(self, open_pr: OpenPR) -> None:
        pr, _ = open_pr({"M0": b"-0008\r\n"})

        with pytest.raises(MeasurementOutOfRange) as caught:
            pr.measure()

        assert caught.value.too_dark
        assert caught.value.floor == pytest.approx(3.4)
        assert caught.value.floor_source == FLOOR_SOURCE_NOMINAL

    def test_overload_carries_no_floor(self, open_pr: OpenPR) -> None:
        pr, _ = open_pr({"M0": b"-0002\r\n"})

        with pytest.raises(MeasurementOutOfRange) as caught:
            pr.measure()

        assert not caught.value.too_dark
        assert caught.value.floor is None

    def test_a_refusal_is_not_retried(self, open_pr: OpenPR) -> None:
        pr, port = open_pr({"M0": b"-0008\r\n"})

        with pytest.raises(MeasurementOutOfRange):
            pr.measure()

        assert port.commands.count("M0") == 1

    def test_any_other_measurement_error_is_a_command_error(
        self, open_pr: OpenPR
    ) -> None:
        pr, _ = open_pr({"M0": b"-0012\r\n"})

        with pytest.raises(PRCommandError) as caught:
            pr.measure()

        assert not isinstance(caught.value, MeasurementOutOfRange)


class TestStatedFloor:
    def test_the_standard_lens_at_one_degree(self, open_pr: OpenPR) -> None:
        pr, _ = open_pr()

        assert pr.floor == pytest.approx(3.4)
        assert pr.floor_source == FLOOR_SOURCE_NOMINAL

    @pytest.mark.parametrize(
        "setup",
        [
            _setup(addon="ND-2"),
            _setup(primary="SL-1X"),
            _setup(aperture="1/2 deg"),
        ],
        ids=["add-on", "other-lens", "other-aperture"],
    )
    def test_a_setup_the_chart_does_not_state_has_no_floor(
        self, open_pr: OpenPR, setup: bytes
    ) -> None:
        pr, _ = open_pr({"D602": setup})

        assert pr.floor is None
        assert pr.floor_source is None

    def test_an_unreadable_setup_is_an_error(self, open_pr: OpenPR) -> None:
        """A failed D602 read is not a setup without a floor."""
        pr, _ = open_pr({"D602": b"-1000\r\n"})

        with pytest.raises(PRCommandError):
            _ = pr.floor

    def test_the_floor_is_read_on_every_access(self, open_pr: OpenPR) -> None:
        """A changed aperture or accessory changes the floor."""
        pr, port = open_pr({"D602": [_setup(), _setup(aperture="1/2 deg")]})

        assert pr.floor == pytest.approx(3.4)
        assert pr.floor is None
        assert port.commands.count("D602") == 2


class TestARefusalWithAnUnreadableFloor:
    """A failed D602 read leaves the refusal intact, without a floor."""

    @pytest.mark.parametrize(
        "setup",
        [b"-1000\r\n", Reply((0.0, b"00000,MS-75,None,None"))],
        ids=["error-code", "cut-reply"],
    )
    def test_the_refusal_is_raised_without_a_floor(
        self, open_pr: OpenPR, setup: ScriptedReply
    ) -> None:
        pr, _ = open_pr({"M0": b"-0008\r\n", "D602": setup})

        with pytest.raises(MeasurementOutOfRange) as caught:
            pr.measure()

        assert caught.value.response.code is PRResponseCode.WEAK_LIGHT
        assert caught.value.floor is None
        assert caught.value.floor_source is None

    def test_each_refusal_reads_the_current_setup(self, open_pr: OpenPR) -> None:
        pr, _ = open_pr(
            {"M0": b"-0008\r\n", "D602": [_setup(), _setup(aperture="1/2 deg")]}
        )

        with pytest.raises(MeasurementOutOfRange) as first:
            pr.measure()
        with pytest.raises(MeasurementOutOfRange) as second:
            pr.measure()

        assert first.value.floor == pytest.approx(3.4)
        assert second.value.floor is None


class TestRecordedDevice:
    """Replies captured from a real PR-655, played back."""

    @pytest.fixture
    def recorded(self, open_pr: OpenPR) -> PRSpectrometer:
        replies = {
            "D5": (RECORDED / "M5.bin").read_bytes(),
            "D13": (RECORDED / "D13.bin").read_bytes(),
            "D110": (RECORDED / "D110.bin").read_bytes(),
            "D111": (RECORDED / "D111.bin").read_bytes(),
        }
        pr, _ = open_pr(replies)
        return pr

    def test_identity(self, recorded: PRSpectrometer) -> None:
        assert recorded.readable_id == "PR655 - 10000002"

    def test_the_spectrum_reproduces_the_device_s_own_tristimulus(
        self, recorded: PRSpectrometer
    ) -> None:
        """XYZ integrated from the spectrum matches the device's D2."""
        d2 = (RECORDED / "D2.bin").read_bytes().decode().strip().split(",")
        expected = [float(v) for v in d2[2:]]

        m = recorded.measure()

        assert m.spd.shape.start == 380
        assert m.spd.shape.end == 780
        assert m.spd.shape.interval == 4
        assert list(m.XYZ) == pytest.approx(expected, rel=2e-3)
        assert m.exposure == pytest.approx(0.067)
