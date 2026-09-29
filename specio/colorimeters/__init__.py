"""
Colorimeter device implementations.
"""

from specio._device_implementations.colorimetry_research import (
    CRColorimeter,
)
from specio._device_implementations.virtual import VirtualColorimeter

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CRColorimeter",
    "VirtualColorimeter",
]
