"""A CR measurement records the settings it was taken under.

The fakes answer like a CR-300 (CR Protocol Manual 1.36) and complete a whole
measurement, so the recorded settings come from the real ``_raw_measure``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import serial

from specio._device_implementations.colorimetry_research import _common
from specio._device_implementations.colorimetry_research._cr_colorimeters import (
    CRColorimeter,
)
from specio._device_implementations.colorimetry_research._cr_spectrometers import (
    CRSpectrometer,
)

if TYPE_CHECKING:
    from collections.abc import Callable

SPEED_NAMES = {"0": "Slow", "1": "Normal", "2": "Fast", "3": "2x Fast"}
SPECTRUM_START, SPECTRUM_END, SPECTRUM_STEP = 400, 500, 10
SPEED_TIMEOUTS = {"Slow": 70, "Normal": 21, "Fast": 14, "2x Fast": 7}


class CRPort(serial.Serial):
    """A closed serial port that plays a CR instrument for whole measurements."""

    def __init__(self, filters: str = "ND 0.3,None,None", samples: int = 4) -> None:
        super().__init__()
        self.sent: list[str] = []
        self.timeout_when_sent: dict[str, float | None] = {}
        self.speed = "Normal"
        self.samples = samples
        self.filters = filters
        self._pending: list[bytes] = []

    def _reply(self, text: str) -> None:
        self._pending.append(text.encode() + b"\r\n")

    def _static_replies(self) -> dict[str, list[str]]:
        """Reply lines for each command whose answer reads the fake's state."""
        spectrum_lines = (SPECTRUM_END - SPECTRUM_START) // SPECTRUM_STEP + 1
        return {
            "SM ExposureMode 0": ["OK:0:ExposureMode:No errors"],
            "RS Speed": [f"OK:0:RS Speed:{self.speed}"],
            "RS ExposureX": [f"OK:0:RS ExposureX:{self.samples}"],
            "RS Filter": [f"OK:0:RS Filter:{self.filters}"],
            "RC Filter": ["OK:0:RC Filter:2", "1,ND 0.3", "2,ND 0.6"],
            "RC ID": ["OK:0:RC ID:100001"],
            "RC Model": ["OK:0:RC Model:CR-300"],
            "M": ["OK:0:M:No errors"],
            "RM Spectrum": [
                f"OK:0:RM Spectrum:{SPECTRUM_START},{SPECTRUM_END},{SPECTRUM_STEP}",
                *["0.5"] * spectrum_lines,
            ],
            "RM XYZ": ["OK:0:RM XYZ:10.0,20.0,30.0"],
            "RM Exposure": ["OK:0:RM Exposure:12.5"],
        }

    def write(self, b: bytes, /) -> int:  # type: ignore[override]
        command = b.decode().removesuffix("\n")
        self.sent.append(command)
        self.timeout_when_sent[command] = self.timeout
        if command.startswith("SM Speed "):
            self.speed = SPEED_NAMES[command.removeprefix("SM Speed ")]
            lines = ["OK:0:Speed:No errors"]
        elif command in (replies := self._static_replies()):
            lines = replies[command]
        else:
            raise AssertionError(f"unscripted command {command!r}")
        for line in lines:
            self._reply(line)
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
def make_port(monkeypatch: pytest.MonkeyPatch) -> Callable[..., CRPort]:
    """Build a CR port, and make opening any serial port return it."""

    def make(**kwargs: object) -> CRPort:
        port = CRPort(**kwargs)  # type: ignore[arg-type]
        monkeypatch.setattr(_common.serial, "Serial", lambda *a, **k: port)
        return port

    return make


