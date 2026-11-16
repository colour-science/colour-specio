"""`specio.spectrometers` is where every spectroradiometer class is imported
from, and importing it raises no warning of its own."""

from __future__ import annotations

import subprocess
import sys


def test_every_spectroradiometer_is_exported() -> None:
    from specio import spectrometers
    from specio._device_implementations.konica_minolta import CS2000

    assert spectrometers.CS2000 is CS2000
    assert {"CRSpectrometer", "CS2000", "VirtualSpectrometer"} <= set(
        spectrometers.__all__
    )


def test_importing_the_namespace_raises_no_deprecation_warning() -> None:
    """The namespace imported a deprecated shim, so a caller running with
    warnings as errors could not import it at all. A fresh interpreter
    records every warning the import raises."""
    script = (
        "import warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import specio.spectrometers\n"
        "print([str(w.message) for w in caught"
        " if issubclass(w.category, DeprecationWarning)"
        " and 'specio' in w.filename + str(w.message)])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
