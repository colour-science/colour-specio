"""A colorimeter measurement refuses XYZ that is not three values."""

from __future__ import annotations

import numpy as np
import pytest

from specio.common import ColorimeterMeasurement
from specio.common.exceptions import MeasurementError


@pytest.mark.parametrize("XYZ", [[1.0, 2.0], [1.0, 2.0, 3.0, 4.0], [[1.0, 2.0, 3.0]]])
def test_xyz_that_is_not_three_values_is_refused(XYZ: list) -> None:
    """The check compared the array's size, an int, with a tuple, and built
    the error without raising it, so it never refused anything."""
    with pytest.raises(MeasurementError, match="XYZ"):
        ColorimeterMeasurement(XYZ, 0.0, "dev", no_compute=True)


def test_three_values_are_accepted() -> None:
    m = ColorimeterMeasurement([1.0, 2.0, 3.0], 0.0, "dev", no_compute=True)

    np.testing.assert_array_equal(m.XYZ, [1.0, 2.0, 3.0])
