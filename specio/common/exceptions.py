"""
Centralized exception handling for specio.
"""

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "DeviceError",
    "MeasurementError",
    "SpecioError",
    "SuspiciousFileOperationError",
]


class SpecioError(Exception):
    """Base exception class for all specio-related errors."""


class MeasurementError(SpecioError):
    """Raised when measurement data is invalid or processing fails."""


class DeviceError(SpecioError):
    """Raised when device communication or operation fails."""


class SuspiciousFileOperationError(SpecioError):
    """Raised when a user attempts suspicious file operations."""
