from specio.serialization.protobuf import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TargetRGBSpace(_message.Message):
    __slots__ = ("gamut", "tf")
    class StandardTransferFunctions(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ST2084: _ClassVar[TargetRGBSpace.StandardTransferFunctions]
        BT1886: _ClassVar[TargetRGBSpace.StandardTransferFunctions]
        ITU_HLG: _ClassVar[TargetRGBSpace.StandardTransferFunctions]
    ST2084: TargetRGBSpace.StandardTransferFunctions
    BT1886: TargetRGBSpace.StandardTransferFunctions
    ITU_HLG: TargetRGBSpace.StandardTransferFunctions
    class Primaries(_message.Message):
        __slots__ = ("red", "green", "blue")
        RED_FIELD_NUMBER: _ClassVar[int]
        GREEN_FIELD_NUMBER: _ClassVar[int]
        BLUE_FIELD_NUMBER: _ClassVar[int]
        red: _common_pb2.xy_value
        green: _common_pb2.xy_value
        blue: _common_pb2.xy_value
        def __init__(self, red: _Optional[_Union[_common_pb2.xy_value, _Mapping]] = ..., green: _Optional[_Union[_common_pb2.xy_value, _Mapping]] = ..., blue: _Optional[_Union[_common_pb2.xy_value, _Mapping]] = ...) -> None: ...
    class TransferFunc(_message.Message):
        __slots__ = ("gamma", "standard")
        GAMMA_FIELD_NUMBER: _ClassVar[int]
        STANDARD_FIELD_NUMBER: _ClassVar[int]
        gamma: float
        standard: TargetRGBSpace.StandardTransferFunctions
        def __init__(self, gamma: _Optional[float] = ..., standard: _Optional[_Union[TargetRGBSpace.StandardTransferFunctions, str]] = ...) -> None: ...
    GAMUT_FIELD_NUMBER: _ClassVar[int]
    TF_FIELD_NUMBER: _ClassVar[int]
    gamut: TargetRGBSpace.Primaries
    tf: TargetRGBSpace.TransferFunc
    def __init__(self, gamut: _Optional[_Union[TargetRGBSpace.Primaries, _Mapping]] = ..., tf: _Optional[_Union[TargetRGBSpace.TransferFunc, _Mapping]] = ...) -> None: ...
