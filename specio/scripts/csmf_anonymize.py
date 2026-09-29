import argparse
import os
import sys
from pathlib import Path

from specio.common import get_valid_filename
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    load_csmf_file,
    save_csmf_file,
)


def main(*args: str) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="The csmf file to strip data from")

    parser.add_argument("-o", "--out-dir", help="Output directory", default=None)

    parsed_args = None if args == () else args
    parsed_args = parser.parse_args(parsed_args)

    file_path = Path(parsed_args.file)
    file_data = load_csmf_file(file_path)

    output_path = (
        file_path.parent if parsed_args.out_dir is None else Path(parsed_args.out_dir)
    )

    file_data.metadata = CSMF_Metadata(software="specio:csmf_anonymize")

    output_path = output_path.joinpath(
        get_valid_filename(file_data.shortname)
    ).with_suffix(".csmf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ml = CSMF_Data(
        test_colors=file_data.test_colors,
        measurements=file_data.measurements,
        metadata=file_data.metadata,
        order=file_data.order,
    )

    save_csmf_file(file=str(output_path), ml=ml)
    if args == ():
        output_path = output_path.relative_to(os.getcwd())
        sys.stdout.writelines(f"{output_path!s}")
    return output_path


if __name__ == "__main__":
    main()
