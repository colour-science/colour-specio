"""
A byte-stream fake of a Photo Research PR-655 serial port.

The fake subclasses pyserial's ``SerialBase`` and implements only the
byte-level primitives, so pyserial's own ``read_until`` and ``readline`` run
against it. A virtual clock times the replies, so a test can script a late,
cut or trailing reply without sleeping. Replies follow the formats in the PR-655/670 User Manual: the
``PHOTO`` handshake (p.129), command framing (p.132-133) and the data codes
(p.141-148).
"""

# cspell:ignore crlf msec serialutil

from __future__ import annotations

import heapq
import itertools
from typing import TYPE_CHECKING

import numpy as np
from serial.serialutil import SerialBase

if TYPE_CHECKING:
    from collections.abc import Mapping

    import numpy.typing as npt

__all__ = [
    "PR655_SHAPE",
    "FakePRPort",
    "Reply",
    "ScriptedReply",
    "d5_reply",
    "default_replies",
]

PR655_SHAPE = (380, 780, 4)
"""Start, end and increment in nanometers of the PR-655 native sampling."""

_CR = b"\r"
_CRLF = b"\r\n"
_HANDSHAKE = b"PHOTO"
_QUIT = b"Q"
_ILLEGAL_COMMAND = b"-1000\r\n"
_SETUP_OK = b"00000\r\n"


class Reply:
    """
    A reply delivered in timed parts.

    Each part arrives at its offset, in seconds on the fake's virtual clock,
    after the fake receives the command. Parts model a reply that arrives
    late, one cut by a pause, or stale lines that trail a complete reply.

    Parameters
    ----------
    *parts : tuple[float, bytes]
        ``(offset, data)`` pairs.
    """

    def __init__(self, *parts: tuple[float, bytes]) -> None:
        self.parts = parts


ScriptedReply = bytes | Reply
"""A reply that arrives at once, as bytes, or in timed parts."""


def d5_reply(
    values: npt.ArrayLike,
    shape: tuple[int, int, int] = PR655_SHAPE,
    code: str = "00000",
) -> bytes:
    """
    Build a D5 reply: a header line, then one ``wl,value`` line per sample.

    Parameters
    ----------
    values : npt.ArrayLike
        Spectral values, one per wavelength of ``shape``.
    shape : tuple[int, int, int], optional
        Start, end and increment of the wavelength domain in nanometers.
    code : str, optional
        The five-character error code at the start of the header.

    Returns
    -------
    bytes
        The reply as the instrument sends it, CRLF-terminated per line.
    """
    start, end, step = shape
    wavelengths = range(start, end + 1, step)
    header = f"{code},0,5.560e+02,1.827e-01,5.147e+01".encode()
    lines = [header] + [
        f"{wl},{value:.3e}".encode()
        for wl, value in zip(wavelengths, np.asarray(values, dtype=float), strict=True)
    ]
    return _CRLF.join(lines) + _CRLF


def default_replies() -> dict[str, ScriptedReply | list[ScriptedReply]]:
    """
    Return manual-format replies for a PR-655 in adaptive exposure mode.

    Returns
    -------
    dict[str, ScriptedReply | list[ScriptedReply]]
        Replies keyed by command, without the CR terminator.
    """
    start, end, step = PR655_SHAPE
    points = (end - start) // step + 1
    return {
        "D110": b"00000,67065106\r\n",
        "D111": b"00000,PR-655\r\n",
        "D120": f"00000,{points},0.00,{start},{end},{step},256,7,247\r\n".encode(),
        "M0": b"00000\r\n",
        "D5": d5_reply([float(i) for i in range(points)]),
        "D13": b"00000,Normal,250 msec\r\n",
        "D602": (
            b"00000,MS-75,None,None,None,1 deg,English,Adaptive,0 msec,Normal,"
            b"1 cycles,2 deg,No Smart Dark,No Sync,Standard Sensitivity,"
            b"60.00 Hertz\r\n"
        ),
    }


