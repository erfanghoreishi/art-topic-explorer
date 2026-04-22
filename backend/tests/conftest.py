from __future__ import annotations

import sys
from pathlib import Path


# Ensure imports like `from backend.src import ...` work when running pytest.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

