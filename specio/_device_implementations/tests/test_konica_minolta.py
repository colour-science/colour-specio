"""
Test the Konica Minolta CS-2000 driver's settings against a scripted port.

Replies follow the CS-2000 communication specification (KMSE A0E3-CS.07E).
"""

from collections.abc import Mapping

import serial

from specio._device_implementations.konica_minolta import (
    CS2000,
    InternalNDMode,
    SpeedMode,
    SpeedModeSetting,
    SyncMode,
    SyncSpeedSetting,
)

NORMAL_SPEED_REPLY = b"OK00,0,2\n"
FAST_SPEED_REPLY = b"OK00,1,2\n"
NO_SYNC_REPLY = b"OK00,0\n"
INTERNAL_60_HZ_REPLY = b"OK00,1,6000\n"


class ScriptedPort(serial.Serial):
    """A closed serial port that answers each command from a reply table.

    A command mapped to a list of replies answers with the next one each time
    it is sent, and repeats the last.
    """

    def __init__(self, replies: Mapping[str, bytes | list[bytes]]) -> None:
        super().__init__()
        self.replies = {
            k: list(v) if isinstance(v, list) else [v] for k, v in replies.items()
        }
        self.sent: list[str] = []
        self._pending: list[bytes] = []

    def write(self, b: bytes, /) -> int:  # type: ignore[override]
        command = b.decode().removesuffix("\n")
        self.sent.append(command)
        queue = self.replies[command]
        self._pending.append(queue.pop(0) if len(queue) > 1 else queue[0])
        return len(b)

    def readline(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self._pending.pop(0) if self._pending else b""

    def read_all(self) -> bytes:
        self._pending.clear()
        return b""


def make_port(**overrides: bytes | list[bytes]) -> ScriptedPort:
    """Build a port for a CS-2000, with optional reply overrides."""
    replies: dict[str, bytes | list[bytes]] = {
        "RMTS,1": b"OK00\n",
        "IDDR": b"OK00,CS-2000,1,10001234\n",
        "SPMR": NORMAL_SPEED_REPLY,
        "SPMS,1,2": b"OK00\n",
        "SCMR": NO_SYNC_REPLY,
        "SCMS,0": b"OK00\n",
    }
    replies.update({k.replace("_", ","): v for k, v in overrides.items()})
    return ScriptedPort(replies)


class TestSpeedMode:
    def test_reads_the_setting_it_just_wrote(self):
        port = make_port(SPMR=[NORMAL_SPEED_REPLY, FAST_SPEED_REPLY])
        cs = CS2000(port)
        assert cs.speedmode.mode is SpeedMode.NORMAL

        cs.speedmode = SpeedModeSetting(SpeedMode.FAST, InternalNDMode.AUTO)

        assert cs.speedmode.mode is SpeedMode.FAST

    def test_each_read_queries_the_instrument(self):
        # The front panel can change the setting between two reads
        port = make_port(SPMR=[NORMAL_SPEED_REPLY, FAST_SPEED_REPLY])
        cs = CS2000(port)

        cs.speedmode  # noqa: B018

        assert cs.speedmode.mode is SpeedMode.FAST
        assert port.sent.count("SPMR") == 2


class TestSyncMode:
    def test_sets_before_any_read(self):
        port = make_port()
        cs = CS2000(port)

        cs.syncmode = SyncSpeedSetting(SyncMode.NO_SYNC, None)

        assert port.sent[-1] == "SCMS,0"

    def test_each_read_queries_the_instrument(self):
        port = make_port(SCMR=[NO_SYNC_REPLY, INTERNAL_60_HZ_REPLY])
        cs = CS2000(port)

        cs.syncmode  # noqa: B018

        assert cs.syncmode == SyncSpeedSetting(SyncMode.INTERNAL, 60.0)
        assert port.sent.count("SCMR") == 2
