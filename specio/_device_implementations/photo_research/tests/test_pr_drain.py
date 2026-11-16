"""
Input drain before each command on the Photo Research driver.

Bytes that arrive after a reply has been read, or after its read timed out,
belong to no command. The driver discards them before it sends the next
command, so each command reads its own reply.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pytest

from specio._device_implementations.photo_research import (
    PRIncompleteReplyError,
    _common,
)
from specio._device_implementations.photo_research.tests.fakes import (
    Reply,
    d5_reply,
)
from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research import PRSpectrometer
    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]

# Just past the driver's 5 s default reply timeout.
_JUST_AFTER_TIMEOUT = 5.01
# Just past the driver's 2 s timeout for each spectral data line.
_JUST_AFTER_LINE_TIMEOUT = 2.01
# A device's processing time before it answers.
_LATENCY = 0.02
# Delay before stale bytes trail a reply, shorter than the quiet gap.
_TRAIL = 0.01
_SERIAL = "12345678"
_STALE_LINE = b"424,1.999e-04\r\n"
_PR655_POINTS = 101
_CHATTER_PERIOD = 0.01
_CHATTER_COUNT = 2000


class TestDrainBeforeWrite:
    """Each command starts on a quiet line."""

    def test_command_after_cut_reply(self, open_pr: OpenPR) -> None:
        """The rest of a cut reply is not read as the next reply."""
        pr, _ = open_pr(
            {
                "D110": Reply(
                    (0.0, f"00000,{_SERIAL[:4]}".encode()),
                    (_JUST_AFTER_TIMEOUT, f"{_SERIAL[4:]}\r\n".encode()),
                ),
                "D111": Reply((_LATENCY, b"00000,PR-655\r\n")),
            }
        )

        with pytest.raises(PRIncompleteReplyError):
            _ = pr.serial_number
        assert pr.model == "PR-655"

    def test_trailing_line_is_discarded(self, open_pr: OpenPR) -> None:
        """A stale line after a complete reply is not the next reply."""
        pr, _ = open_pr(
            {
                "D110": Reply(
                    (0.0, f"00000,{_SERIAL}\r\n".encode()), (_TRAIL, _STALE_LINE)
                ),
                "D111": Reply((_LATENCY, b"00000,PR-655\r\n")),
            }
        )

        assert pr.serial_number == _SERIAL
        assert pr.model == "PR-655"

    def test_discarded_bytes_are_logged(
        self, open_pr: OpenPR, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The drain logs what it discards at debug level."""
        pr, port = open_pr()
        port.emit(_STALE_LINE, after=_TRAIL)

        with caplog.at_level(logging.DEBUG, logger="specio.PR"):
            assert pr.model == "PR-655"

        assert any(
            record.levelno == logging.DEBUG
            and _STALE_LINE.decode().strip() in record.getMessage()
            for record in caplog.records
        )

    def test_line_trailing_the_spectrum(self, open_pr: OpenPR) -> None:
        """A stale line after the M5 spectrum is not read as the D13 reply."""
        values = np.linspace(1.0, 2.0, _PR655_POINTS)
        pr, _ = open_pr(
            {
                "M5": Reply((0.0, d5_reply(values)), (_TRAIL, _STALE_LINE)),
                "D13": Reply((_LATENCY, b"00000,Normal,250 msec\r\n")),
            }
        )

        measurement = pr.measure()

        np.testing.assert_allclose(measurement.spd.values, values, rtol=1e-3)
        assert measurement.exposure == pytest.approx(0.25)

    def test_drain_is_bounded(self, open_pr: OpenPR) -> None:
        """A port that never falls quiet stops the drain at its time limit."""
        pr, port = open_pr()
        for index in range(_CHATTER_COUNT):
            port.emit(b"x", after=index * _CHATTER_PERIOD)
        start = port.clock()

        pr._drain_input()

        elapsed = port.clock() - start
        assert elapsed >= _common._DRAIN_MAX_TIME
        assert elapsed <= _common._DRAIN_MAX_TIME + _common._DRAIN_QUIET_GAP


class TestSpectrumRecovery:
    """A failed spectrum read leaves the line clean before it raises."""

    @staticmethod
    def _assert_line_is_clean(port: FakePRPort) -> None:
        """Nothing is left to read, now or within the port timeout."""
        assert port.read_until(b"\r\n") == b""

    def test_malformed_line(self, open_pr: OpenPR) -> None:
        """The lines after a malformed one are drained before the error."""
        lines = d5_reply(np.ones(_PR655_POINTS)).splitlines(keepends=True)
        lines[10] = b"garbage\r\n"
        pr, port = open_pr({"M5": b"".join(lines)})

        with pytest.raises(DeviceError, match="garbage"):
            pr.measure()

        assert "D13" not in port.commands
        self._assert_line_is_clean(port)

    def test_short_read_then_command(self, open_pr: OpenPR) -> None:
        """Lines that arrive after the line timeout are drained, not read."""
        lines = d5_reply(np.ones(_PR655_POINTS)).splitlines(keepends=True)
        received = 1 + _PR655_POINTS // 2
        late = [
            (_JUST_AFTER_LINE_TIMEOUT + index * _TRAIL, line)
            for index, line in enumerate(lines[received:])
        ]
        pr, port = open_pr(
            {
                "M5": Reply((0.0, b"".join(lines[:received])), *late),
                "D110": f"00000,{_SERIAL}\r\n".encode(),
            }
        )

        with pytest.raises(PRIncompleteReplyError, match="spectral lines"):
            pr.measure()

        self._assert_line_is_clean(port)
        assert pr.serial_number == _SERIAL
