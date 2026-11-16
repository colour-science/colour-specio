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

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research import PRSpectrometer
    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]

# Just past the driver's 5 s default reply timeout.
_JUST_AFTER_TIMEOUT = 5.01
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

    def test_spectrum_streamed_after_m0(self, open_pr: OpenPR) -> None:
        """A spectrum that streams after M0 is not read as the D5 reply."""
        values = np.linspace(1.0, 2.0, _PR655_POINTS)
        stale = d5_reply(np.zeros(_PR655_POINTS))
        pr, _ = open_pr(
            {
                "M0": Reply((0.0, b"00000\r\n"), (_TRAIL, stale)),
                "D5": Reply((_LATENCY, d5_reply(values))),
            }
        )

        spd = pr.measure().spd

        np.testing.assert_allclose(spd.values, values, rtol=1e-3)

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
