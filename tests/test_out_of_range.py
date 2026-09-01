"""An out-of-range measurement is a result, not a failed exchange."""

import pytest

from specio._device_implementations.colorimetry_research._common import (
    OUT_OF_RANGE_CODES,
    CommandError,
    CommandResponse,
    MeasurementOutOfRange,
    ResponseCode,
    ResponseType,
)


def response(code: ResponseCode, arguments: list[str]) -> CommandResponse:
    return CommandResponse(
        type=ResponseType.ERROR, code=code, description="M", arguments=arguments
    )


class TestOutOfRangeIsItsOwnType:
    def test_the_codes_the_device_uses_for_it(self) -> None:
        assert ResponseCode.TOO_DARK in OUT_OF_RANGE_CODES
        assert ResponseCode.LIGHT_INTENSITY_UNMEASURABLE in OUT_OF_RANGE_CODES
        assert ResponseCode.LIGHT_INTENSITY_TOO_HIGH in OUT_OF_RANGE_CODES

    def test_it_is_still_a_command_error(self) -> None:
        """Callers that only knew CommandError keep working."""
        assert issubclass(MeasurementOutOfRange, CommandError)

    def test_it_carries_the_device_s_own_code(self) -> None:
        e = MeasurementOutOfRange(
            response(ResponseCode.TOO_DARK, ["too dark"]), "too dark"
        )

        assert e.code is ResponseCode.TOO_DARK


class TestAnErrorWithNoArguments:
    """The device does not always attach an argument to an error.

    Indexing one that is not there turned the instrument's report into
    an `IndexError` raised from inside this library: a caller saw a
    crash where the device had sent a perfectly clear message. Observed
    on a CR-300 reading a capped aperture at NORMAL speed.
    """

    def test_it_reports_rather_than_crashing(self) -> None:
        from specio._device_implementations.colorimetry_research import _common

        class Port:
            timeout = 0.1

            def write(self, data: bytes) -> None: ...

            def readline(self) -> bytes:
                return b"ER:100:M\n"

            def apply_settings(self, settings: dict) -> None: ...

            def reset_input_buffer(self) -> None: ...

            def read(self, n: int = 1) -> bytes:
                return b""

            def readall(self) -> bytes:
                return b""

        class Bare(_common.CRDeviceBase):
            """The base's command path, with the abstract read stubbed."""

            def _raw_measure(self):  # type: ignore[override]
                raise NotImplementedError

            def __init__(self) -> None:
                self._port = Port()
                self._CRDeviceBase__last_cmd_time = 0.0

        device = Bare()

        with pytest.raises(_common.CommandError) as raised:
            device._write_cmd("RM Measure")

        # It reports rather than crashing, and it says which condition.
        assert isinstance(raised.value, MeasurementOutOfRange)
        assert raised.value.code is ResponseCode.TOO_DARK
