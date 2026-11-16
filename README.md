# Colour - Specio

Colour - Specio connects Python to spectroradiometers and colorimeters. It
discovers an instrument on a serial port, triggers measurements, and returns
each one with its colorimetry computed by
[Colour](https://github.com/colour-science/colour): CIE XYZ, chromaticity,
correlated colour temperature, and, from a spectroradiometer, the spectral
distribution. Measurement sets save to and load from CSMF, a measurement file
format built on Protocol Buffers.

The distribution is `colour-specio`, and the package imports as `specio`.

## Features

| Instrument | Kind | Class |
| --- | --- | --- |
| Colorimetry Research CR-250, CR-300 | Spectroradiometer | `specio.spectrometers.CRSpectrometer` |
| Colorimetry Research CR-120 | Colorimeter | `specio.colorimeters.CRColorimeter` |
| Konica Minolta CS-2000 | Spectroradiometer | `specio.konica_minolta.CS2000` |
| Konica Minolta CA-410 | Display colour analyzer | `specio.colorimeters.CA410` |
| Virtual spectroradiometer | Semi-random spectral distributions | `specio.spectrometers.VirtualSpectrometer` |
| Virtual colorimeter | Semi-random XYZ | `specio.colorimeters.VirtualColorimeter` |

The virtual instruments measure without hardware, for tests and for code
written before an instrument is at hand.

## Installation

Colour - Specio requires Python 3.13 or 3.14 and Colour 0.4.7 or later.

```bash
pip install colour-specio
```

## Usage

Each instrument class finds a connected device with `discover()`. Its
`measure()` returns a measurement with `XYZ`, `xy`, `cct` and `duv`; a
spectroradiometer's measurement also carries `spd`, the spectral
distribution.

```python
from specio.spectrometers import CRSpectrometer

spectrometer = CRSpectrometer.discover()
measurement = spectrometer.measure()

print(measurement.XYZ, measurement.xy, measurement.cct)
```

`measure(repetitions=3)` averages several readings into one. The
[examples](examples) folder has a script for the CR-300, the CR-120, the
CA-410 and the virtual instruments.

### Instrument settings

Instruments store their measurement settings, such as speed and sync mode,
and several keep them across power cycles, so a setting left by one session
applies to the next. When a measurement set starts, set the settings it
depends on, or read them and record them with the data.

| Instrument | Settings kept across power cycles |
| --- | --- |
| Konica Minolta CS-2000 | Speed mode and sync mode, in flash memory. Each change writes to flash, which tolerates a limited number of writes. |
| Colorimetry Research | Not documented. `CRSpectrometer` sets its measurement speed when it connects, `NORMAL` by default. |

### Measurement files

`specio.serialization` saves a measurement set as a CSMF file and loads it
back. A `CSMF_Data` holds the measurements, the test colours they measured,
the order they were measured in, and metadata such as notes and author.

```python
from specio.serialization import load_csmf_file, save_csmf_file

path = save_csmf_file("session", data)
data = load_csmf_file(path)
```

Two command-line tools work on CSMF files:

- `csmf_doctor FILE` recomputes the derived colorimetry in a file, or in every
  file in a directory, with `-r` to search subdirectories too.
- `csmf_anonymize FILE` writes a copy named by a hash of its rows, without
  the notes, author, location and ancillary bytes.

## Development

The project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run pyright
uv run pre-commit run --all-files
```

`uv run invoke build-proto` regenerates the Python modules from the `.proto`
definitions in `specio/serialization/protobuf`.

## Contributing

If you would like to contribute to
[Colour - Specio](https://github.com/colour-science/colour-specio), please
refer to the following [Contributing](https://www.colour-science.org/contributing/)
guide for Colour.

## Code of Conduct

The _Code of Conduct_, adapted from the
[Contributor Covenant 1.4](https://www.contributor-covenant.org/version/1/4/code-of-conduct.html),
is available on the
[Code of Conduct](https://www.colour-science.org/code-of-conduct/) page.

## Contact & Social

The _Colour Developers_ can be reached via different means:

- [Email](mailto:colour-developers@colour-science.org)
- [Facebook](https://www.facebook.com/python.colour.science)
- [Gitter](https://gitter.im/colour-science/colour)
- [Issues](https://github.com/colour-science/colour-specio/issues)

## About

**Colour - Specio** by Colour Developers\
Copyright 2013 Colour Developers – [colour-developers@colour-science.org](mailto:colour-developers@colour-science.org)\
This software is released under terms of BSD-3-Clause: <https://opensource.org/licenses/BSD-3-Clause>\
<https://github.com/colour-science/colour-specio>
