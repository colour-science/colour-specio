"""
Hardware device implementations for specio.
"""

from . import konica_minolta
from .colorimetry_research import colorimetry_research

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "colorimetry_research",
    "konica_minolta",
]
