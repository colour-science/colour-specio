# Developer Guide

## Build protobufs

The protobuf code needs to be generated every time you change definitions in
protobuf.

Step 1: Install protobuf on your machine

Step 2: Build protobufs, this builds them for python

`protoc --proto_path=protobuf --python_out=specio/protobuf --pyi_out=specio/protobuf protobuf/measurements.proto `

### Optional Steps

Make your python IDE aware of the type hinting in typeings
