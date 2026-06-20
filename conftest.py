"""Pytest configuration: add `src/` to sys.path so `import gramtrans` works
without an editable install in the host environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
