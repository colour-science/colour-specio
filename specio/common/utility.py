import re
from typing import Any

from colour.utilities import warning


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


class SpecioRuntimeWarning(Warning):
    """
    Define the base class of *Colour* runtime warnings.

    It is a subclass of the :class:`colour.utilities.ColourWarning` class.
    """


def specio_warning(*args: Any, **kwargs: Any):
    """
    Issue a specio runtime warning.

    Other Parameters
    ----------------
    args
        Arguments.
    kwargs
        Keywords arguments.

    Examples
    --------
    >>> usage_warning("This is a runtime warning!")  # doctest: +SKIP
    """

    kwargs["category"] = SpecioRuntimeWarning

    warning(*args, **kwargs)
