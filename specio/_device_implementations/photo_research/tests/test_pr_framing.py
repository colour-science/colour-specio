"""
Reply framing on the Photo Research driver.

Every reply line ends in CR LF, and every reply starts with the
five-character code ``qqqqq``: ``00000`` on success, or a negative code such
as ``-0008`` (PR-655/670 User Manual, p.140). A late, cut or leftover reply
must never pass for the answer to a later command.
"""

# cspell:ignore qqqqq

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specio._device_implementations import photo_research
from specio._device_implementations.photo_research import (
    PRCommandError,
    PRIncompleteReplyError,
)
from specio._device_implementations.photo_research.tests.fakes import Reply
from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research import PRSpectrometer
    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]

# Past the driver's 5 s default reply timeout.
_LATE = 6.0


class TestIncompleteReplyError:
    """The error for a lost or cut reply."""

    def test_is_a_device_error(self) -> None:
        """It belongs to specio's device error hierarchy."""
        assert issubclass(PRIncompleteReplyError, DeviceError)

    def test_is_not_a_command_error(self) -> None:
        """It carries no device code, so it is not a PRCommandError."""
        assert not issubclass(PRIncompleteReplyError, PRCommandError)

    def test_is_exported_beside_command_error(self) -> None:
        """The package exports it next to PRCommandError."""
        assert "PRIncompleteReplyError" in photo_research.__all__


class TestFraming:
    """A reply is complete only when it ends in CR LF."""

    def test_cut_reply_raises(self, open_pr: OpenPR) -> None:
        """A reply that stops short of CR LF is not read as success."""
        pr, _ = open_pr({"D110": Reply((0.0, b"00000,1234"))})

        with pytest.raises(PRIncompleteReplyError):
            _ = pr.serial_number

    def test_late_reply_raises(self, open_pr: OpenPR) -> None:
        """A reply that arrives after the timeout is a lost reply."""
        pr, _ = open_pr({"D111": Reply((_LATE, b"00000,PR-655\r\n"))})

        with pytest.raises(PRIncompleteReplyError):
            _ = pr.model

    def test_reply_within_timeout_is_read(self, open_pr: OpenPR) -> None:
        """A slow reply that arrives in parts within the timeout is read."""
        pr, _ = open_pr(
            {"D111": Reply((0.5, b"00000,PR"), (1.0, b"-6"), (1.5, b"55\r\n"))}
        )

        assert pr.model == "PR-655"


class TestStrictCodes:
    """Only a fixed-width code at the start of a line is a reply code."""

    def test_data_line_is_not_a_code(self, open_pr: OpenPR) -> None:
        """A spectral line such as 424,1.999e-04 is not error code 424."""
        pr, _ = open_pr({"D111": b"424,1.999e-04\r\n"})

        with pytest.raises(PRIncompleteReplyError):
            _ = pr.model

    @pytest.mark.parametrize(
        "reply",
        [
            b"-8\r\n",
            b"0000\r\n",
            b"000000,PR-655\r\n",
            b"10000001\r\n",
            b" 00000,PR-655\r\n",
            b"\r\n",
        ],
    )
    def test_malformed_code_raises(self, open_pr: OpenPR, reply: bytes) -> None:
        """A code of the wrong width is unexpected, not a device error code."""
        pr, _ = open_pr({"D111": reply})

        with pytest.raises(PRIncompleteReplyError):
            _ = pr.model

    @pytest.mark.parametrize(
        ("reply", "data"),
        [(b"00000\r\n", ""), (b"00000,PR-655\r\n", "PR-655")],
    )
    def test_success_code(self, open_pr: OpenPR, reply: bytes, data: str) -> None:
        """00000, alone or before a comma and data, is success."""
        pr, _ = open_pr({"D111": reply})

        assert pr.model == data
