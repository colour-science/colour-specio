"""
Test the Konica Minolta CA-410 driver against an in-memory serial port.

The scripted replies are captured from a CA-VP427A probe connected over USB.
"""

# cspell:ignore comports footlamberts

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


def patch_reply(Y: float) -> bytes:
    """Build an ``MES,2`` reply whose X, Y and Z all equal ``Y``."""
    XYZ = b"%.7f,%.7f,%.7f" % (Y, Y, Y)
    return b"OK00,P1,0,0.3333333,0.3333333,%.7f,+0.02,-99999999,%s\r" % (Y, XYZ)


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
        "STR,6": b"OK00,1\r",
        "STR,23": b"OK00,2\r",
        "ZRC": b"OK00\r",
        "MES,2": MEASURE_REPLY,
    }
    replies.update({k.replace("_", ","): v for k, v in overrides.items()})
    return StreamPort(replies)


def attach_ports(
    monkeypatch: pytest.MonkeyPatch, ports: Mapping[str, StreamPort | None]
) -> None:
    """List ``ports`` as CA-410 USB ports, and open them by name.

    A port mapped to None fails to open.
    """

    def open_port(device: str, **kwargs: object) -> StreamPort:
        port = ports[device]
        if port is None:
            raise serial.SerialException(f"could not open port {device}")
        return port

    listed = [SimpleNamespace(device=d, vid=0x132B, pid=0x210D) for d in ports]
    monkeypatch.setattr(konica_minolta_ca410.list_ports, "comports", lambda: listed)
    monkeypatch.setattr(konica_minolta_ca410.serial, "Serial", open_port)


class TestConnect:
    def test_reads_identity(self):
        ca = CA410(make_port())

        assert ca.manufacturer == "Konica-Minolta"
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

    def test_rejects_other_product(self):
        port = make_port(IDO_0_1=IDENTITY_REPLY.replace(b"CA-410", b"CA-310"))

        with pytest.raises(CA410Error, match="CA-310"):
            CA410(port)

    def test_closes_port_it_opened_when_connect_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        port = make_port(STR_23=b"OK00,0\r", ZRC=b"ER21\r")
        attach_ports(monkeypatch, {"/dev/cu.ca410": port})

        with pytest.raises(CA410Error):
            CA410("/dev/cu.ca410")
        assert port.was_closed

    def test_leaves_callers_port_open_when_connect_fails(self):
        port = make_port(STR_23=b"OK00,0\r", ZRC=b"ER21\r")

        with pytest.raises(CA410Error):
            CA410(port)
        assert not port.was_closed


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

    def test_averages_repetitions(self):
        port = make_port(MES_2=[patch_reply(1), patch_reply(3)])
        ca = CA410(port)

        m = ca.measure(repetitions=2)

        np.testing.assert_allclose(m.XYZ, [2, 2, 2])
        assert port.commands.count("MES,2") == 2

    def test_exposure_is_unknown(self):
        ca = CA410(make_port())

        assert ca.measure().exposure == konica_minolta_ca410.UNKNOWN_EXPOSURE

    def test_sends_extended_format(self):
        port = make_port()
        ca = CA410(port)

        ca.measure()

        assert port.commands[-1] == "MES,2"

    def test_converts_footlamberts_to_candelas_per_square_metre(self):
        # NIST SP 811, Appendix B.9: 1 fL = 3.426 259 cd/m^2
        ca = CA410(make_port(STR_6=b"OK00,0\r", MES_2=patch_reply(1)))

        np.testing.assert_allclose(ca.measure().XYZ, [3.426259] * 3, rtol=1e-6)

    @pytest.mark.parametrize("value", [b"0.1610704", b"0.1777124", b"0.1835998"])
    def test_missing_xyz_value_raises(self, value: bytes):
        head, xyz = MEASURE_REPLY.split(b"-99999999,")
        reply = head + b"-99999999," + xyz.replace(value, b"-99999999")
        ca = CA410(make_port(MES_2=reply))

        with pytest.raises(CA410Error, match="no value"):
            ca.measure()

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

    def test_command_error_names_zero_calibration(self):
        # ER10 also means zero calibration has not been executed (p. 102, 112)
        ca = CA410(make_port(MES_2=b"ER10\r"))

        with pytest.raises(CA410Error, match="zero calibration"):
            ca.measure()

    @pytest.mark.parametrize(
        "code",
        # Error Codes List, p. 111-115
        [
            "ER03", "ER05", "ER06", "ER10", "ER16", "ER20", "ER21", "ER22",
            "ER24", "ER31", "ER32", "ER50", "ER51", "ER53", "ER91", "ER99",
        ],
    )  # fmt: skip
    def test_every_specified_error_code_has_a_message(self, code: str):
        ca = CA410(make_port(MES_2=code.encode() + b"\r"))

        with pytest.raises(CA410Error) as e:
            ca.measure()
        assert e.value.code == code
        assert "Unknown error" not in str(e.value)

    def test_error_is_device_error(self):
        assert issubclass(CA410Error, DeviceError)


