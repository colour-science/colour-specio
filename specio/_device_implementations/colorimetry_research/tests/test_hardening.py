"""The CR link survives what a genuinely black display does to it.

Every case here was observed on a bench rig measuring an LED wall in a
dark room: the panel emitted less than the colorimeter can integrate, and
the device answered three different ways. Two of them used to escape the
instrument layer as `IndexError` and `ValueError` -- exceptions that say
nothing about instruments and give a caller nothing to catch.
"""

from __future__ import annotations

import pytest

from specio._device_implementations.colorimetry_research._common import (
    _MAX_AVERAGE_SAMPLES,
    CRDeviceBase,
    IncompleteResponse,
    UnexpectedResponse,
)


class _Port:
    """Enough of a serial port for the parser.

    `_parse_response` reads follow-on argument lines only when the port
    says bytes are waiting, so a port with nothing waiting keeps a
    single-line reply single-line.
    """

    in_waiting = 0

    def readline(self) -> bytes:  # pragma: no cover - not reached here
        return b""


class _Device(CRDeviceBase):
    """A CRDeviceBase with the serial port replaced by a script of replies."""

    def __init__(self, replies: list[bytes]) -> None:
        self._port = _Port()
        self._replies = list(replies)
        self.sent: list[str] = []
        self.resyncs = 0
        self._CRDeviceBase__last_cmd_time = 0.0
        self._CRDeviceBase__last_command = ""
        self._CRDeviceBase__average_samples = None

    # The two hooks the base class needs, stubbed.
    def _write_cmd(self, command: str):
        self.sent.append(command)
        raw = self._replies.pop(0)
        return self._parse_response(raw)

    def resync(self) -> None:
        self.resyncs += 1
        self._CRDeviceBase__average_samples = None

    def _raw_measure(self):  # pragma: no cover - unused here
        raise NotImplementedError

    @property
    def instrument_type(self):  # pragma: no cover - unused here
        raise NotImplementedError


def _ok(value: bytes) -> bytes:
    """A well-formed CR reply: type:code:description:argument."""
    return b"OK:0:No errors:" + value


class TestShortReply:
    def test_a_truncated_line_raises_by_name(self) -> None:
        """A reply cut off mid-line used to index past its own end."""
        d = _Device([b"OK:0"])

        with pytest.raises(IncompleteResponse):
            d._write_cmd("RS ExposureX")

    def test_an_empty_line_raises_by_name(self) -> None:
        d = _Device([b""])

        with pytest.raises(IncompleteResponse):
            d._write_cmd("RS ExposureX")


class TestDesynchronisedLink:
    def test_a_stale_reply_is_not_cast_into_a_number(self) -> None:
        """The failure this replaces: a link one reply behind answered
        `RS ExposureX` with a previous command's status line, and
        `int('No errors')` aborted a measurement that had not started."""
        d = _Device([b"OK:0:No errors:No errors"])

        with pytest.raises(UnexpectedResponse) as excinfo:
            _ = d.average_samples

        assert "RS ExposureX" in str(excinfo.value)

    def test_the_error_names_what_came_back(self) -> None:
        d = _Device([b"OK:0:No errors:No errors"])

        with pytest.raises(UnexpectedResponse, match="one reply behind"):
            _ = d.average_samples


class TestExposureMultiplier:
    def test_each_read_asks_the_device(self) -> None:
        """The setting can change on the instrument, so a read reports
        what the device holds now rather than what this driver last saw."""
        d = _Device([_ok(b"16"), _ok(b"4")])

        assert d.average_samples == 16
        assert d.average_samples == 4
        assert d.sent == ["RS ExposureX", "RS ExposureX"]

    def test_the_read_window_is_sized_without_a_round_trip(self) -> None:
        """The measure path sizes its timeout from the last value read or
        written, so a measurement does not carry an extra serial exchange,
        and a failure point, before it starts."""
        d = _Device([_ok(b"16"), _ok(b"")])

        assert d.average_samples == 16
        assert d._samples_for_timeout() == 16
        d.average_samples = 8
        assert d._samples_for_timeout() == 8
        assert d.sent == ["RS ExposureX", "SM ExposureX 8"]

    def test_an_unknown_multiplier_is_read_once_for_the_window(self) -> None:
        d = _Device([_ok(b"3")])

        assert d._samples_for_timeout() == 3
        assert d._samples_for_timeout() == 3
        assert d.sent == ["RS ExposureX"]

    def test_a_link_that_cannot_say_gets_the_widest_window(self) -> None:
        """Sizing the window must not fail the measurement it sizes."""
        d = _Device([b"OK:0:No errors:No errors"])

        assert d._samples_for_timeout() == _MAX_AVERAGE_SAMPLES

    def test_the_setter_clamps_to_the_command_set(self) -> None:
        d = _Device([_ok(b""), _ok(b"")])

        d.average_samples = 9999
        assert d._samples_for_timeout() == _MAX_AVERAGE_SAMPLES
        assert d.sent[-1] == f"SM ExposureX {_MAX_AVERAGE_SAMPLES}"

        d.average_samples = 0
        assert d._samples_for_timeout() == 1
        assert d.sent[-1] == "SM ExposureX 1"

    def test_resync_forgets_the_multiplier(self) -> None:
        """After a resynchronisation the device may not agree with what
        was last seen, so the next window is sized from a fresh read."""
        d = _Device([_ok(b"4"), _ok(b"6")])

        assert d._samples_for_timeout() == 4
        d.resync()
        assert d._samples_for_timeout() == 6
        assert d.sent == ["RS ExposureX", "RS ExposureX"]
