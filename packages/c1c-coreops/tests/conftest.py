from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve()
SRC = BASE.parents[1] / "src"
ROOT = BASE.parents[3]

for path in (SRC, ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
