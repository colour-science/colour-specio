"""A reading carries the status and settings it was taken under."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from colour import SpectralDistribution, SpectralShape

from specio.common import (
    Colorimeter,
    ColorimeterMeasurement,
    RawColorimeterMeasurement,
    RawSPDMeasurement,
    ReadingStatus,
    SPDMeasurement,
    SpecRadiometer,
)

XYZ = np.array([10.0, 20.0, 30.0])
SHAPE = SpectralShape(400, 700, 10)


def make_spd(level: float = 1.0) -> SpectralDistribution:
    return SpectralDistribution(
        np.full(len(SHAPE.wavelengths), level), domain=SHAPE, name="fixed"
    )


class FakeColorimeter(Colorimeter):
    """Returns scripted raw readings, one per call."""

    serial_number = "1"  # type: ignore[assignment]
    manufacturer = "Fake"  # type: ignore[assignment]
    model = "Fake"  # type: ignore[assignment]

    def __init__(self, raws: list[RawColorimeterMeasurement]) -> None:
        self._raws = list(raws)

    def _raw_measure(self) -> RawColorimeterMeasurement:
        return self._raws.pop(0)


class FakeSpectrometer(SpecRadiometer):
    """Returns scripted raw readings, one per call."""

    serial_number = "1"  # type: ignore[assignment]
    manufacturer = "Fake"  # type: ignore[assignment]
    model = "Fake"  # type: ignore[assignment]

    def __init__(self, raws: list[RawSPDMeasurement]) -> None:
        self._raws = list(raws)

    def _raw_measure(self) -> RawSPDMeasurement:
        return self._raws.pop(0)


def raw_col(**kwargs: object) -> RawColorimeterMeasurement:
    return RawColorimeterMeasurement(XYZ, 0.5, "dev", **kwargs)  # type: ignore[arg-type]


def raw_spd(**kwargs: object) -> RawSPDMeasurement:
    return RawSPDMeasurement(make_spd(), 0.5, "dev", **kwargs)  # type: ignore[arg-type]


class TestReadingStatus:
    def test_defaults_describe_a_clean_reply(self):
        assert ReadingStatus() == ReadingStatus(code="", message="", flags=())

    def test_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            ReadingStatus().code = "OK04"  # type: ignore[misc]

    def test_is_hashable(self):
        assert hash(ReadingStatus("OK04", "x", ("A",))) == hash(
            ReadingStatus("OK04", "x", ("A",))
        )

    def test_is_exported_from_common(self):
        import specio.common

        assert "ReadingStatus" in specio.common.__all__


class TestDefaults:
    def test_raw_colorimeter(self):
        raw = RawColorimeterMeasurement(XYZ, 0.5, "dev")
        assert raw.status is None
        assert raw.settings == {}

    def test_raw_spd(self):
        raw = RawSPDMeasurement(make_spd(), 0.5, "dev")
        assert raw.status is None
        assert raw.settings == {}
        assert raw.anc_data is None

    def test_raw_settings_are_not_shared(self):
        a = RawColorimeterMeasurement(XYZ, 0.5, "dev")
        b = RawColorimeterMeasurement(XYZ, 0.5, "dev")
        a.settings["k"] = "v"
        assert b.settings == {}

    def test_colorimeter_measurement_constructor(self):
        m = ColorimeterMeasurement(XYZ, 0.5, "dev")
        assert m.status is None
        assert dict(m.settings) == {}

    def test_colorimeter_measurement_no_compute(self):
        m = ColorimeterMeasurement(XYZ, 0.5, "dev", no_compute=True)
        assert m.status is None
        assert dict(m.settings) == {}

    def test_spd_measurement_constructor(self):
        m = SPDMeasurement(make_spd(), 0.5, "dev")
        assert m.status is None
        assert dict(m.settings) == {}

    def test_spd_measurement_no_compute(self):
        m = SPDMeasurement(make_spd(), 0.5, "dev", no_compute=True)
        assert m.status is None
        assert dict(m.settings) == {}

    def test_class_level_default_settings_are_read_only(self):
        with pytest.raises(TypeError):
            ColorimeterMeasurement(XYZ, 0.5, "dev").settings["k"] = "v"  # type: ignore[index]

    def test_virtual_instruments_use_the_defaults(self):
        from specio._device_implementations.virtual import (
            VirtualColorimeter,
            VirtualSpectrometer,
        )

        for m in (VirtualColorimeter().measure(), VirtualSpectrometer().measure()):
            assert m.status is None
            assert dict(m.settings) == {}


class TestFromRaw:
    STATUS = ReadingStatus(
        "OK04", "BELOW_GUARANTEED_RANGE", ("BELOW_GUARANTEED_RANGE",)
    )

    def test_colorimeter_carries_status_and_settings(self):
        m = ColorimeterMeasurement.FromRaw(
            raw_col(status=self.STATUS, settings={"speed": "fast"})
        )
        assert m.status == self.STATUS
        assert dict(m.settings) == {"speed": "fast"}

    def test_spd_carries_status_and_settings(self):
        m = SPDMeasurement.FromRaw(
            raw_spd(status=self.STATUS, settings={"speed": "fast"})
        )
        assert m.status == self.STATUS
        assert dict(m.settings) == {"speed": "fast"}

    def test_constructors_take_keywords(self):
        c = ColorimeterMeasurement(
            XYZ, 0.5, "dev", status=self.STATUS, settings={"a": "b"}
        )
        s = SPDMeasurement(
            make_spd(), 0.5, "dev", status=self.STATUS, settings={"a": "b"}
        )
        assert c.status == s.status == self.STATUS
        assert dict(c.settings) == dict(s.settings) == {"a": "b"}

    def test_measurement_copies_the_settings(self):
        settings = {"a": "b"}
        m = ColorimeterMeasurement.FromRaw(raw_col(settings=settings))
        settings["a"] = "changed"
        assert dict(m.settings) == {"a": "b"}


class TestEquality:
    def test_unchanged_without_status_or_settings(self):
        a = ColorimeterMeasurement(XYZ, 0.5, "dev")
        b = ColorimeterMeasurement(XYZ, 0.5, "dev")
        b.time = a.time
        assert a == b

    @pytest.mark.parametrize(
        "kwargs",
        [{"status": ReadingStatus("OK04")}, {"settings": {"speed": "fast"}}],
    )
    def test_colorimeter_differs_by_status_or_settings(self, kwargs: dict[str, object]):
        a = ColorimeterMeasurement(XYZ, 0.5, "dev")
        b = ColorimeterMeasurement(XYZ, 0.5, "dev", **kwargs)  # type: ignore[arg-type]
        b.time = a.time
        assert a != b

    @pytest.mark.parametrize(
        "kwargs",
        [{"status": ReadingStatus("OK04")}, {"settings": {"speed": "fast"}}],
    )
    def test_spd_differs_by_status_or_settings(self, kwargs: dict[str, object]):
        a = SPDMeasurement(make_spd(), 0.5, "dev")
        b = SPDMeasurement(make_spd(), 0.5, "dev", **kwargs)  # type: ignore[arg-type]
        b.time = a.time
        assert a != b

    def test_equal_when_status_and_settings_match(self):
        kwargs = {"status": ReadingStatus("OK04"), "settings": {"speed": "fast"}}
        a = ColorimeterMeasurement(XYZ, 0.5, "dev", **kwargs)
        b = ColorimeterMeasurement(XYZ, 0.5, "dev", **kwargs)
        b.time = a.time
        assert a == b

    def test_comparison_keys_name_both(self):
        for m in (
            ColorimeterMeasurement(XYZ, 0.5, "dev"),
            SPDMeasurement(make_spd(), 0.5, "dev"),
        ):
            assert {"status", "settings"} <= set(m._get_comparison_keys())


class TestAveraging:
    def test_colorimeter_keeps_first_settings(self):
        col = FakeColorimeter(
            [raw_col(settings={"speed": "fast"}), raw_col(settings={"speed": "slow"})]
        )
        assert dict(col.measure(2).settings) == {"speed": "fast"}

    def test_spd_keeps_first_settings(self):
        spec = FakeSpectrometer(
            [raw_spd(settings={"speed": "fast"}), raw_spd(settings={"speed": "slow"})]
        )
        assert dict(spec.measure(2).settings) == {"speed": "fast"}

    def test_status_unions_flags_in_order_without_duplicates(self):
        readings = [
            raw_col(
                status=ReadingStatus(
                    "OK02", "TEMPERATURE_SHIFT", ("TEMPERATURE_SHIFT",)
                )
            ),
            raw_col(
                status=ReadingStatus(
                    "OK06", "a", ("TEMPERATURE_SHIFT", "BELOW_GUARANTEED_RANGE")
                )
            ),
            raw_col(status=ReadingStatus("OK00")),
        ]
        status = FakeColorimeter(readings).measure(3).status
        assert status == ReadingStatus(
            "OK02", "TEMPERATURE_SHIFT", ("TEMPERATURE_SHIFT", "BELOW_GUARANTEED_RANGE")
        )

    def test_status_takes_code_and_message_of_first_reading_with_one(self):
        readings = [
            raw_spd(),
            raw_spd(status=ReadingStatus("OK04", "m4", ("X",))),
            raw_spd(status=ReadingStatus("OK02", "m2", ("Y",))),
        ]
        status = FakeSpectrometer(readings).measure(3).status
        assert status == ReadingStatus("OK04", "m4", ("X", "Y"))

    def test_no_status_stays_none(self):
        assert FakeColorimeter([raw_col(), raw_col()]).measure(2).status is None
        assert FakeSpectrometer([raw_spd(), raw_spd()]).measure(2).status is None

    def test_single_reading_passes_through(self):
        status = ReadingStatus("OK04", "m", ("X",))
        m = FakeColorimeter([raw_col(status=status, settings={"a": "b"})]).measure()
        assert m.status == status
        assert dict(m.settings) == {"a": "b"}


def test_measurement_without_either_equals_what_it_did_before():
    """A raw reading built the old way still yields the same measurement."""
    old_way = ColorimeterMeasurement(XYZ, 0.5, "dev")
    via_raw = ColorimeterMeasurement.FromRaw(RawColorimeterMeasurement(XYZ, 0.5, "dev"))
    via_raw.time = old_way.time
    assert via_raw == old_way
