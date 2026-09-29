"""
Measurement, exposure and averaging on the Photo Research driver.

Reply formats follow the PR-655/670 User Manual: D5 (p.143), D13 and D111
(p.145), D120 (p.147), D602 (p.148), SE (p.136) and SN (p.137).
"""

# cspell:ignore keepends msec

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from specio._device_implementations.photo_research import (
    PRCommandError,
    PRResponseCode,
    PRSpectrometer,
)
from specio._device_implementations.photo_research.tests.fakes import (
    PR655_SHAPE,
    d5_reply,
)
from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]

PR670_SHAPE = (380, 780, 2)
PR670_POINTS = 201
PR655_POINTS = 101


def _d120(points: int, shape: tuple[int, int, int]) -> bytes:
    """Build a D120 hardware configuration reply."""
    start, end, step = shape
    return f"00000,{points},0.00,{start},{end},{step},256,7,247\r\n".encode()


def _d602(mode: str, exposure: str, cycles: str) -> bytes:
    """Build a verbose D602 setup report."""
    return (
        f"00000,MS-75,None,None,None,1 deg,English,{mode},{exposure},Normal,"
        f"{cycles},2 deg,No Smart Dark,No Sync,Standard Sensitivity,"
        "60.00 Hertz\r\n"
    ).encode()


