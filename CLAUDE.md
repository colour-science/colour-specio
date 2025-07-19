# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Specio is a Python library for interacting with spectrometers and colorimeters,
focusing on hardware instrument control for color measurement. The library is
built around the colour-science library and provides:

- Spectrometer control (currently Colorimetry Research family, tested with
  CR300)
- Colorimeter support (Konica Minolta devices)
- Virtual instruments for testing and development
- Data serialization using Protocol Buffers (.csmf format)
- Color science calculations (XYZ, CCT, dominant wavelength, colorimetric
  purity)

## Development Commands

### Dependency Management

- `uv sync` - Install all dependencies including dev dependencies
- `uv add <package>` - Add new dependency
- `uv add --group dev <package>` - Add development dependency

### Code Quality and Linting

- `uv run invoke ai-quality` - Comprehensive quality checks for AI agents
  (formats, fixes linting, type checks, spell checks)
- `uv run invoke ai-quality <target>` - Run quality checks on specific files or
  directories
- `ai-quality` MUST pass. If it fails, and the failures are deemed acceptable
  then comments must be added to the code to allow the quality checks to pass.
  Only create exceptions for quality checks when necessary and justified.
- **CRITICAL**: Before completing any task, ALWAYS run `uv run invoke ai-quality`
  and fix ALL issues including formatting, linting, type checking, AND spelling.
  No exceptions.
- When importing library objects, import them from public modules. Only use
  private `_name` modules when absolutely necessary.

#### Quality Requirements

1. **Formatting**: Code must be formatted with Ruff (88 char line length)
2. **Linting**: All Ruff linting rules must pass
3. **Type Checking**: Pyright must report 0 errors, 0 warnings, 0 information
4. **Spelling**: CSpell must find 0 spelling errors
   - Fix genuine typos in code and comments
   - Add legitimate technical terms to `cspell.json` in the `words` array
   - Common technical terms already included: colour, numpy, protoc, etc.
5. **No Duplicate Configuration**: Avoid duplicate keys in pyproject.toml

#### Self Documenting Code

All python functions should have doc strings, type annotations, and return
types. Do not use overly complicated types. Use numpy types when applicable,
i.e. `npt.ArrayLike`

### Protocol Buffers

- `uv run invoke build-proto` - Build protobuf files (requires protoc v27.0+)
- Generates `*_pb2.py` and `*_pb2.pyi` files in `specio/serialization/protobuf/`
- Protocol buffer definitions are in `specio/serialization/protobuf/*.proto`

### Scripts

- `uv run csmf_doctor` - Diagnose and repair .csmf files
- `uv run csmf_anonymize` - Anonymize measurement data in .csmf files

## Architecture

### Core Structure

- `specio/common/` - Base classes and interfaces for spectrometers and
  colorimeters
- `specio/_device_implementations/` - Hardware-specific implementations
- `specio/colorimeters/` - Colorimeter-specific functionality
- `specio/spectrometers/` - Spectrometer-specific functionality
- `specio/serialization/` - Data persistence using Protocol Buffers
- `specio/scripts/` - Command-line utilities

### Key Classes

- `SPDMeasurement` - Core spectral power distribution measurement class with
  color calculations
- `ColorimeterMeasurement` - Colorimeter measurement with XYZ values and derived
  calculations
- `VirtualSpectrometer` - Mock spectrometer for testing (generates semi-random
  SPDs)
- `VirtualColorimeter` - Mock colorimeter for testing

### Measurement Data Flow

1. Raw measurements from hardware (`RawSPDMeasurement`,
   `RawColorimeterMeasurement`)
2. Processed measurements with color calculations (`SPDMeasurement`,
   `ColorimeterMeasurement`)
3. Serialization to .csmf format using Protocol Buffers
4. Color science calculations using colour-science library

### Device Implementation Pattern

Device implementations in `_device_implementations/` follow a consistent
pattern:

- Hardware communication via pyserial
- Command protocols specific to each manufacturer
- Raw measurement collection transformed to common measurement classes

## Important Configuration

### Code Style

- Line length: 88 characters (Ruff formatter)
- Import sorting with Ruff (trailing commas, known first-party)
- Numpy docstring convention
- Type hints required (checked with Pyright)
- Empty lines should never have whitespace

### Dependencies

- Python 3.13+ required
- Core: colour-science, numpy 2.x, pyserial, protobuf
- Dev tools: pytest, ruff, pyright, pre-commit, invoke

## Claude Instructions

Unless auto accept edits is on, you will always use the "edit" function to allow
the user to manually approve changes to the code.
