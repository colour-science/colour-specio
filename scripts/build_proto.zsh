#! zsh
# Intended to be run on mac, verified against protoc v27.0
protoc --python_out=. --pyi_out=. specio/**/*.proto