class TestReplyFraming:
    def test_discards_stale_reply_before_command(self):
        port = make_port(MES_2=[patch_reply(1), patch_reply(2)])
        ca = CA410(port)
        ca.measure()
        port.rx += b"OK00\r"  # The reply to a command abandoned by a timeout

        np.testing.assert_allclose(ca.measure().XYZ, [2, 2, 2])

    def test_late_reply_raises_then_recovers(self):
        # A ZRC reply abandoned by Ctrl-C arrives after the next MES,2 is sent.
        late = b"OK00\r" + patch_reply(1)
        ca = CA410(make_port(MES_2=[late, patch_reply(2)]))

        with pytest.raises(CA410Error, match="Malformed"):
            ca.measure()
        np.testing.assert_allclose(ca.measure().XYZ, [2, 2, 2])

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"MES_2": MEASURE_REPLY[:-1] + b",\r"}, id="trailing comma"),
            pytest.param({"MES_2": b"\x00" + MEASURE_REPLY}, id="leading NUL"),
            pytest.param({"MES_2": b"OK00,P1,0\r"}, id="missing fields"),
            pytest.param({"MES_2": b"\r"}, id="empty reply"),
            pytest.param({"MES_2": MEASURE_REPLY[:20]}, id="partial reply"),
            pytest.param({"MES_2": b"OK0" + MEASURE_REPLY[4:]}, id="short code"),
            pytest.param({"MES_2": b"XX00" + MEASURE_REPLY[4:]}, id="unknown code"),
            pytest.param(
                {"MES_2": MEASURE_REPLY.replace(b"0.1610704", b"0.16107x4")},
                id="non-numeric X",
            ),
            pytest.param(
                {"MES_2": MEASURE_REPLY.replace(b"P1", b"P\xb1")}, id="non-ASCII"
            ),
            pytest.param({"STR_6": b"OK00,2\r"}, id="undefined luminance unit"),
            pytest.param({"STR_23": b"OK00,3\r"}, id="undefined zero status"),
            pytest.param({"STR_23": b"OK00,\r"}, id="empty zero status"),
            pytest.param({"STR_23": b"OK00\r"}, id="zero status missing"),
            pytest.param({"IDO_0_1": b"OK00,CA-410\r"}, id="short identity"),
        ],
    )
    def test_malformed_reply_raises(self, overrides: dict[str, bytes]):
        with pytest.raises(CA410Error):
            CA410(make_port(**overrides)).measure()


class TestTimeouts:
    def test_each_command_waits_its_own_timeout(self):
        port = make_port(STR_23=b"OK00,0\r")

        CA410(port).measure()

        assert port.read_timeouts == {
            "IDO,0,1": konica_minolta_ca410.QUERY_TIMEOUT,
            "STR,6": konica_minolta_ca410.QUERY_TIMEOUT,
            "STR,23": konica_minolta_ca410.QUERY_TIMEOUT,
            "ZRC": konica_minolta_ca410.ZERO_CALIBRATION_TIMEOUT,
            "MES,2": konica_minolta_ca410.MEASURE_TIMEOUT,
        }

    def test_measure_timeout_covers_slowest_jeita_measurement(self):
        # Timeout Duration, p. 9: (1 / 0.07 Hz x 5 + 0.6 + 1) x 1 x 1 + 1.5 s
        slowest_jeita = (1 / 0.07 * 5 + 0.6 + 1) + 1.5

        assert slowest_jeita == pytest.approx(konica_minolta_ca410.MEASURE_TIMEOUT)

    def test_queries_time_out_quickly(self):
        assert (
            konica_minolta_ca410.QUERY_TIMEOUT
            < konica_minolta_ca410.MEASURE_TIMEOUT / 10
        )


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

    def test_propagates_error_from_a_ca410(self, monkeypatch: pytest.MonkeyPatch):
        port = make_port(STR_23=b"OK00,0\r", ZRC=b"ER21\r")
        attach_ports(monkeypatch, {"/dev/cu.ca410": port})

        with pytest.raises(CA410Error) as e:
            CA410.discover()
        assert e.value.code == "ER21"
        assert port.was_closed

    def test_skips_ports_that_are_not_a_ca410(self, monkeypatch: pytest.MonkeyPatch):
        other = make_port(IDO_0_1=IDENTITY_REPLY.replace(b"CA-410", b"CA-310"))
        silent = make_port(IDO_0_1=b"")
        ca410 = make_port()
        attach_ports(
            monkeypatch,
            {
                "/dev/busy": None,
                "/dev/other": other,
                "/dev/silent": silent,
                "/dev/ca": ca410,
            },
        )

        assert CA410.discover().serial_number == "80005086"
        assert other.was_closed
        assert silent.was_closed
        assert not ca410.was_closed

    def test_raises_when_no_port_is_a_ca410(self, monkeypatch: pytest.MonkeyPatch):
        attach_ports(monkeypatch, {"/dev/silent": make_port(IDO_0_1=b"")})

        with pytest.raises(serial.SerialException, match="Couldn't find a CA-410"):
            CA410.discover()
