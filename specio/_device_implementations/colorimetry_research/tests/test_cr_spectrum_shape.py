"""A CR spectrometer reads its spectrum's wavelength range from the device,
and a reply with no range from a model the driver has no default for raises
a named error instead of an unbound-variable crash."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from specio._device_implementations.colorimetry_research._cr_spectrometers import (
    CRSpectrometer,
)
from specio._device_implementations.colorimetry_research.tests.test_cr_spectrometer import (  # noqa: E501
    ScriptedPort,
)
from specio.common.exceptions import DeviceError


class SpectrumPort(ScriptedPort):
    """A scripted port that also measures and sends a spectrum.

    ``spectrum`` is the `RM Spectrum` header's argument, ``start,end,step``,
    and ``points`` the data lines that follow it.
    """

    def __init__(self, model: str, spectrum: str, points: int) -> None:
        super().__init__()
        self.model = model
        self.spectrum = spectrum
        self.points = points
        self.drained = False

    def write(self, b: bytes, /) -> int:
        command = b.decode().removesuffix("\n")
        replies = {
            "M": ["OK:0:M:No errors"],
            "RC Model": [f"OK:0:RC Model:{self.model}"],
            "RC ID": ["OK:0:RC ID:A00000"],
            "RM Exposure": ["OK:0:RM Exposure:100 ms"],
            "RM Spectrum": [f"OK:0:RM Spectrum:{self.spectrum}"]
            + ["0.001"] * self.points,
        }
        if command not in replies:
            return super().write(b)
        self.sent.append(command)
        self._pending += [line.encode() + b"\r\n" for line in replies[command]]
        return len(b)

    @property
    def in_waiting(self) -> int:
        # The spectrum's data lines are read by the driver itself, after the
        # header, so the parser must not take them as the header's arguments.
        return 0

    def reset_input_buffer(self) -> None:
        self._pending.clear()
        self.drained = True

    def reset_output_buffer(self) -> None:
        return None


OpenCR = Callable[["SpectrumPort"], CRSpectrometer]


@pytest.fixture
def open_cr(monkeypatch: pytest.MonkeyPatch) -> OpenCR:
    def open_with(port: SpectrumPort) -> CRSpectrometer:
        from specio._device_implementations.colorimetry_research import _common

        monkeypatch.setattr(_common.serial, "Serial", lambda *a, **k: port)
        return CRSpectrometer("/dev/fake")

    return open_with


def test_the_range_the_device_reports_is_used(open_cr: OpenCR) -> None:
    port = SpectrumPort("CR-300", "380,382,1", points=3)
    raw = open_cr(port)._raw_measure()

    assert list(raw.spd.wavelengths) == [380, 381, 382]


@pytest.mark.parametrize(("model", "points"), [("CR-300", 401), ("CR-250", 101)])
def test_a_known_model_without_a_range_takes_its_default(
    open_cr: OpenCR, model: str, points: int
) -> None:
    port = SpectrumPort(model, "0,0,0", points=points)
    raw = open_cr(port)._raw_measure()

    assert len(raw.spd.wavelengths) == points


def test_an_unknown_model_without_a_range_raises_by_name(open_cr: OpenCR) -> None:
    """The shape was left unbound, so the measurement crashed with an
    UnboundLocalError naming a local variable."""
    port = SpectrumPort("CR-999", "0,0,0", points=5)
    cr = open_cr(port)

    with pytest.raises(DeviceError, match="CR-999"):
        cr._raw_measure()

    # The spectrum lines still in flight would answer the next command.
    assert port.drained