class FakePRPort(SerialBase):
    """
    Replay manual-format PR-655 replies over a byte stream.

    The fake enters remote mode when it receives the five bytes ``PHOTO``,
    leaves it on the single byte ``Q``, and otherwise treats every
    CR-terminated string as a command. A command with no scripted reply gets
    ``-1000`` (illegal command), except setup (``S``) commands, which
    succeed.

    Received bytes wait in a schedule until the virtual clock reaches their
    arrival time. A read that finds nothing advances the clock to the next
    arrival if it falls within the port timeout, and otherwise by the whole
    timeout, as a real port blocks. With no timeout and nothing scheduled, a
    read returns empty so that a test cannot hang.

    Parameters
    ----------
    replies : Mapping[str, ScriptedReply | list[ScriptedReply]] | None, optional
        Replies keyed by command. A list is consumed one reply per call.
        Entries override :func:`default_replies`.
    handshake : bytes, optional
        The bytes sent in reply to ``PHOTO``.
    """

    def __init__(
        self,
        replies: Mapping[str, ScriptedReply | list[ScriptedReply]] | None = None,
        handshake: bytes = b"REMOTE MODE\r\n",
    ) -> None:
        super().__init__()
        self.replies: dict[str, ScriptedReply | list[ScriptedReply]] = default_replies()
        self.replies.update(replies or {})
        self.handshake = handshake
        self.written = bytearray()
        self.commands: list[str] = []
        self.remote = False
        self.close_count = 0
        self._pending = bytearray()
        self._rx = bytearray()
        self._now = 0.0
        # Heap of (arrival time, sequence, data); the sequence keeps parts
        # that share an arrival time in the order they were scheduled.
        self._schedule: list[tuple[float, int, bytes]] = []
        self._sequence = itertools.count()
        self.is_open = True

    def _reconfigure_port(self, *args: object, **kwargs: object) -> None:
        """Accept timeout changes; a fake has no hardware to reconfigure."""

    def clock(self) -> float:
        """
        Return the virtual time in seconds since the fake was created.

        Returns
        -------
        float
            The virtual clock reading.
        """
        return self._now

    def emit(self, data: bytes, after: float = 0.0) -> None:
        """
        Schedule bytes that arrive unasked, ``after`` seconds from now.

        Parameters
        ----------
        data : bytes
            The bytes to deliver.
        after : float, optional
            Delay in virtual seconds.
        """
        entry = (self._now + after, next(self._sequence), data)
        heapq.heappush(self._schedule, entry)

    def _arrive(self) -> None:
        """Move every scheduled part whose time has come into the input."""
        while self._schedule and self._schedule[0][0] <= self._now:
            self._rx += heapq.heappop(self._schedule)[2]

    def _wait_for_input(self) -> None:
        """Advance the clock as a blocking read with the port timeout would."""
        if self._rx or self.timeout == 0:
            return
        next_arrival = self._schedule[0][0] if self._schedule else None
        if next_arrival is not None and (
            self.timeout is None or next_arrival <= self._now + self.timeout
        ):
            self._now = next_arrival
        elif self.timeout is not None:
            self._now += self.timeout
        self._arrive()

    def _queue_reply(self, reply: ScriptedReply) -> None:
        """
        Schedule a scripted reply from the current virtual time.

        Parameters
        ----------
        reply : ScriptedReply
            The reply to deliver.
        """
        parts = reply.parts if isinstance(reply, Reply) else ((0.0, reply),)
        for offset, data in parts:
            self.emit(data, after=offset)
        self._arrive()

    def _reply_for(self, command: str) -> ScriptedReply:
        """
        Look up the scripted reply for one command.

        Parameters
        ----------
        command : str
            The command without its CR terminator.

        Returns
        -------
        ScriptedReply
            The reply.
        """
        reply = self.replies.get(command)
        if isinstance(reply, list):
            return reply.pop(0)
        if reply is not None:
            return reply
        if command.startswith("S"):
            return _SETUP_OK
        return _ILLEGAL_COMMAND

    def _dispatch(self) -> None:
        """Act on the pending bytes once they form a complete command."""
        pending = bytes(self._pending)
        if not self.remote:
            if pending == _HANDSHAKE:
                self.commands.append(pending.decode())
                self.remote = True
                self._queue_reply(self.handshake)
                self._pending.clear()
            elif not _HANDSHAKE.startswith(pending):
                self._pending.clear()
        elif pending == _QUIT:
            self.commands.append(pending.decode())
            self.remote = False
            self._pending.clear()
        elif pending.endswith(_CR):
            command = pending[: -len(_CR)].decode()
            self.commands.append(command)
            self._queue_reply(self._reply_for(command))
            self._pending.clear()

    def write(self, data: bytes) -> int:  # type: ignore[override]
        """
        Receive bytes from the driver.

        Parameters
        ----------
        data : bytes
            The bytes written.

        Returns
        -------
        int
            The number of bytes accepted.
        """
        for byte in data:
            self.written.append(byte)
            self._pending.append(byte)
            self._dispatch()
        return len(data)

    def read(self, size: int = 1) -> bytes:
        """
        Return up to ``size`` arrived bytes, or ``b""`` after a timeout.

        A read returns as soon as any bytes have arrived, without waiting
        to fill ``size``.

        Parameters
        ----------
        size : int, optional
            The maximum number of bytes to return.

        Returns
        -------
        bytes
            The bytes read.
        """
        self._arrive()
        self._wait_for_input()
        chunk = bytes(self._rx[:size])
        del self._rx[:size]
        return chunk

    @property
    def in_waiting(self) -> int:
        """
        Return the number of bytes that have arrived and not been read.

        Returns
        -------
        int
            Bytes available to read.
        """
        self._arrive()
        return len(self._rx)

    def reset_input_buffer(self) -> None:
        """Discard arrived bytes; bytes still in transit arrive later."""
        self._arrive()
        self._rx.clear()

    def flush(self) -> None:
        """Accept a flush; the fake has no output buffer."""

    def close(self) -> None:
        """Mark the port closed and count the call."""
        self.close_count += 1
        self.is_open = False
