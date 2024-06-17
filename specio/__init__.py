"""
Specio
======
Provides support for interacting with various hardware spectrometers.
"""

__version__ = "0.2.9"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


import re

from specio.colorimeters.common import (
    ColorimeterMeasurement,
    VirtualColorimeter,
)

from .spectrometers.common import (
    SPDMeasurement,
    VirtualSpectrometer,
)

__all__ = [
    "SPDMeasurement",
    "VirtualSpectrometer",
    "ColorimeterMeasurement",
    "VirtualColorimeter",
    "SuspiciousFileOperationError",
    "get_valid_filename",
]


class SuspiciousFileOperationError(Exception):
    """Generated when a user does something suspicious with file names"""


def get_valid_filename(name: str) -> str:
    """Clean / validate filename string

    Parameters
    ----------
    name : str
        The string to be cleaned for file name validity

    Returns
    -------
    str
        A clean filename

    Raises
    ------
    SuspiciousFileOperation
        if the cleaned string looks like a spooky filepath (i.e. '/', '.', etc...)
    """
    s = str(name).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    s = re.sub(r"_+-+_+", "__", s)
    if s in {"", ".", ".."}:
        raise SuspiciousFileOperationError(f"Could not derive file name from '{name}'")
    return s


def _config__specio_logger() -> None:
    """
    Configure the default specio logger "specio"
    """
    import logging

    log = logging.getLogger("specio")

    stream_handler = logging.StreamHandler()
    stream_handler.formatter = logging.Formatter(
        fmt="[%(asctime)s.%(msecs)d] %(levelname)s - %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log.addHandler(stream_handler)


_config__specio_logger()
