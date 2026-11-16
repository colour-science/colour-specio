"""
Timed delivery in the fake PR-655 port.

The fake keeps a virtual clock. A read that finds no bytes waits, on that
clock, for at most the port timeout, so tests of late, cut and trailing
replies run instantly and the same way every time.
"""

from __future__ import annotations

import pytest

from specio._device_implementations.photo_research.tests.fakes import (
    FakePRPort,
    Reply,
)

_TIMEOUT = 1.0


def _remote_port(replies: dict[str, bytes | Reply]) -> FakePRPort:
    """Return a fake port already in remote mode, with its input empty."""
    port = FakePRPort(replies)
    port.timeout = _TIMEOUT
    port.write(b"PHOTO")
    port.reset_input_buffer()
    return port


class TestVirtualClock:
    """An empty read waits on the virtual clock, never in real time."""

    def test_empty_read_waits_one_timeout(self) -> None:
        """A read with nothing to deliver returns empty after the timeout."""
        port = _remote_port({})

        assert port.read(1) == b""
        assert port.clock() == pytest.approx(_TIMEOUT)

    def test_untimed_bytes_arrive_at_once(self) -> None:
        """A plain bytes reply is readable as soon as the command is sent."""
        port = _remote_port({})
        port.write(b"D111\r")

        assert port.read_until(b"\r\n") == b"00000,PR-655\r\n"
        assert port.clock() == 0.0


class TestTimedReplies:
    """A Reply arrives in parts, each at its own offset after the command."""

    def test_delayed_reply_within_timeout(self) -> None:
        """A read waits for a reply that arrives before the timeout."""
        port = _remote_port({"D111": Reply((0.5, b"00000,PR-655\r\n"))})
        port.write(b"D111\r")

        assert port.in_waiting == 0
        assert port.read_until(b"\r\n") == b"00000,PR-655\r\n"
        assert port.clock() == pytest.approx(0.5)

    def test_delayed_reply_beyond_timeout(self) -> None:
        """A reply later than the timeout is still queued for later reads."""
        port = _remote_port({"D111": Reply((1.5, b"00000,PR-655\r\n"))})
        port.write(b"D111\r")

        assert port.read_until(b"\r\n") == b""
        assert port.read_until(b"\r\n") == b"00000,PR-655\r\n"

    def test_split_reply(self) -> None:
        """A reply cut by a pause longer than the timeout reads in two parts."""
        port = _remote_port({"D110": Reply((0.0, b"00000,12"), (1.5, b"345678\r\n"))})
        port.write(b"D110\r")

        assert port.read_until(b"\r\n") == b"00000,12"
        assert port.read_until(b"\r\n") == b"345678\r\n"

    def test_trailing_bytes(self) -> None:
        """Stale lines after a reply stay pending until they arrive."""
        port = _remote_port(
            {"D110": Reply((0.0, b"00000,12345678\r\n"), (0.2, b"424,1.0\r\n"))}
        )
        port.write(b"D110\r")

        assert port.read_until(b"\r\n") == b"00000,12345678\r\n"
        port.reset_input_buffer()
        assert port.read_until(b"\r\n") == b"424,1.0\r\n"

    def test_unsolicited_bytes(self) -> None:
        """emit() schedules bytes that no command asked for."""
        port = _remote_port({})
        port.emit(b"noise\r\n", after=0.25)

        assert port.read_until(b"\r\n") == b"noise\r\n"
        assert port.clock() == pytest.approx(0.25)
