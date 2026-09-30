"""
Photo Research device implementations.
"""

from ._common import PRCommandError, PRCommandResponse, PRDeviceBase, PRResponseCode
from ._pr_spectrometers import PRSpectrometer

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "PRCommandError",
    "PRCommandResponse",
    "PRDeviceBase",
    "PRResponseCode",
    "PRSpectrometer",
]
