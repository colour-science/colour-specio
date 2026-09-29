"""
Test the Konica Minolta CA-410 driver against an in-memory serial port.

The scripted replies are captured from a CA-VP427A probe connected over USB.
"""

# cspell:ignore comports

from collections.abc import Mapping
from types import SimpleNamespace

import numpy as np
import pytest
import serial

from specio._device_implementations import konica_minolta_ca410
from specio._device_implementations.konica_minolta_ca410 import (
    CA410,
    CA410Error,
    MeasurementStatus,
)
from specio.common.exceptions import DeviceError
from specio.common.utility import SpecioRuntimeWarning

IDENTITY_REPLY = b"OK00,CA-410,00800,CA-VP427A       ,Ver.1.80.0002,80005086,\r"
MEASURE_REPLY = (
    b"OK00,P1,0,0.3083380,0.3401959,0.1777124,+0.02,-99999999,"
    b"0.1610704,0.1777124,0.1835998\r"
)


class StreamPort(serial.Serial):
    """A closed serial port backed by an in-memory input buffer.

    Each command written appends its scripted reply to the input buffer, and
    pyserial's own ``read_until`` reads it back one byte at a time. An empty
    input buffer reads as a timeout.
    """

    def __init__(self, replies: Mapping[str, bytes | list[bytes]]) -> None:
        super().__init__()
        self.replies = {
            k: list(v) if isinstance(v, list) else [v] for k, v in replies.items()
        }
        self.rx = bytearray()
        self.sent: list[bytes] = []
        self.read_timeouts: dict[str, float | None] = {}
        self.was_closed = False

    def write(self, b: bytes, /) -> int:  # type: ignore[override]
        self.sent.append(bytes(b))
        queue = self.replies[b.decode().removesuffix("\r")]
        self.rx += queue.pop(0) if len(queue) > 1 else queue[0]
        return len(b)

    def read(self, size: int = 1) -> bytes:
        self.read_timeouts[self.commands[-1]] = self.timeout
        data = bytes(self.rx[:size])
        del self.rx[:size]
        return data

    @property
    def in_waiting(self) -> int:
        return len(self.rx)

    def reset_input_buffer(self) -> None:
        self.rx.clear()

    def close(self) -> None:
        self.was_closed = True

    @property
    def commands(self) -> list[str]:
        """Commands sent so far, without the delimiter."""
        return [c.decode().removesuffix("\r") for c in self.sent]


def make_port(**overrides: bytes | list[bytes]) -> StreamPort:
    """Build a port for a zero-calibrated probe, with optional reply overrides."""
    replies: dict[str, bytes | list[bytes]] = {
        "IDO,0,1": IDENTITY_REPLY,
        "STR,23": b"OK00,2\r",
        "ZRC": b"OK00\r",
        "MES,2": MEASURE_REPLY,
    }
    replies.update({k.replace("_", ","): v for k, v in overrides.items()})
    return StreamPort(replies)


class TestConnect:
    def test_reads_identity(self):
        ca = CA410(make_port())

        assert ca.manufacturer == "Konica Minolta"
        assert ca.model == "CA-410 CA-VP427A"
        assert ca.serial_number == "80005086"
        assert ca.firmware == "Ver.1.80.0002"
        assert ca.readable_id == "CA-410 CA-VP427A - 80005086"

    def test_terminates_commands_with_carriage_return(self):
        port = make_port()
        CA410(port)

        assert all(c.endswith(b"\r") and b"\n" not in c for c in port.sent)

    def test_zero_calibrates_when_never_calibrated(self):
        port = make_port(STR_23=b"OK00,0\r")
        CA410(port)

        assert "ZRC" in port.commands

    def test_skips_zero_calibration_when_completed(self):
        port = make_port()
        CA410(port)

        assert "ZRC" not in port.commands

    def test_warns_when_zero_calibration_recommended(self):
        port = make_port(STR_23=b"OK00,1\r")

        with pytest.warns(SpecioRuntimeWarning, match="zero_calibrate"):
            CA410(port)
        assert "ZRC" not in port.commands

    def test_no_reply_raises(self):
        port = make_port(IDO_0_1=b"")

        with pytest.raises(CA410Error, match="No response"):
            CA410(port)


class TestZeroCalibrate:
    def test_sends_zrc(self):
        port = make_port()
        ca = CA410(port)

        ca.zero_calibrate()

        assert port.commands[-1] == "ZRC"

    def test_light_leak_raises(self):
        port = make_port(ZRC=b"ER21\r")
        ca = CA410(port)

        with pytest.raises(CA410Error, match="light not fully blocked") as e:
            ca.zero_calibrate()
        assert e.value.code == "ER21"


class TestMeasure:
    def test_returns_xyz(self):
        ca = CA410(make_port())

        m = ca.measure()

        np.testing.assert_allclose(m.XYZ, [0.1610704, 0.1777124, 0.1835998])
        np.testing.assert_allclose(m.xy, [0.3083380, 0.3401959], atol=1e-6)
        assert m.device_id == "CA-410 CA-VP427A - 80005086"

    def test_exposure_is_unknown(self):
        ca = CA410(make_port())

        assert ca.measure().exposure == konica_minolta_ca410.UNKNOWN_EXPOSURE

    def test_sends_extended_format(self):
        port = make_port()
        ca = CA410(port)

        ca.measure()

        assert port.commands[-1] == "MES,2"

    def test_status_code_warns_and_returns(self):
        reply = MEASURE_REPLY.replace(b"OK00", b"OK06")
        ca = CA410(make_port(MES_2=reply))

        with pytest.warns(SpecioRuntimeWarning, match="TEMPERATURE_SHIFT"):
            m = ca.measure()
        np.testing.assert_allclose(m.XYZ[1], 0.1777124)

    def test_out_of_range_raises(self):
        ca = CA410(make_port(MES_2=b"ER22\r"))

        with pytest.raises(CA410Error, match="measurable range"):
            ca.measure()

    def test_error_is_device_error(self):
        assert issubclass(CA410Error, DeviceError)


class TestMeasurementStatus:
    def test_decodes_combined_codes(self):
        status = MeasurementStatus(71)

        assert status == (
            MeasurementStatus.CALIBRATION_PROBE_MISMATCH
            | MeasurementStatus.TEMPERATURE_SHIFT
            | MeasurementStatus.BELOW_GUARANTEED_RANGE
            | MeasurementStatus.BATTERY_LOW
        )


class TestDiscover:
    def test_filters_ports_by_usb_id(self, monkeypatch: pytest.MonkeyPatch):
        ports = [
            SimpleNamespace(device="/dev/cu.other", vid=0x0403, pid=0x6001),
            SimpleNamespace(device="/dev/cu.ca410", vid=0x132B, pid=0x210D),
            SimpleNamespace(device="/dev/cu.bt", vid=None, pid=None),
        ]
        monkeypatch.setattr(konica_minolta_ca410.list_ports, "comports", lambda: ports)

        assert konica_minolta_ca410.candidate_ports() == ["/dev/cu.ca410"]
