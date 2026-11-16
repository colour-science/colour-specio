"""The CR colorimeter reads its settings without changing them, and reads
its filter wheel whether the device has filters or none."""

from __future__ import annotations

import pytest

from specio._device_implementations.colorimetry_research import CRColorimeter
from specio.common import SpecioRuntimeWarning


class _Port:
    """A serial port that hands out queued follow-on lines.

    `waiting` is what `in_waiting` reports when a reply is parsed: zero
    stands for rows that have not arrived yet at that instant.
    """

    def __init__(self, lines: list[bytes], waiting: int) -> None:
        self.lines = list(lines)
        self.waiting = waiting

    @property
    def in_waiting(self) -> int:
        return self.waiting

    def readline(self) -> bytes:
        return self.lines.pop(0) if self.lines else b""


def _colorimeter(
    replies: dict[str, bytes], port: _Port | None = None
) -> tuple[CRColorimeter, list[str]]:
    """A CRColorimeter whose commands answer from a script, with no serial
    port opened, and the list of commands it sends.

    The class is final, so the instance is built bare and its exchange
    replaced, rather than subclassed.
    """
    device = object.__new__(CRColorimeter)
    device._port = port or _Port([], 0)  # pyright: ignore[reportAttributeAccessIssue]
    sent: list[str] = []

    def write_cmd(command: str):  # noqa: ANN202
        sent.append(command)
        return device._parse_response(replies[command])

    device._write_cmd = write_cmd
    return device, sent


class TestMeasurementSpeed:
    def test_reading_the_speed_changes_nothing(self) -> None:
        """Reading the property used to switch the device to auto exposure."""
        d, sent = _colorimeter({"RS Speed": b"OK:0:RS Speed:Normal"})

        assert d.measurement_speed is CRColorimeter.MeasurementSpeed.NORMAL
        assert sent == ["RS Speed"]

    def test_setting_the_speed_selects_auto_exposure(self) -> None:
        """The speed applies only in auto exposure mode."""
        d, sent = _colorimeter(
            {"SM ExposureMode 0": b"OK:0:", "SM Speed 2": b"OK:0:"}
        )

        d.measurement_speed = CRColorimeter.MeasurementSpeed.FAST
        assert sent == ["SM ExposureMode 0", "SM Speed 2"]


class TestAvailableFilters:
    def test_a_device_with_no_filters_reports_only_none(self) -> None:
        d, _ = _colorimeter({"RC Filter": b"OK:0:RC Filter:0"})

        assert dict(d.available_filters) == {0: "None"}

    def test_filter_rows_that_arrive_after_the_header_are_read(self) -> None:
        """A slow reply's rows are not yet waiting when the header parses;
        reading the count as "no filters" cached an empty wheel."""
        port = _Port([b"1,Photopic\r\n", b"2,X\r\n"], waiting=0)
        d, _ = _colorimeter({"RC Filter": b"OK:0:RC Filter:2"}, port)

        assert dict(d.available_filters) == {0: "None", 1: "Photopic", 2: "X"}

    def test_rows_already_waiting_are_read(self) -> None:
        port = _Port([b"1,Photopic\r\n"], waiting=1)
        d, _ = _colorimeter({"RC Filter": b"OK:0:RC Filter:1"}, port)

        assert dict(d.available_filters) == {0: "None", 1: "Photopic"}


class TestFilterWarning:
    def _with_filters(self, selected: bytes) -> CRColorimeter:
        port = _Port([b"1,Photopic\r\n", b"2,X\r\n"], waiting=1)
        device, _ = _colorimeter(
            {"RC Filter": b"OK:0:RC Filter:2", "RS Filter": b"OK:0:RS Filter:" + selected},
            port,
        )
        return device

    def test_no_selected_filter_is_not_called_stacked(self) -> None:
        """Every slot reads back, selected or not, so an empty selection was
        reported as three stacked filters."""
        d = self._with_filters(b"None,None,None")

        with pytest.warns(SpecioRuntimeWarning, match="no active filters"):
            d._warn_filter_selection()

    def test_two_selected_filters_are_stacked(self) -> None:
        d = self._with_filters(b"Photopic,X,None")

        with pytest.warns(SpecioRuntimeWarning, match="stacked filters: Photopic, X"):
            d._warn_filter_selection()
