"""
Hardware integration tests for a Colorimetry Research colorimeter.

Every test skips unless discovery finds a connected CR colorimeter, such as a
CR-100 or CR-120. The tests send queries and one measurement only: they
change no setting, so the instrument keeps the filters and exposure mode it
had.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
import serial

from specio._device_implementations.colorimetry_research import (
    CRColorimeter,
    MeasurementOutOfRange,
)
from specio.common import ColorimeterMeasurement

if TYPE_CHECKING:
    from collections.abc import Iterator

# The setting reads that must leave the instrument as they found it.
_SETTING_QUERIES = ("RS ExposureMode", "RS Filter", "RS Mode", "RS Accessory")


@pytest.fixture(scope="module")
def colorimeter() -> Iterator[CRColorimeter]:
    """Discover a connected CR colorimeter, or skip the entire module."""
    try:
        device = CRColorimeter.discover()
    except serial.SerialException:
        pytest.skip("No CR colorimeter connected")
    yield device
    device._port.close()


def _settings(device: CRColorimeter) -> dict[str, str]:
    return {
        query: str(device._write_cmd(query).arguments) for query in _SETTING_QUERIES
    }


def test_the_instrument_identifies_as_a_cr_colorimeter(
    colorimeter: CRColorimeter,
) -> None:
    assert colorimeter.model.startswith("CR-1")
    assert colorimeter.firmware


def test_every_configured_filter_has_a_name(colorimeter: CRColorimeter) -> None:
    """ "None" is always ID 0, and each configured filter, such as an ND
    attachment, maps to a non-empty name without its type field."""
    filters = colorimeter.available_filters

    assert filters[0] == "None"
    for index, name in filters.items():
        assert name
        assert "," not in name, f"filter {index} kept its type field"


def test_the_declared_filters_resolve_by_name(colorimeter: CRColorimeter) -> None:
    """RS Filter names each slot's filter; every name maps back to an ID."""
    ids = colorimeter.current_filters

    assert len(ids) == 3
    assert colorimeter.current_filters_names == tuple(
        colorimeter.available_filters[i] for i in ids
    )


def test_reading_settings_changes_none_of_them(colorimeter: CRColorimeter) -> None:
    """Reads that used to write (the speed getter selected auto exposure)
    must leave every setting as it was."""
    before = _settings(colorimeter)

    _ = colorimeter.available_filters
    _ = colorimeter.current_filters
    _ = colorimeter.average_samples

    assert _settings(colorimeter) == before


def test_a_colorimeter_has_no_measurement_speed(colorimeter: CRColorimeter) -> None:
    """CR Protocol Manual 1.36 limits SM Speed and RS Speed to
    spectroradiometers; a CR-120 answers RC Speed with -502."""
    assert not hasattr(colorimeter, "measurement_speed")


def test_a_measurement_returns_xyz_or_a_typed_refusal(
    colorimeter: CRColorimeter,
) -> None:
    """Whatever the instrument faces: a reading, or the light is outside
    what it can measure."""
    try:
        measurement = colorimeter.measure()
    except MeasurementOutOfRange:
        return

    assert isinstance(measurement, ColorimeterMeasurement)
    assert measurement.XYZ.shape == (3,)
    assert np.all(np.isfinite(measurement.XYZ))
