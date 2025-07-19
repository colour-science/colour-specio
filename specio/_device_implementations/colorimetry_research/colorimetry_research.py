"""
Colorimetry Research device implementations.

This module provides backwards compatibility imports. The implementation has been
refactored into separate modules for better organization and maintainability.

For new code, consider importing directly from:
- specio._device_implementations.colorimetry_research.CRColorimeter
- specio._device_implementations.colorimetry_research.CRSpectrometer
"""

import warnings

from ._common import (
    CommandError,
    CommandResponse,
    InstrumentType,
    Model,
    ResponseCode,
    ResponseType,
)
from ._cr_colorimeters import CRColorimeter
from ._cr_spectrometers import CRSpectrometer

# Issue deprecation warning for direct imports from this file
warnings.warn(
    "Direct imports from colorimetry_research.py are deprecated. "
    "Use imports from the colorimetry_research package instead.",
    DeprecationWarning,
    stacklevel=2,
)

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CRColorimeter",
    "CRSpectrometer",
    "CommandError",
    "CommandResponse",
    "InstrumentType",
    "Model",
    "ResponseCode",
    "ResponseType",
]
