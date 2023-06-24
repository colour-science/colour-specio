from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SpectralShape(_message.Message):
    __slots__ = ["start", "end", "step"]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    start: float
    end: float
    step: float
    def __init__(self, start: _Optional[float] = ..., end: _Optional[float] = ..., step: _Optional[float] = ...) -> None: ...

class SpectralDistribution(_message.Message):
    __slots__ = ["shape", "values", "values_old", "name"]
    SHAPE_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    VALUES_OLD_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    shape: SpectralShape
    values: _containers.RepeatedScalarFieldContainer[float]
    values_old: _containers.RepeatedScalarFieldContainer[float]
    name: str
    def __init__(self, shape: _Optional[_Union[SpectralShape, _Mapping]] = ..., values: _Optional[_Iterable[float]] = ..., values_old: _Optional[_Iterable[float]] = ..., name: _Optional[str] = ...) -> None: ...

class XYZ_value(_message.Message):
    __slots__ = ["X", "Y", "Z"]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    X: float
    Y: float
    Z: float
    def __init__(self, X: _Optional[float] = ..., Y: _Optional[float] = ..., Z: _Optional[float] = ...) -> None: ...

class xy_value(_message.Message):
    __slots__ = ["x", "y"]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...

class cct_value(_message.Message):
    __slots__ = ["cct", "duv"]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DUV_FIELD_NUMBER: _ClassVar[int]
    cct: float
    duv: float
    def __init__(self, cct: _Optional[float] = ..., duv: _Optional[float] = ...) -> None: ...

class Timestamp(_message.Message):
    __slots__ = ["timestr"]
    TIMESTR_FIELD_NUMBER: _ClassVar[int]
    timestr: str
    def __init__(self, timestr: _Optional[str] = ...) -> None: ...

class Measurement(_message.Message):
    __slots__ = ["spd", "exposure", "XYZ", "xy", "cct", "dominant_wl", "power", "spectrometer_id", "time"]
    SPD_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_FIELD_NUMBER: _ClassVar[int]
    XYZ_FIELD_NUMBER: _ClassVar[int]
    XY_FIELD_NUMBER: _ClassVar[int]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DOMINANT_WL_FIELD_NUMBER: _ClassVar[int]
    POWER_FIELD_NUMBER: _ClassVar[int]
    SPECTROMETER_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    spd: SpectralDistribution
    exposure: float
    XYZ: XYZ_value
    xy: xy_value
    cct: cct_value
    dominant_wl: float
    power: float
    spectrometer_id: str
    time: Timestamp
    def __init__(self, spd: _Optional[_Union[SpectralDistribution, _Mapping]] = ..., exposure: _Optional[float] = ..., XYZ: _Optional[_Union[XYZ_value, _Mapping]] = ..., xy: _Optional[_Union[xy_value, _Mapping]] = ..., cct: _Optional[_Union[cct_value, _Mapping]] = ..., dominant_wl: _Optional[float] = ..., power: _Optional[float] = ..., spectrometer_id: _Optional[str] = ..., time: _Optional[_Union[Timestamp, _Mapping]] = ...) -> None: ...

class MeasurementList(_message.Message):
    __slots__ = ["measurements", "test_colors", "order", "notes", "author", "location", "software", "ancillary"]
    class TestColor(_message.Message):
        __slots__ = ["c", "f"]
        C_FIELD_NUMBER: _ClassVar[int]
        F_FIELD_NUMBER: _ClassVar[int]
        c: _containers.RepeatedScalarFieldContainer[int]
        f: _containers.RepeatedScalarFieldContainer[float]
        def __init__(self, c: _Optional[_Iterable[int]] = ..., f: _Optional[_Iterable[float]] = ...) -> None: ...
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    TEST_COLORS_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SOFTWARE_FIELD_NUMBER: _ClassVar[int]
    ANCILLARY_FIELD_NUMBER: _ClassVar[int]
    measurements: _containers.RepeatedCompositeFieldContainer[Measurement]
    test_colors: _containers.RepeatedCompositeFieldContainer[MeasurementList.TestColor]
    order: _containers.RepeatedScalarFieldContainer[int]
    notes: str
    author: str
    location: str
    software: str
    ancillary: bytes
    def __init__(self, measurements: _Optional[_Iterable[_Union[Measurement, _Mapping]]] = ..., test_colors: _Optional[_Iterable[_Union[MeasurementList.TestColor, _Mapping]]] = ..., order: _Optional[_Iterable[int]] = ..., notes: _Optional[str] = ..., author: _Optional[str] = ..., location: _Optional[str] = ..., software: _Optional[str] = ..., ancillary: _Optional[bytes] = ...) -> None: ...
