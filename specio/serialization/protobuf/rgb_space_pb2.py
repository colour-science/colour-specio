# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: specio/serialization/protobuf/rgb_space.proto
# Protobuf Python Version: 5.27.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    0,
    '',
    'specio/serialization/protobuf/rgb_space.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from specio.serialization.protobuf import common_pb2 as specio_dot_serialization_dot_protobuf_dot_common__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n-specio/serialization/protobuf/rgb_space.proto\x12\x0cspecio.proto\x1a*specio/serialization/protobuf/common.proto\"\xb8\x03\n\x0eTargetRGBSpace\x12\x35\n\x05gamut\x18\x01 \x01(\x0b\x32&.specio.proto.TargetRGBSpace.Primaries\x12\x35\n\x02tf\x18\x02 \x01(\x0b\x32).specio.proto.TargetRGBSpace.TransferFunc\x1a}\n\tPrimaries\x12#\n\x03red\x18\x01 \x01(\x0b\x32\x16.specio.proto.xy_value\x12%\n\x05green\x18\x02 \x01(\x0b\x32\x16.specio.proto.xy_value\x12$\n\x04\x62lue\x18\x03 \x01(\x0b\x32\x16.specio.proto.xy_value\x1aw\n\x0cTransferFunc\x12\x0f\n\x05gamma\x18\x01 \x01(\x01H\x00\x12J\n\x08standard\x18\x02 \x01(\x0e\x32\x36.specio.proto.TargetRGBSpace.StandardTransferFunctionsH\x00\x42\n\n\x08\x66unction\"@\n\x19StandardTransferFunctions\x12\n\n\x06ST2084\x10\x00\x12\n\n\x06\x42T1886\x10\x01\x12\x0b\n\x07ITU_HLG\x10\x02\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'specio.serialization.protobuf.rgb_space_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_TARGETRGBSPACE']._serialized_start=108
  _globals['_TARGETRGBSPACE']._serialized_end=548
  _globals['_TARGETRGBSPACE_PRIMARIES']._serialized_start=236
  _globals['_TARGETRGBSPACE_PRIMARIES']._serialized_end=361
  _globals['_TARGETRGBSPACE_TRANSFERFUNC']._serialized_start=363
  _globals['_TARGETRGBSPACE_TRANSFERFUNC']._serialized_end=482
  _globals['_TARGETRGBSPACE_STANDARDTRANSFERFUNCTIONS']._serialized_start=484
  _globals['_TARGETRGBSPACE_STANDARDTRANSFERFUNCTIONS']._serialized_end=548
# @@protoc_insertion_point(module_scope)
