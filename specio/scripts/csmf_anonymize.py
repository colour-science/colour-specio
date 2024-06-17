import argparse
from pathlib import Path

from specio import get_valid_filename
from specio.serialization.csmf import (
    MeasurementList,
    MeasurementListNotes,
    load_csmf_file,
    save_csmf_file,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="The csmf file to strip data from")

    parser.add_argument("-o", "--out-dir", help="Output directory", default=None)

    args = parser.parse_args()

    file_path = Path(args.file)
    file_data = load_csmf_file(file_path)

    output_path = file_path.parent if args.out_dir is None else Path(args.out_dir)

    file_data.metadata = MeasurementListNotes(software="colour-workbench file stripper")

    output_path = output_path.joinpath(
        get_valid_filename(file_data.shortname)
    ).with_suffix(".csmf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving anonymized data: {output_path!s} <- {file_path!s}")

    ml = MeasurementList(
        test_colors=file_data.test_colors,
        measurements=file_data.measurements,
        metadata=file_data.metadata,
        order=file_data.order,
    )

    save_csmf_file(file=str(output_path), ml=ml)


if __name__ == "__main__":
    main()
