"""
Port discovery for the Photo Research driver.

Discovery filters ports by USB metadata before opening any, so it never
sends ``PHOTO`` to another vendor's instrument. The Konica Minolta port
below matches a CA-410 (VID 0x132B, the Konica Minolta vendor ID in the
linux-usb.org usb.ids list).
"""

from __future__ import annotations

import platform

import pytest
import serial
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from specio._device_implementations.photo_research import PRSpectrometer
from specio._device_implementations.photo_research.tests.fakes import FakePRPort

KONICA_MINOLTA_VID = 0x132B
CA410_PID = 0x210D
KONICA_MINOLTA_MANUFACTURER = "KONICA MINOLTA, INC."

KM_PORT = "/dev/cu.usbmodemAA1J800050861"
PR_PORT = "/dev/cu.usbmodem1101"


def _port_info(
    device: str,
    vid: int | None = None,
    pid: int | None = None,
    manufacturer: str | None = None,
    description: str = "n/a",
) -> ListPortInfo:
    """Build the ListPortInfo that list_ports.comports() would report."""
    info = ListPortInfo(device, skip_link_detection=True)
    info.vid = vid
    info.pid = pid
    info.manufacturer = manufacturer
    info.description = description
    return info


def _konica_minolta(
    device: str = KM_PORT,
    vid: int | None = KONICA_MINOLTA_VID,
    manufacturer: str | None = KONICA_MINOLTA_MANUFACTURER,
) -> ListPortInfo:
    """A Konica Minolta CA-410 port."""
    return _port_info(device, vid, CA410_PID, manufacturer, "CA-410")


class FakeSerialFactory:
    """
    Stand in for ``serial.Serial``, recording every port opened.

    Parameters
    ----------
    ports : dict[str, FakePRPort]
        Fake ports keyed by device path. Any other path fails to open with
        ``serial.SerialException``, as a missing device would.
    """

    def __init__(self, ports: dict[str, FakePRPort]) -> None:
        self.ports = ports
        self.opened: list[str] = []

    def __call__(self, device: str, **_kwargs: object) -> FakePRPort:
        """Open ``device``, or raise as pyserial does for a missing one."""
        self.opened.append(device)
        if device not in self.ports:
            raise serial.SerialException(f"could not open port {device}")
        return self.ports[device]


def _install(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    comports: list[ListPortInfo],
    ports: dict[str, FakePRPort],
) -> FakeSerialFactory:
    """Patch the platform, the port listing and the serial constructor."""
    factory = FakeSerialFactory(ports)
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(list_ports, "comports", lambda *_args, **_kwargs: comports)
    monkeypatch.setattr(serial, "Serial", factory)
    return factory


class TestOtherVendorsAreNeverOpened:
    """Ports that identify as another vendor's device are skipped unopened."""

    def test_konica_minolta_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With only a CA-410 attached, discovery fails without opening it."""
        factory = _install(monkeypatch, "Darwin", [_konica_minolta()], {})

        with pytest.raises(serial.SerialException):
            PRSpectrometer.discover()

        assert factory.opened == []

    def test_konica_minolta_beside_pr655(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Discovery finds the PR-655 and never opens the CA-410."""
        pr_port = FakePRPort()
        factory = _install(
            monkeypatch,
            "Darwin",
            [_konica_minolta(), _port_info(PR_PORT)],
            {PR_PORT: pr_port},
        )

        device = PRSpectrometer.discover()

        assert factory.opened == [PR_PORT]
        assert device.model == "PR-655"

    @pytest.mark.parametrize(
        "port",
        [
            _konica_minolta(manufacturer=None),
            _konica_minolta(vid=None),
            _port_info("/dev/cu.usbmodem2201", manufacturer="Arduino LLC"),
        ],
        ids=["vid-only", "manufacturer-only", "other-manufacturer"],
    )
    def test_either_identifier_is_enough(
        self, monkeypatch: pytest.MonkeyPatch, port: ListPortInfo
    ) -> None:
        """A foreign VID or a foreign manufacturer string rules a port out."""
        factory = _install(monkeypatch, "Darwin", [port], {})

        with pytest.raises(serial.SerialException):
            PRSpectrometer.discover()

        assert factory.opened == []


class TestCandidatePorts:
    """Which ports discovery opens on each platform."""

    def test_linux_probes_cdc_acm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The PR-655's USB CDC interface appears as /dev/ttyACM* on Linux."""
        acm = "/dev/ttyACM0"
        factory = _install(
            monkeypatch,
            "Linux",
            [_port_info("/dev/ttyS0"), _port_info(acm)],
            {acm: FakePRPort()},
        )

        PRSpectrometer.discover()

        assert factory.opened == [acm]

    def test_windows_needs_photo_research_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows only a port described as Photo Research is opened."""
        factory = _install(
            monkeypatch,
            "Windows",
            [
                _port_info("COM3", description="USB Serial Device (COM3)"),
                _port_info(
                    "COM4",
                    manufacturer="Photo Research, Inc.",
                    description="Photo Research PR-655 (COM4)",
                ),
            ],
            {"COM4": FakePRPort()},
        )

        PRSpectrometer.discover()

        assert factory.opened == ["COM4"]


class TestFailures:
    """Failed candidates are closed, and only expected errors are skipped."""

    def test_failed_handshake_is_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A port that fails the handshake is closed before the next is tried."""
        silent = FakePRPort(handshake=b"")
        good_path = "/dev/cu.usbmodem3301"
        _install(
            monkeypatch,
            "Darwin",
            [_port_info(PR_PORT), _port_info(good_path)],
            {PR_PORT: silent, good_path: FakePRPort()},
        )

        PRSpectrometer.discover()

        assert not silent.is_open

    def test_unopenable_port_is_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A port that raises SerialException on open is skipped."""
        good_path = "/dev/cu.usbmodem3301"
        factory = _install(
            monkeypatch,
            "Darwin",
            [_port_info(PR_PORT), _port_info(good_path)],
            {good_path: FakePRPort()},
        )

        PRSpectrometer.discover()

        assert factory.opened == [PR_PORT, good_path]

    def test_unexpected_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Errors other than serial and device errors are not swallowed."""

        def broken(*_args: object, **_kwargs: object) -> FakePRPort:
            raise RuntimeError("driver bug")

        _install(monkeypatch, "Darwin", [_port_info(PR_PORT)], {})
        monkeypatch.setattr(serial, "Serial", broken)

        with pytest.raises(RuntimeError, match="driver bug"):
            PRSpectrometer.discover()
