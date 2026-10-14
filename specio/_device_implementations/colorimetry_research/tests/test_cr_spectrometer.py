"""
Test the Colorimetry Research spectrometer's speed setting against a scripted
port.

Replies follow the CR Protocol Manual 1.36, with the CRLF line endings a CR-300
(firmware 1.44) sends.
"""

import pytest
import serial

from specio._device_implementations.colorimetry_research import _common
from specio._device_implementations.colorimetry_research._common import CommandError
from specio._device_implementations.colorimetry_research._cr_spectrometers import (
    CRSpectrometer,
)

SPEED_NAMES = {"0": "Slow", "1": "Normal", "2": "Fast", "3": "2x Fast"}


class ScriptedPort(serial.Serial):
    """A closed serial port that answers CR commands like an instrument.

    ``SM Speed`` changes the speed that ``RS Speed`` reports, and ``M``
    fails with a light-too-low error, so a measurement stops once it has
    sent its setup commands.
    """

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []
        self.speed = "Normal"
        self._pending: list[bytes] = []

    def write(self, b: bytes, /) -> int:  # type: ignore[override]
        command = b.decode().removesuffix("\n")
        self.sent.append(command)
        if command.startswith("SM Speed "):
            self.speed = SPEED_NAMES[command.removeprefix("SM Speed ")]
            reply = "OK:0:Speed:No errors"
        elif command == "SM ExposureMode 0":
            reply = "OK:0:ExposureMode:No errors"
        elif command == "RS Speed":
            reply = f"OK:0:RS Speed:{self.speed}"
        elif command == "RS ExposureX":
            reply = "OK:0:RS ExposureX:1"
        elif command == "M":
            reply = "ER:-304:M:Light intensity too low"
        else:
            raise AssertionError(f"unscripted command {command!r}")
        self._pending.append(reply.encode() + b"\r\n")
        return len(b)

    @property
    def in_waiting(self) -> int:
        return len(self._pending)

    def readline(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self._pending.pop(0) if self._pending else b""

    def readall(self) -> bytes:
        self._pending.clear()
        return b""

    def apply_settings(self, d: dict) -> None:
        self.timeout = d.get("timeout", self.timeout)


@pytest.fixture
def port(monkeypatch: pytest.MonkeyPatch) -> ScriptedPort:
    """A scripted port that opening any serial port returns."""
    port = ScriptedPort()
    monkeypatch.setattr(_common.serial, "Serial", lambda *args, **kwargs: port)
    return port


class TestMeasurementSpeed:
    def test_reading_only_queries_the_instrument(self, port: ScriptedPort):
        cr = CRSpectrometer("/dev/fake")
        port.sent.clear()

        assert cr.measurement_speed is CRSpectrometer.MeasurementSpeed.NORMAL
        assert port.sent == ["RS Speed"]

    def test_setting_selects_auto_exposure(self, port: ScriptedPort):
        # The speed applies only in auto exposure mode (SM Speed, 4.2.1.19)
        cr = CRSpectrometer("/dev/fake")
        port.sent.clear()

        cr.measurement_speed = CRSpectrometer.MeasurementSpeed.FAST

        assert port.sent == ["SM ExposureMode 0", "SM Speed 2"]
        assert cr.measurement_speed is CRSpectrometer.MeasurementSpeed.FAST

    def test_measuring_selects_auto_exposure_first(self, port: ScriptedPort):
        cr = CRSpectrometer("/dev/fake")
        port.sent.clear()

        with pytest.raises(CommandError):
            cr.measure()

        assert port.sent.index("SM ExposureMode 0") < port.sent.index("M")
