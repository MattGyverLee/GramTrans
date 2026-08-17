"""Pytest configuration: add `src/` to sys.path so `import gramtrans` works
without an editable install in the host environment.

Also adds `tests/unit` to sys.path so helper modules (e.g. _fakes_affix)
can be imported directly by test files without a package structure.

Finally, pins the interface theme off for the whole suite -- see the comment on
`GRAMTRANS_NO_THEME` below.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_TESTS_UNIT = Path(__file__).parent / "tests" / "unit"
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

# Keep the interface theme (Lib/ui/theme.py) out of the test session.
#
# `SelectionWizard.__init__` calls `install_theme()`, which mutates the SHARED
# QApplication palette, style and font -- and restores whatever text size the
# developer last picked in the real GUI from QSettings. Without this pin, a
# developer who had scaled the interface to 160% would run a different suite
# from CI: every Qt widget's font, and therefore any geometry-sensitive
# assertion, would shift under them. `install()` honours GRAMTRANS_NO_THEME by
# returning False and leaving the palette untouched, so wizard-construction
# tests stay hermetic.
#
# `setdefault`, not a plain assignment: `GRAMTRANS_NO_THEME=0` in the
# environment still lets someone deliberately run the suite themed. The theme's
# own tests do not need this off -- they exercise an un-installed ThemeManager.
os.environ.setdefault("GRAMTRANS_NO_THEME", "1")