class TestSpectrum:
    """D5 parsing: header first, then one wavelength line per sample."""

    def test_header_is_not_parsed_as_data(self, open_pr: OpenPR) -> None:
        """Each value lands on its own wavelength, 380 nm through 780 nm."""
        values = np.linspace(1.0, 2.0, PR655_POINTS)
        pr, _ = open_pr({"D5": d5_reply(values)})

        spd = pr.measure().spd

        np.testing.assert_allclose(spd.values, values, rtol=1e-3)
        np.testing.assert_array_equal(
            spd.wavelengths, np.arange(380, 781, 4, dtype=float)
        )

    def test_domain_comes_from_the_reply(self, open_pr: OpenPR) -> None:
        """A 2 nm reply yields a 2 nm domain, whatever the model table says."""
        values = np.linspace(1.0, 2.0, PR670_POINTS)
        pr, _ = open_pr(
            {
                "D111": b"00000,PR-670\r\n",
                "D120": _d120(PR670_POINTS, PR670_SHAPE),
                "D5": d5_reply(values, shape=PR670_SHAPE),
            }
        )

        spd = pr.measure().spd

        assert spd.shape.interval == PR670_SHAPE[2]
        assert len(spd.values) == PR670_POINTS

    def test_unknown_model_uses_the_reply(self, open_pr: OpenPR) -> None:
        """An unlisted model still measures on the domain the device reports."""
        pr, _ = open_pr({"D111": b"00000,PR-999\r\n"})

        spd = pr.measure().spd

        assert spd.shape.start == PR655_SHAPE[0]
        assert spd.shape.end == PR655_SHAPE[1]

    def test_short_read_raises_device_error(self, open_pr: OpenPR) -> None:
        """Fewer lines than D120 announces is a driver error."""
        received = 50
        lines = d5_reply(np.ones(PR655_POINTS)).splitlines(keepends=True)
        header_and_received = lines[: 1 + received]
        pr, _ = open_pr({"D5": b"".join(header_and_received)})

        with pytest.raises(DeviceError, match=f"{received} of {PR655_POINTS}"):
            pr.measure()

    def test_malformed_line_raises_device_error(self, open_pr: OpenPR) -> None:
        """A data line that is not ``wl,value`` is a driver error."""
        lines = d5_reply(np.ones(PR655_POINTS)).splitlines(keepends=True)
        lines[10] = b"garbage\r\n"
        pr, _ = open_pr({"D5": b"".join(lines)})

        with pytest.raises(DeviceError, match="garbage"):
            pr.measure()

    def test_header_error_code_raises(self, open_pr: OpenPR) -> None:
        """The D5 header's code is an error code."""
        pr, _ = open_pr({"D5": d5_reply(np.ones(PR655_POINTS), code="-0008")})

        with pytest.raises(PRCommandError) as info:
            pr.measure()
        assert info.value.response.code is PRResponseCode.WEAK_LIGHT

    def test_commands_go_through_write_cmd(
        self, open_pr: OpenPR, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M0, D5 and D13 use the shared command path."""
        pr, _ = open_pr()
        sent: list[str] = []
        write_cmd = pr._write_cmd

        def spy(command: str, *args: object, **kwargs: object) -> object:
            sent.append(command)
            return write_cmd(command, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(pr, "_write_cmd", spy)
        pr.measure()

        assert {"M0", "D5", "D13"} <= set(sent)


class TestTimeouts:
    """Temporary timeouts are restored, on success and on error."""

    def test_restored_after_measurement(self, open_pr: OpenPR) -> None:
        """A measurement leaves the port timeout as it found it."""
        pr, port = open_pr()
        original = port.timeout

        pr.measure()

        assert port.timeout == original

    @pytest.mark.parametrize(
        "replies",
        [
            {"M0": b"-0008\r\n"},
            {"D5": b"00000,0,5.560e+02,1.827e-01,5.147e+01\r\n380,1.0\r\n"},
        ],
    )
    def test_restored_after_error(
        self, open_pr: OpenPR, replies: dict[str, bytes]
    ) -> None:
        """A failed measurement leaves the port timeout as it found it."""
        pr, port = open_pr(replies)
        original = port.timeout

        with pytest.raises(DeviceError):
            pr.measure()

        assert port.timeout == original


class TestExposure:
    """Exposure is float seconds; ADAPTIVE_EXPOSURE marks adaptive mode."""

    def test_measurement_reports_d13_exposure(self, open_pr: OpenPR) -> None:
        """The measurement carries the last exposure from D13, in seconds."""
        pr, _ = open_pr({"D13": b"00000,Fast,16500 msec\r\n"})

        assert pr.measure().exposure == pytest.approx(16.5)

    def test_malformed_d13_raises(self, open_pr: OpenPR) -> None:
        """An unreadable D13 exposure is a driver error."""
        pr, _ = open_pr({"D13": b"00000,Normal\r\n"})

        with pytest.raises(DeviceError):
            pr.measure()

    def test_adaptive_setting_reads_as_adaptive(self, open_pr: OpenPR) -> None:
        """D602 reports 0 msec in adaptive mode (p.148)."""
        pr, _ = open_pr({"D602": _d602("Adaptive", "0 msec", "1 cycles")})

        assert pr.exposure == PRSpectrometer.ADAPTIVE_EXPOSURE

    def test_fixed_setting_reads_in_seconds(self, open_pr: OpenPR) -> None:
        """A fixed exposure reads back in seconds."""
        pr, _ = open_pr({"D602": _d602("Fixed", "100 msec", "1 cycles")})

        assert pr.exposure == pytest.approx(0.1)

    @pytest.mark.parametrize(
        ("seconds", "command"),
        [(0.1, "SE100"), (6.0, "SE6000"), (PRSpectrometer.ADAPTIVE_EXPOSURE, "SE0")],
    )
    def test_setter_sends_milliseconds(
        self, open_pr: OpenPR, seconds: float, command: str
    ) -> None:
        """SE takes milliseconds, and SE0 selects adaptive mode (p.136)."""
        pr, port = open_pr()

        pr.exposure = seconds

        assert port.commands[-1] == command

    def test_setter_rejects_negative(self, open_pr: OpenPR) -> None:
        """A negative exposure is refused before reaching the device."""
        pr, port = open_pr()

        with pytest.raises(ValueError, match="exposure"):
            pr.exposure = -0.1
        assert not any(c.startswith("SE") for c in port.commands)

    def test_out_of_range_raises_device_code(self, open_pr: OpenPR) -> None:
        """The device's range check (-1010) surfaces as PRCommandError."""
        pr, _ = open_pr({"SE1": b"-1010\r\n"})

        with pytest.raises(PRCommandError) as info:
            pr.exposure = 0.001
        assert info.value.response.code is PRResponseCode.INVALID_EXPOSURE_VALUE


class TestAverageSamples:
    """Cycles to average: D602 reads, SN writes, 1 to 99 (p.137)."""

    def test_getter_reads_d602(self, open_pr: OpenPR) -> None:
        """The cycle count comes from the D602 report."""
        pr, _ = open_pr({"D602": _d602("Adaptive", "0 msec", "3 cycles")})

        assert pr.average_samples == 3

    @pytest.mark.parametrize(
        ("count", "command"), [(0, "SN1"), (5, "SN5"), (150, "SN99")]
    )
    def test_setter_clamps(self, open_pr: OpenPR, count: int, command: str) -> None:
        """The count is clamped to the manual's 1 to 99 range."""
        pr, port = open_pr()

        pr.average_samples = count

        assert port.commands[-1] == command
