# Specio

Specio is a python library for interacting with spectrometers. Currently only
the Colorimetry Research family is supported, and particularly this library is
tested and maintained with a CR300.

This library also provides a virtual spectrometer which provides semi-random
SPDs as measurements.

## Usage

See Examples Folder

## Instrument settings

Instruments store their measurement settings, such as speed and sync mode,
and several keep them across power cycles, so a setting left by one session
applies to the next. When a measurement set starts, set the settings it
depends on, or read them and record them with the data.

| Instrument | Settings kept across power cycles |
|---|---|
| Konica Minolta CS-2000 | Speed mode and sync mode, in flash memory. Each change writes to flash, which tolerates a limited number of writes. |
| Colorimetry Research | Not documented. `CRSpectrometer` sets its measurement speed when it connects, `NORMAL` by default. |
