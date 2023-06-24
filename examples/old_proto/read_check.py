from pathlib import Path
from specio import fileio
import os

os.chdir(Path(__file__).parent)

data = fileio.load_measurements("ex_file.csmf")

pass
