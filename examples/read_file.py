from pathlib import Path

from specio.serialization import csmf

p = Path("data/cmsf/ETC_Jan/C_QST_1920230231403.csmf")
data = csmf.load_csmf_file(p)
