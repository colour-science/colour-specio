import os
from pathlib import Path

from specio.serialization import csmf

os.chdir(Path(__file__).parent)

data = csmf.load_csmf_file("ex_file.csmf")
