# Colorimetry Research Device Refactoring Plan

## Current State
- Single file: `specio/_device_implementations/_colorimetry_research/colorimetry_research.py`
- Two main classes: `CRSpectrometer` and `CRColorimeter`
- Significant code duplication between the two classes

## Detailed Code Duplication Analysis

### Identical Methods (100% duplicated):
1. **`__clear_buffer(self) -> None`** - Lines ~432-443 (CRSpectrometer) and ~914-925 (CRColorimeter)
   - Identical implementation for clearing serial buffer
   - Same timeout logic and port operations

2. **`_write_cmd(self, command: str) -> CommandResponse`** - Lines ~445-487 (CRSpectrometer) and ~927-969 (CRColorimeter)
   - Identical command sending logic
   - Same timeout handling, buffer clearing, response parsing
   - Only difference: docstring mentions "spectrometer" vs "colorimeter"

3. **`_parse_response(self, data: bytes) -> CommandResponse`** - Lines ~489-512 (CRSpectrometer) and ~971-994 (CRColorimeter)
   - 100% identical response parsing logic
   - Same argument handling and CommandResponse creation

### Nearly Identical Properties:
4. **`manufacturer`** - Lines ~304-306 (CRSpectrometer) and ~693-695 (CRColorimeter)
   - Identical: Returns "Colorimetry Research"

5. **`firmware`** - Lines ~308-318 (CRSpectrometer) and ~697-708 (CRColorimeter)
   - Identical: RC Firmware command, caching logic

6. **`serial_number`** - Lines ~351-361 (CRSpectrometer) and ~719-729 (CRColorimeter)
   - Identical: RC ID command, caching logic

7. **`model`** - Lines ~374-384 (CRSpectrometer) and ~844-854 (CRColorimeter)
   - Identical: RC Model command with @cached_property

8. **`aperture`** - Lines ~356-373 (CRSpectrometer) and ~699-716 (CRColorimeter)
   - Identical: RS Aperture command, caching logic
   - Only difference: docstring mentions "spectrometer" vs "colorimeter"

9. **`instrument_type`** - Lines ~410-430 (CRSpectrometer) and ~892-912 (CRColorimeter)
   - Identical logic, different expected return value (SPECTRORADIOMETER vs COLORIMETER)

10. **`average_samples` (getter/setter)** - Lines ~363-372 (CRSpectrometer) and ~855-890 (CRColorimeter)
    - Identical: RS ExposureX query and SM ExposureX setting
    - Same clamping logic (1-50 range)

### Identical Discovery Logic:
11. **`discover()` classmethod** - Lines ~217-275 (CRSpectrometer) and ~608-666 (CRColorimeter)
    - 95% identical platform-specific port discovery
    - Same serial port probing logic
    - Only difference: instrument type check (InstrumentType:2 vs InstrumentType:1)

### Identical Constructor Patterns:
12. **`__init__`** - Lines ~277-301 (CRSpectrometer) and ~658-679 (CRColorimeter)
    - Same serial port setup with _CR_SERIAL_KWARGS
    - Same __last_cmd_time initialization
    - CRColorimeter adds _warn_filter_selection() call

### Shared Constants and Types:
- `_COMMAND_TIMEOUT`, `_DEFAULT_SERIAL_TIMEOUT`, `_CR_SERIAL_KWARGS`
- `InstrumentType`, `Model`, `ResponseType`, `ResponseCode`, `CommandResponse`, `CommandError`
- All imports and dependencies

## Device-Specific Functionality

### CRSpectrometer Only:
- `MeasurementSpeed` enum
- `measurement_speed` property (getter/setter)
- `_apply_measurementspeed_timeout()` method
- `_raw_measure()` returns `RawSPDMeasurement` with spectral data

### CRColorimeter Only:
- `available_filters`, `current_filters`, `current_filters_names` properties
- `_warn_filter_selection()` method
- `_raw_measure()` returns `RawColorimeterMeasurement` with XYZ data

## Proposed Refactoring Structure

```
_colorimetry_research/
├── __init__.py                 # Public API exports
├── _common.py                  # Shared base class and utilities
├── _cr_spectrometers.py       # CRSpectrometer implementation
├── _cr_colorimeters.py        # CRColorimeter implementation
└── colorimetry_research.py    # (deprecated/backwards compatibility)
```

### 1. _common.py Contents:
- All shared enums: `InstrumentType`, `Model`, `ResponseType`, `ResponseCode`
- `CommandResponse`, `CommandError` classes
- `CRDeviceBase` abstract base class with:
  - All shared properties and methods
  - Parameterized discovery logic
  - Common serial communication infrastructure
- Constants: `_COMMAND_TIMEOUT`, `_DEFAULT_SERIAL_TIMEOUT`, `_CR_SERIAL_KWARGS`

### 2. _cr_spectrometers.py Contents:
- `CRSpectrometer` class inheriting from `CRDeviceBase`
- `MeasurementSpeed` enum
- Spectrometer-specific measurement logic

### 3. _cr_colorimeters.py Contents:
- `CRColorimeter` class inheriting from `CRDeviceBase`
- Colorimeter-specific filter management
- Colorimeter-specific measurement logic

### 4. __init__.py Contents:
- Import and export all public classes and functions
- Maintain backward compatibility

## Implementation Benefits:
- Reduce ~400 lines of duplicated code to ~150 lines
- Centralize serial communication logic
- Easier maintenance and bug fixes
- Cleaner separation of concerns
- Foundation for future CR device types
- Preserve all existing APIs and functionality