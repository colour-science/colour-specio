"""
Remote-mode entry and exit on the Photo Research driver.

The PR-655/670 User Manual sends ``PHOTO`` as five single characters with
no terminator (p.129), and ``Q`` exits remote mode, also with no terminator
(p.132). Psychtoolbox's PR655init.m and PR670close.m send the same bytes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import serial

from specio._device_implementations.photo_research import PRSpectrometer
from specio._device_implementations.photo_research.tests.conftest import (
    FAKE_PORT_NAME,
)
from specio._device_implementations.photo_research.tests.fakes import FakePRPort
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

    @pytest.mark.parametrize("handshake", [b"", b"-1000\r\n"])
    def test_failed_handshake_closes_port(
        self, monkeypatch: pytest.MonkeyPatch, handshake: bytes
    ) -> None:
        """A device that does not answer REMOTE MODE is closed and reported."""
        port = FakePRPort(handshake=handshake)
        monkeypatch.setattr(serial, "Serial", lambda *_args, **_kwargs: port)

        with pytest.raises(DeviceError, match="handshake"):
            PRSpectrometer(FAKE_PORT_NAME)

        assert not port.is_open


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
