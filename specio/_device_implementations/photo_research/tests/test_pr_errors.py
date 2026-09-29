"""
Error-code handling of the Photo Research driver.

The codes come from the PR-655/670 User Manual, p.149-150 (Remote Control
Error Codes). Every data reply starts with the code ``qqqqq``, and any value
other than ``00000`` is an error (p.140).
"""

# cspell:ignore qqqqq

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specio._device_implementations.photo_research import (
    PRCommandError,
    PRResponseCode,
)
from specio.common.exceptions import DeviceError

if TYPE_CHECKING:
    from collections.abc import Callable

    from specio._device_implementations.photo_research import PRSpectrometer
    from specio._device_implementations.photo_research.tests.fakes import (
        FakePRPort,
    )

    OpenPR = Callable[..., tuple[PRSpectrometer, FakePRPort]]


class TestResponseCodes:
    """PRResponseCode mirrors the manual's error table."""

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (PRResponseCode.OK, 0),
            (PRResponseCode.LIGHT_SOURCE_NOT_CONSTANT, -1),
            (PRResponseCode.LIGHT_OVERLOAD, -2),
            (PRResponseCode.CANNOT_SYNC, -3),
            (PRResponseCode.ADAPTIVE_MODE_ERROR, -4),
            (PRResponseCode.WEAK_LIGHT, -8),
            (PRResponseCode.SYNC_ERROR, -9),
            (PRResponseCode.CANNOT_AUTO_SYNC, -10),
            (PRResponseCode.ADAPTIVE_MODE_TIMEOUT, -12),
            (PRResponseCode.ILLEGAL_COMMAND, -1000),
            (PRResponseCode.INVALID_EXPOSURE_VALUE, -1010),
            (PRResponseCode.INVALID_AVERAGE_CYCLES, -1012),
            (PRResponseCode.PARAMETER_NOT_APPLICABLE, -1035),
            (PRResponseCode.INVALID_DATA_REQUEST, -2000),
        ],
    )
    def test_values_match_manual(self, member: PRResponseCode, value: int) -> None:
        """Each member carries the manual's numeric code."""
        assert member == value

    def test_unknown_code_is_preserved(self) -> None:
        """A code outside the table keeps its value instead of becoming OK."""
        code = PRResponseCode(10)
        assert code == 10
        assert code != PRResponseCode.OK


class TestCommandErrors:
    """Any non-zero code raises PRCommandError."""

    def test_command_error_is_device_error(self) -> None:
        """PRCommandError belongs to specio's device error hierarchy."""
        assert issubclass(PRCommandError, DeviceError)

    @pytest.mark.parametrize(
        ("reply", "expected"),
        [
            (b"-0008\r\n", PRResponseCode.WEAK_LIGHT),
            (b"-8\r\n", PRResponseCode.WEAK_LIGHT),
            (b"-0001\r\n", PRResponseCode.LIGHT_SOURCE_NOT_CONSTANT),
            (b"-0010\r\n", PRResponseCode.CANNOT_AUTO_SYNC),
            (b"-1000\r\n", PRResponseCode.ILLEGAL_COMMAND),
            (b"-2000\r\n", PRResponseCode.INVALID_DATA_REQUEST),
        ],
    )
    def test_negative_code_raises(
        self, open_pr: OpenPR, reply: bytes, expected: PRResponseCode
    ) -> None:
        """Negative codes are errors, whatever their padding."""
        pr, _ = open_pr({"D111": reply})
        with pytest.raises(PRCommandError) as info:
            _ = pr.model
        assert info.value.response.code is expected

    @pytest.mark.parametrize("reply", [b"00010\r\n", b"00018,1.0e+00\r\n"])
    def test_positive_code_below_1000_raises(
        self, open_pr: OpenPR, reply: bytes
    ) -> None:
        """Non-zero codes below 1000 are errors, not OK."""
        pr, _ = open_pr({"D110": reply})
        with pytest.raises(PRCommandError) as info:
            _ = pr.serial_number
        assert info.value.response.code == int(reply[:5])

    def test_setup_error_raises(self, open_pr: OpenPR) -> None:
        """A rejected setup command raises with the manual's code."""
        pr, _ = open_pr({"SN5": b"-1012\r\n"})
        with pytest.raises(PRCommandError) as info:
            pr.average_samples = 5
        assert info.value.response.code is PRResponseCode.INVALID_AVERAGE_CYCLES

    def test_measurement_error_raises(self, open_pr: OpenPR) -> None:
        """A measurement error code from M0 raises before any data is read."""
        pr, port = open_pr({"M0": b"-0008\r\n"})
        with pytest.raises(PRCommandError) as info:
            pr.measure()
        assert info.value.response.code is PRResponseCode.WEAK_LIGHT
        assert "D5" not in port.commands

    @pytest.mark.parametrize("reply", [b"", b"garbage\r\n", b",PR-655\r\n"])
    def test_malformed_reply_raises_device_error(
        self, open_pr: OpenPR, reply: bytes
    ) -> None:
        """A missing or non-numeric code is a driver error, not success."""
        pr, _ = open_pr({"D111": reply})
        with pytest.raises(DeviceError):
            _ = pr.model