class TestSpectrometerSettings:
    def test_records_exposure_mode_speed_and_average_samples(
        self, make_port: Callable[..., CRPort]
    ):
        port = make_port(samples=4)
        cr = CRSpectrometer("/dev/fake", speed=CRSpectrometer.MeasurementSpeed.FAST)

        m = cr.measure()

        assert dict(m.settings) == {
            "exposure_mode": "auto",
            "speed": "fast",
            "average_samples": "4",
        }
        assert port.speed == "Fast"

    def test_speed_is_the_lowercase_enum_name(self, make_port: Callable[..., CRPort]):
        make_port()
        cr = CRSpectrometer("/dev/fake", speed=CRSpectrometer.MeasurementSpeed.FAST_2X)

        assert cr.measure().settings["speed"] == "fast_2x"

    def test_speed_is_read_once_per_measurement(self, make_port: Callable[..., CRPort]):
        port = make_port()
        cr = CRSpectrometer("/dev/fake")
        cr.measure()
        port.sent.clear()

        cr.measure()

        assert port.sent.count("RS Speed") == 1

    def test_recording_adds_no_exchange_beyond_the_speed_read(
        self, make_port: Callable[..., CRPort]
    ):
        port = make_port()
        cr = CRSpectrometer("/dev/fake")
        cr.measure()  # the first measurement also learns the average samples
        port.sent.clear()

        cr.measure()

        assert port.sent == [
            "SM ExposureMode 0",
            "RS Speed",
            "M",
            "RM Spectrum",
            "RM Exposure",
        ]

    @pytest.mark.parametrize("speed", list(CRSpectrometer.MeasurementSpeed))  # type: ignore[call-overload]
    def test_read_windows_are_sized_as_before(
        self,
        make_port: Callable[..., CRPort],
        speed: CRSpectrometer.MeasurementSpeed,
    ):
        port = make_port(samples=3)
        cr = CRSpectrometer("/dev/fake", speed=speed)
        restore = port.timeout

        cr.measure()

        window = SPEED_TIMEOUTS[SPEED_NAMES[str(speed.values[0])]] * 3
        assert port.timeout_when_sent["M"] == window
        assert port.timeout_when_sent["RM Spectrum"] == window
        assert port.timeout == restore

    def test_status_is_not_reported(self, make_port: Callable[..., CRPort]):
        make_port()

        assert CRSpectrometer("/dev/fake").measure().status is None


class TestColorimeterSettings:
    def test_records_declared_filters_and_average_samples(
        self, make_port: Callable[..., CRPort]
    ):
        make_port(samples=4)
        cr = CRColorimeter("/dev/fake")

        m = cr.measure()

        assert dict(m.settings) == {
            "filters": "ND 0.3,None,None",
            "average_samples": "4",
        }

    def test_records_every_declared_filter_in_position_order(
        self, make_port: Callable[..., CRPort]
    ):
        make_port(filters="ND 0.3,ND 0.6,None")

        m = CRColorimeter("/dev/fake").measure()

        assert m.settings["filters"] == "ND 0.3,ND 0.6,None"

    def test_has_no_speed_or_exposure_mode(self, make_port: Callable[..., CRPort]):
        make_port()

        m = CRColorimeter("/dev/fake").measure()

        assert "speed" not in m.settings
        assert "exposure_mode" not in m.settings

    def test_filters_cost_one_exchange(self, make_port: Callable[..., CRPort]):
        port = make_port()
        cr = CRColorimeter("/dev/fake")
        cr.measure()  # the first measurement also learns samples and identity
        port.sent.clear()

        cr.measure()

        assert port.sent == ["RS Filter", "M", "RM XYZ", "RM Exposure"]

    def test_filters_are_read_fresh_each_measurement(
        self, make_port: Callable[..., CRPort]
    ):
        port = make_port(filters="ND 0.3,None,None")
        cr = CRColorimeter("/dev/fake")
        first = cr.measure().settings["filters"]
        port.filters = "None,None,None"

        assert (first, cr.measure().settings["filters"]) == (
            "ND 0.3,None,None",
            "None,None,None",
        )

    def test_status_is_not_reported(self, make_port: Callable[..., CRPort]):
        make_port()

        assert CRColorimeter("/dev/fake").measure().status is None

    def test_averaged_readings_keep_the_first_settings(
        self, make_port: Callable[..., CRPort]
    ):
        port = make_port(filters="ND 0.3,None,None")
        cr = CRColorimeter("/dev/fake")
        port.filters = "None,None,None"

        m = cr.measure(repetitions=2)

        assert m.settings["filters"] == "None,None,None"
