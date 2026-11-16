"""
Remote-mode entry and exit on the Photo Research driver.

The PR-655/670 User Manual sends ``PHOTO`` as five single characters with
no terminator (p.129), and ``Q`` exits remote mode, also with no terminator
(p.132). Psychtoolbox's PR655init.m and PR670close.m send the same bytes.
"""

# cspell:ignore psychtoolbox

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import serial

from specio._device_implementations.photo_research import PRSpectrometer, _common
from specio._device_implementations.photo_research.tests.conftest import (
    FAKE_PORT_NAME,
)
from specio._device_implementations.photo_research.tests.fakes import (
    FakePRPort,
    Reply,
)
from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Callable

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]


class TestEnterRemoteMode:
    """The PHOTO handshake."""

    def test_sends_photo_without_terminator(self, open_pr: OpenPR) -> None:
        """Opening the driver writes exactly the five bytes PHOTO."""
        _, port = open_pr()

        assert bytes(port.written) == b"PHOTO"
        assert port.remote

    @pytest.mark.parametrize(
        ("handshake", "replies"),
        [(b"", {"D111": b""}), (b"-1000\r\n", None)],
        ids=["silent", "wrong-reply"],
    )
    def test_failed_handshake_closes_port(
        self,
        monkeypatch: pytest.MonkeyPatch,
        handshake: bytes,
        replies: dict[str, bytes] | None,
    ) -> None:
        """A device that does not answer REMOTE MODE is closed and reported."""
        port = FakePRPort(replies, handshake=handshake)
        monkeypatch.setattr(serial, "Serial", lambda *_args, **_kwargs: port)

        with pytest.raises(DeviceError, match="handshake"):
            PRSpectrometer(FAKE_PORT_NAME)

        assert not port.is_open

    def test_a_device_already_in_remote_mode_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Silent to PHOTO but answering commands: a bench PR-655 left in
        remote mode by a caller that never sent Q."""
        port = FakePRPort(handshake=b"")
        monkeypatch.setattr(serial, "Serial", lambda *_args, **_kwargs: port)

        pr = PRSpectrometer(FAKE_PORT_NAME)

        assert port.commands[:3] == ["PHOTO", "", "D111"]
        assert pr.model == "PR-655"


def _install_timed(monkeypatch: pytest.MonkeyPatch, port: FakePRPort) -> None:
    """Open ``port`` with the driver's timeout, on the fake's virtual clock."""

    def open_port(
        *_args: object, timeout: float | None = None, **_kwargs: object
    ) -> FakePRPort:
        port.timeout = timeout
        return port

    monkeypatch.setattr(serial, "Serial", open_port)
    monkeypatch.setattr(_common, "_monotonic", port.clock)


class TestReconnectIsBounded:
    """The reconnect after a silent handshake costs little on an empty port."""

    def test_a_silent_port_is_refused_quickly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing answers the ended line, so no model request follows."""
        port = FakePRPort({"": b"", "D111": b""}, handshake=b"")
        _install_timed(monkeypatch, port)

        with pytest.raises(DeviceError, match="handshake"):
            PRSpectrometer(FAKE_PORT_NAME)

        assert "D111" not in port.commands
        assert port.clock() <= (
            _common._REMOTE_MODE_TIMEOUT + _common._RECONNECT_TIMEOUT
        )
        assert not port.is_open

    def test_a_port_that_answers_only_the_line_is_refused_quickly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The model request after the ended line has a short timeout too."""
        port = FakePRPort({"D111": b""}, handshake=b"")
        _install_timed(monkeypatch, port)

        with pytest.raises(DeviceError, match="handshake"):
            PRSpectrometer(FAKE_PORT_NAME)

        assert port.clock() <= (
            _common._REMOTE_MODE_TIMEOUT
            + 2 * _common._RECONNECT_TIMEOUT
            + _common._DRAIN_QUIET_GAP
        )

    def test_a_line_answer_that_is_no_reply_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only a reply code shows a Photo Research device in remote mode."""
        port = FakePRPort({"": b"garbage\r\n"}, handshake=b"")
        _install_timed(monkeypatch, port)

        with pytest.raises(DeviceError, match="handshake"):
            PRSpectrometer(FAKE_PORT_NAME)

        assert "D111" not in port.commands

    def test_a_slow_answer_within_the_bound_reconnects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An answer inside the reconnect timeout is still accepted."""
        late = _common._RECONNECT_TIMEOUT / 2
        port = FakePRPort({"": Reply((late, b"-1000\r\n"))}, handshake=b"")
        _install_timed(monkeypatch, port)

        pr = PRSpectrometer(FAKE_PORT_NAME)

        assert pr.model == "PR-655"


class TestExitRemoteMode:
    """close() and the context manager."""

    def test_close_sends_bare_q(self, open_pr: OpenPR) -> None:
        """close() writes Q with no terminator, then closes the port."""
        pr, port = open_pr()

        pr.close()

        assert bytes(port.written).endswith(b"Q")
        assert port.commands[-1] == "Q"
        assert not port.remote
        assert not port.is_open

    def test_close_is_idempotent(self, open_pr: OpenPR) -> None:
        """A second close() sends nothing and does not fail."""
        pr, port = open_pr()
        pr.close()
        written = bytes(port.written)

        pr.close()

        assert bytes(port.written) == written
        assert port.close_count == 1

    def test_context_manager_closes(self, open_pr: OpenPR) -> None:
        """Leaving a with block exits remote mode and closes the port."""
        pr, port = open_pr()

        with pr as entered:
            assert entered is pr

        assert port.commands[-1] == "Q"
        assert not port.is_open

    def test_context_manager_closes_on_error(self, open_pr: OpenPR) -> None:
        """An exception inside the block still exits remote mode."""
        pr, port = open_pr()

        with pytest.raises(RuntimeError), pr:
            raise RuntimeError

        assert port.commands[-1] == "Q"
        assert not port.is_open
