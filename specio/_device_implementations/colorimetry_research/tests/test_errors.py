"""The CR driver's errors belong to specio's own hierarchy, so a caller
catches any instrument's failure as `DeviceError` without importing a
driver's private module."""

from __future__ import annotations

import importlib

import pytest

from specio.common.exceptions import DeviceError

# By module path, so the package is what loads: the `colorimetry_research`
# name in its parent package can also name the deprecated shim module.
colorimetry_research = importlib.import_module(
    "specio._device_implementations.colorimetry_research"
)

CR_ERRORS = (
    "CommandError",
    "IncompleteResponse",
    "MeasurementOutOfRange",
    "UnexpectedResponse",
)


@pytest.mark.parametrize("name", CR_ERRORS)
def test_each_cr_error_is_a_device_error(name: str) -> None:
    assert issubclass(getattr(colorimetry_research, name), DeviceError)


@pytest.mark.parametrize("name", CR_ERRORS)
def test_each_cr_error_is_exported_from_the_package(name: str) -> None:
    assert name in colorimetry_research.__all__


def test_a_refusal_is_caught_as_a_device_error() -> None:
    """A caller that measures with any instrument catches one type."""
    response = colorimetry_research.CommandResponse(
        type=colorimetry_research.ResponseType.ERROR,
        code=next(iter(colorimetry_research.OUT_OF_RANGE_CODES)),
        description="M",
        arguments=[],
    )

    with pytest.raises(DeviceError):
        raise colorimetry_research.MeasurementOutOfRange(response, "too dark")
