"""Discovery opens only the USB ports that Colorimetry Research's vendor ID
names, and only those get a handshake."""

from __future__ import annotations

import importlib
import platform
from collections.abc import Callable
from typing import Any, NamedTuple

import pytest
import serial

# By module path, so the package is what loads rather than the deprecated shim.
cr = importlib.import_module("specio._device_implementations.colorimetry_research")
common = importlib.import_module(
    "specio._device_implementations.colorimetry_research._common"
)

CR_VID = 0x2799
OTHER_VID = 0x132B  # Konica Minolta, whose CA-410 shares a machine with a CR


class _PortInfo(NamedTuple):
    """The fields of `ListPortInfo` that discovery reads."""

    device: str
    vid: int | None
    pid: int | None = 0x0002


class _Serial:
    """A serial port that answers `RC InstrumentType` from a table."""

    opened: list[str] = []
    closed: list[str] = []
    written: list[tuple[str, bytes]] = []
    answers: dict[str, bytes] = {}
    timeout = 1.0

    def __init__(self, port: str, **_: Any) -> None:
        if port not in self.answers:
            raise serial.SerialException(f"could not open {port}")
        self.port = port
        type(self).opened.append(port)

    def readall(self) -> bytes:
        return b""

    def write(self, data: bytes) -> int:
        type(self).written.append((self.port, data))
        return len(data)

    def readline(self) -> bytes:
        return self.answers[self.port]

    def close(self) -> None:
        type(self).closed.append(self.port)


Machine = Callable[[list[_PortInfo], dict[str, bytes]], type[_Serial]]


@pytest.fixture
def machine(monkeypatch: pytest.MonkeyPatch) -> Machine:
    """Sets the ports on the machine and what each one answers.

    The colorimeter's constructor also reads its filters, which a fake that
    answers only the handshake can't serve, so that step is skipped: these
    tests are about which ports discovery opens.
    """
    monkeypatch.setattr(cr.CRColorimeter, "_warn_filter_selection", lambda self: None)

    def setup(ports: list[_PortInfo], answers: dict[str, bytes]) -> type[_Serial]:
        fake = type("FakeSerial", (_Serial,), {})
        fake.opened, fake.closed, fake.written = [], [], []
        fake.answers = answers
        monkeypatch.setattr(common.serial, "Serial", fake)
        monkeypatch.setattr(
            common.serial.tools.list_ports, "comports", lambda: list(ports)
        )
        return fake

    return setup


COLORIMETER = b"OK:0:RC InstrumentType:1\r\n"
SPECTRORADIOMETER = b"OK:0:RC InstrumentType:2\r\n"


@pytest.mark.parametrize("system", ["Linux", "Darwin", "Windows"])
def test_the_vendor_id_finds_a_cr_whatever_the_port_is_called(
    machine: Machine, monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    """Port names differ by platform, and a CR on `COM3` or `cu.usb-1` was
    invisible to the name filters. The vendor ID is the same everywhere."""
    monkeypatch.setattr(platform, "system", lambda: system)
    fake = machine(
        [_PortInfo("COM3", CR_VID), _PortInfo("/dev/cu.usb-1", CR_VID)],
        {"COM3": SPECTRORADIOMETER, "/dev/cu.usb-1": COLORIMETER},
    )

    device = cr.CRColorimeter.discover()

    assert device._port.port == "/dev/cu.usb-1"
    assert fake.opened[-1] == "/dev/cu.usb-1"


def test_a_port_of_another_vendor_never_gets_a_handshake(machine: Machine) -> None:
    """A CA-410, a serial adapter or a modem on `ttyACM` is not ours to
    write to. Writing to the wrong instrument can disturb a measurement."""
    fake = machine(
        [
            _PortInfo("/dev/ttyACM0", OTHER_VID, 0x210D),
            _PortInfo("/dev/ttyACM1", None, None),
            _PortInfo("/dev/ttyACM2", CR_VID),
        ],
        {
            "/dev/ttyACM0": b"",
            "/dev/ttyACM1": b"",
            "/dev/ttyACM2": COLORIMETER,
        },
    )

    cr.CRColorimeter.discover()

    assert {port for port, _ in fake.written} == {"/dev/ttyACM2"}
    assert "/dev/ttyACM0" not in fake.opened
    assert "/dev/ttyACM1" not in fake.opened


def test_no_cr_on_the_machine_opens_nothing(machine: Machine) -> None:
    fake = machine([_PortInfo("/dev/ttyACM0", OTHER_VID, 0x210D)], {})

    with pytest.raises(serial.SerialException, match="Colorimetry Research"):
        cr.CRColorimeter.discover()

    assert fake.opened == []
    assert fake.written == []


def test_a_cr_of_the_wrong_kind_is_closed_and_the_search_goes_on(machine: Machine) -> None:
    """A CR-300 and a CR-120 share a vendor ID and a product ID, so only the
    handshake tells them apart; the one that isn't wanted is released."""
    fake = machine(
        [_PortInfo("/dev/ttyACM0", CR_VID), _PortInfo("/dev/ttyACM1", CR_VID)],
        {"/dev/ttyACM0": SPECTRORADIOMETER, "/dev/ttyACM1": COLORIMETER},
    )

    device = cr.CRColorimeter.discover()

    assert device._port.port == "/dev/ttyACM1"
    assert "/dev/ttyACM0" in fake.closed


def test_a_cr_that_will_not_open_is_skipped(machine: Machine) -> None:
    """A port another program holds raises on open; the search goes on."""
    machine(
        [_PortInfo("/dev/ttyACM0", CR_VID), _PortInfo("/dev/ttyACM1", CR_VID)],
        {"/dev/ttyACM1": COLORIMETER},
    )

    assert cr.CRColorimeter.discover()._port.port == "/dev/ttyACM1"


def test_a_cr_of_the_wrong_kind_alone_is_not_found(machine: Machine) -> None:
    fake = machine([_PortInfo("/dev/ttyACM0", CR_VID)], {"/dev/ttyACM0": SPECTRORADIOMETER})

    with pytest.raises(serial.SerialException, match="colorimeter"):
        cr.CRColorimeter.discover()

    assert "/dev/ttyACM0" in fake.closed


def test_discovery_does_not_swallow_a_keyboard_interrupt(
    machine: Machine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare `except` caught the interrupt and kept probing ports."""
    fake = machine([_PortInfo("/dev/ttyACM0", CR_VID)], {"/dev/ttyACM0": COLORIMETER})

    def interrupted(self: _Serial) -> bytes:
        raise KeyboardInterrupt

    monkeypatch.setattr(fake, "readline", interrupted)

    with pytest.raises(KeyboardInterrupt):
        cr.CRColorimeter.discover()
    assert "/dev/ttyACM0" in fake.closed


def test_the_vendor_id_is_exported() -> None:
    assert common.USB_VENDOR_ID == CR_VID
