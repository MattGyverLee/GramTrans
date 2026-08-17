"""GramTrans standalone Windows host shell (feature 034).

This subpackage supplies the four things the FlexTools host supplies today —
an open source project, a report sink, the ``modifyAllowed`` flag, and a run
wrapper — so a machine with FieldWorks 9 but no FlexTools can run the same
transfer. The transfer engine and the selection wizard are reused as-is.

**Import direction is one-way and load-bearing** (FR-016). Modules here may
import ``gramtrans.gramtrans`` and ``gramtrans.Lib.*``; nothing under
``gramtrans.py`` or ``Lib/`` may import ``gramtrans.standalone``. That
direction is what keeps the FlexTools path provably unchanged, and
``tests/unit/test_034_flextools_contract.py`` asserts it by AST scan.

For the same reason this module deliberately exports nothing and imports
nothing at module scope: the package must be importable (and the ban test
must be able to walk it) without dragging in PyQt6, flexicon, or the engine.
Entry point: ``python -m gramtrans.standalone`` (see ``__main__.py``).
"""
