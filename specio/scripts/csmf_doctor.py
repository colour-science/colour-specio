#!python3
"""
CSMF Doctor fixes some broken CSMF files by recalculating derived attributes.
"""
import argparse
import textwrap
from pathlib import Path

from specio.serialization import csmf


def main():
    parser = argparse.ArgumentParser(
        prog="CSMF Doctor",
        description=textwrap.dedent(
            """Read CSMF files and recompute derived data. Output to the same files.
            If a directory is given, all CSMF files will be procesed.
            """
        ),
    )

    parser.add_argument(
        "-r",
        action="store_true",
        help="""Recursive. If file is a directory, all subdirectories will be
            searched searched.""",
    )

    parser.add_argument(
        "file",
        default=".",
        help="""The file to recompute. If file is a directory, all CSMF files will
            be updated. See also -r""",
    )

    args = parser.parse_args()

    base = Path(args.file)

    if not base.exists():
        raise RuntimeError(f"File or Directory {base!s} does not exist.")

    if base.is_dir() and args.r:
        files = tuple(base.glob("**/*.csmf"))
    elif base.is_dir():
        files = tuple(base.glob("*.csmf"))
    else:
        files = (base,)

    if len(files) == 0:
        print("No csmf files found.")

    for file in files:
        print(f"Processing Next File: {file.name!s}")

        data = csmf.load_csmf_file(file, recompute=True)
        csmf.save_csmf_file(file, data)

    print("All files processed")


if __name__ == "__main__":
    main()
