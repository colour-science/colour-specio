"""
Fixtures that connect the Photo Research driver to a fake serial port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import serial

from specio._device_implementations.photo_research import PRSpectrometer, _common
from specio._device_implementations.photo_research.tests.fakes import FakePRPort

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "FAKE_PORT_NAME",
    "no_serial_delays",
    "open_pr",
]

FAKE_PORT_NAME = "/dev/cu.usbmodemFAKE"


@pytest.fixture(autouse=True)
def no_serial_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the per-byte and per-command pacing so tests run instantly."""
    monkeypatch.setattr(_common, "_CHAR_WRITE_DELAY", 0.0)
    monkeypatch.setattr(_common, "_COMMAND_DELAY", 0.0)


@pytest.fixture
def open_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., tuple[PRSpectrometer, FakePRPort]]:
    """
    Return a factory that opens a PRSpectrometer on a FakePRPort.

    Returns
    -------
    Callable[..., tuple[PRSpectrometer, FakePRPort]]
        Takes optional ``replies`` and returns the driver and its fake port.
    """

    def factory(
        replies: Mapping[str, bytes | list[bytes]] | None = None,
    ) -> tuple[PRSpectrometer, FakePRPort]:
        port = FakePRPort(replies)
        monkeypatch.setattr(serial, "Serial", lambda *_args, **_kwargs: port)
        return PRSpectrometer(FAKE_PORT_NAME), port

    return factory
