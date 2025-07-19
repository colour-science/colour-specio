# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Specio is a Python library for interacting with spectrometers and colorimeters, focusing on hardware instrument control for color measurement. The library is built around the colour-science library and provides:

- Spectrometer control (currently Colorimetry Research family, tested with CR300)
- Colorimeter support (Konica Minolta devices)
- Virtual instruments for testing and development
- Data serialization using Protocol Buffers (.csmf format)
- Color science calculations (XYZ, CCT, dominant wavelength, colorimetric purity)

## Development Commands

### Dependency Management
- `uv sync` - Install all dependencies including dev dependencies
- `uv add <package>` - Add new dependency
- `uv add --group dev <package>` - Add development dependency

### Code Quality and Linting
- `ruff check` - Run linting with Ruff
- `ruff format` - Format code with Ruff
- `ruff check --fix` - Auto-fix linting issues
- `pyright` - Type checking with Pyright

### Testing
- `pytest` - Run all tests
- `pytest -x` - Stop on first failure
- `pytest -xvs` - Verbose output, stop on first failure
- `pytest specio/serialization/tests/` - Run specific test directory
- `pytest specio/scripts/tests/test_csmf_anonymize.py` - Run specific test file

### Protocol Buffers
- `./scripts/build_proto.zsh` - Build protobuf files (requires protoc v27.0+)
- Generates `*_pb2.py` and `*_pb2.pyi` files in `specio/serialization/protobuf/`
- Protocol buffer definitions are in `specio/serialization/protobuf/*.proto`

### Scripts
- `csmf_doctor` - Diagnose and repair .csmf files
- `csmf_anonymize` - Anonymize measurement data in .csmf files

## Architecture

### Core Structure
- `specio/common/` - Base classes and interfaces for spectrometers and colorimeters
- `specio/_device_implementations/` - Hardware-specific implementations
- `specio/colorimeters/` - Colorimeter-specific functionality
- `specio/spectrometers/` - Spectrometer-specific functionality
- `specio/serialization/` - Data persistence using Protocol Buffers
- `specio/scripts/` - Command-line utilities

### Key Classes
- `SPDMeasurement` - Core spectral power distribution measurement class with color calculations
- `ColorimeterMeasurement` - Colorimeter measurement with XYZ values and derived calculations
- `VirtualSpectrometer` - Mock spectrometer for testing (generates semi-random SPDs)
- `VirtualColorimeter` - Mock colorimeter for testing

### Measurement Data Flow
1. Raw measurements from hardware (`RawSPDMeasurement`, `RawColorimeterMeasurement`)
2. Processed measurements with color calculations (`SPDMeasurement`, `ColorimeterMeasurement`)
3. Serialization to .csmf format using Protocol Buffers
4. Color science calculations using colour-science library

### Device Implementation Pattern
Device implementations in `_device_implementations/` follow a consistent pattern:
- Hardware communication via pyserial
- Command protocols specific to each manufacturer
- Raw measurement collection transformed to common measurement classes

## Important Configuration

### Code Style
- Line length: 88 characters (Ruff formatter)
- Import sorting with Ruff (trailing commas, known first-party)
- Numpy docstring convention
- Type hints required (checked with Pyright)

### Dependencies
- Python 3.13+ required
- Core: colour-science, numpy 2.x, pyserial, protobuf
- Dev tools: pytest, ruff, pyright, pre-commit, invoke