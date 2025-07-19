"""
Shared measurement processing utilities for colorimeters and spectrometers.
"""

import textwrap
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import numpy as np
from colour.colorimetry.dominant import (
    colorimetric_purity,
    dominant_wavelength,
)
from colour.models.cie_xyy import XYZ_to_xy

from .exceptions import MeasurementError

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "BaseMeasurement",
    "compute_color_properties",
    "validate_repetitions",
]


def validate_repetitions(repetitions: int) -> None:
    """
    Validate that repetitions parameter is valid.

    Parameters
    ----------
    repetitions : int
        Number of repetitions to validate.

    Raises
    ------
    MeasurementError
        If repetitions is less than 1.
    """
    if repetitions < 1:
        raise MeasurementError("Repetitions must be greater than 1")


def compute_color_properties(XYZ: np.ndarray) -> dict[str, Any]:
    """
    Compute common color properties from XYZ tristimulus values.

    Parameters
    ----------
    XYZ : np.ndarray
        CIE 1931 XYZ tristimulus values.

    Returns
    -------
    dict[str, Any]
        Dictionary containing computed color properties:
        - xy: CIE 1931 xy chromaticity coordinates
        - dominant_wl: Dominant wavelength in nm
        - purity: Colorimetric purity (0-1)
        - time: Measurement timestamp
    """
    xy = XYZ_to_xy(XYZ)
    dominant_wl = float(dominant_wavelength(xy, [1 / 3, 1 / 3])[0])
    purity = colorimetric_purity(xy, (1 / 3, 1 / 3))
    time = datetime.now().astimezone()

    return {
        "xy": xy,
        "dominant_wl": dominant_wl,
        "purity": purity,
        "time": time,
    }


class BaseMeasurement(ABC):
    """
    Base class for measurement objects with common functionality.
    """

    # Declare attributes that all measurement classes should have
    XYZ: np.ndarray
    xy: np.ndarray
    time: Any
    cct: float
    duv: float
    dominant_wl: float
    purity: float
    exposure: float

    def __eq__(self, other: object) -> bool:
        """
        Check equality between measurement objects.

        Parameters
        ----------
        other : object
            Object to compare with this measurement.

        Returns
        -------
        bool
            True if all measurement attributes are equal, False otherwise.
        """
        if not isinstance(other, self.__class__):
            return False

        # Get comparison keys from subclass
        keys = self._get_comparison_keys()
        bools = []

        for key in keys:
            self_val = getattr(self, key)
            other_val = getattr(other, key)

            # Handle numpy arrays specially
            if isinstance(self_val, np.ndarray):
                bools.append(np.allclose(self_val, other_val))
            else:
                bools.append(self_val == other_val)

        return all(bools)

    def _format_measurement_string(
        self,
        measurement_type: str,
        device_id: str,
        additional_lines: list[str] | None = None,
    ) -> str:
        """
        Format measurement data into a readable string.

        Parameters
        ----------
        measurement_type : str
            Type of measurement (e.g., "Spectral", "Colorimeter").
        device_id : str
            Device identifier.
        additional_lines : list[str] | None
            Additional formatted lines to include.

        Returns
        -------
        str
            Formatted measurement string.
        """
        lines = [
            f"{measurement_type} Measurement - {device_id}:",
            f"    time: {self.time}",
            f"    XYZ: {np.array2string(self.XYZ, formatter={'float_kind': lambda x: f'{x:.4f}'})}",
            f"    xy: {np.array2string(self.xy, formatter={'float_kind': lambda x: f'{x:.4f}'})}",
            f"    CCT: {self.cct:.0f} ± {self.duv:.5f}",
            f"    Dominant WL: {self.dominant_wl:.1f} @ {self.purity * 100:.1f}%",
            f"    Exposure: {self.exposure:.3f}",
        ]

        if additional_lines:
            # Insert additional lines before the exposure line
            lines = lines[:-1] + additional_lines + [lines[-1]]

        return textwrap.dedent("\n" + "\n".join(lines) + "\n")

    @abstractmethod
    def _get_comparison_keys(self) -> list[str]:
        """
        Get list of attribute names to use for equality comparison.

        Returns
        -------
        list[str]
            List of attribute names for comparison.
        """
        pass
