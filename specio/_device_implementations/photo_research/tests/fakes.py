"""
A byte-stream fake of a Photo Research PR-655 serial port.

The fake subclasses pyserial's ``SerialBase`` and implements only the
byte-level primitives, so pyserial's own ``read_until`` and ``readline`` run
against it. Replies follow the formats in the PR-655/670 User Manual: the
``PHOTO`` handshake (p.129), command framing (p.132-133) and the data codes
(p.141-148).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from serial.serialutil import SerialBase

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "PR655_SHAPE",
    "FakePRPort",
    "d5_reply",
    "default_replies",
]

PR655_SHAPE = (380, 780, 4)
"""Start, end and increment in nanometres of the PR-655 native sampling."""

_CR = b"\r"
_CRLF = b"\r\n"
_HANDSHAKE = b"PHOTO"
_QUIT = b"Q"
_ILLEGAL_COMMAND = b"-1000\r\n"
_SETUP_OK = b"00000\r\n"


def d5_reply(
    values: Sequence[float],
    shape: tuple[int, int, int] = PR655_SHAPE,
    code: str = "00000",
) -> bytes:
    """
    Build a D5 reply: a header line, then one ``wl,value`` line per sample.

    Parameters
    ----------
    values : Sequence[float]
        Spectral values, one per wavelength of ``shape``.
    shape : tuple[int, int, int], optional
        Start, end and increment of the wavelength domain in nanometres.
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
        for wl, value in zip(wavelengths, values, strict=True)
    ]
    return _CRLF.join(lines) + _CRLF


def default_replies() -> dict[str, bytes | list[bytes]]:
    """
    Return manual-format replies for a PR-655 in adaptive exposure mode.

    Returns
    -------
    dict[str, bytes | list[bytes]]
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

    Parameters
    ----------
    replies : Mapping[str, bytes | list[bytes]] | None, optional
        Replies keyed by command. A list is consumed one reply per call.
        Entries override :func:`default_replies`.
    handshake : bytes, optional
        The bytes sent in reply to ``PHOTO``.
    """

    def __init__(
        self,
        replies: Mapping[str, bytes | list[bytes]] | None = None,
        handshake: bytes = b"REMOTE MODE\r\n",
    ) -> None:
        super().__init__()
        self.replies: dict[str, bytes | list[bytes]] = default_replies()
        self.replies.update(replies or {})
        self.handshake = handshake
        self.written = bytearray()
        self.commands: list[str] = []
        self.remote = False
        self.close_count = 0
        self._pending = bytearray()
        self._rx = bytearray()
        self.is_open = True

    def _reconfigure_port(self, *args: object, **kwargs: object) -> None:
        """Accept timeout changes; a fake has no hardware to reconfigure."""

    def _reply_for(self, command: str) -> bytes:
        """
        Look up the scripted reply for one command.

        Parameters
        ----------
        command : str
            The command without its CR terminator.

        Returns
        -------
        bytes
            The reply bytes.
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
                self._rx += self.handshake
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
            self._rx += self._reply_for(command)
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
        Return up to ``size`` queued reply bytes, or ``b""`` when none remain.

        Parameters
        ----------
        size : int, optional
            The maximum number of bytes to return.

        Returns
        -------
        bytes
            The bytes read.
        """
        chunk = bytes(self._rx[:size])
        del self._rx[:size]
        return chunk

    @property
    def in_waiting(self) -> int:
        """
        Return the number of queued reply bytes.

        Returns
        -------
        int
            Bytes available to read.
        """
        return len(self._rx)

    def reset_input_buffer(self) -> None:
        """Discard queued reply bytes."""
        self._rx.clear()

    def flush(self) -> None:
        """Accept a flush; the fake has no output buffer."""

    def close(self) -> None:
        """Mark the port closed and count the call."""
        self.close_count += 1
        self.is_open = False
