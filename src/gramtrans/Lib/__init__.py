"""GramTrans helper modules.

Loaded by `src/gramtrans/gramtrans.py` via `site.addsitedir(r"Lib")` per the
FLExTrans module convention. Modules:

- ``models``   — data-model dataclasses + enums (E1-E6)
- ``residue``  — Import Residue tag + dual-carrier dispatchers (E5 / FR-010)
- ``report``   — RunReport aggregation + snapshot JSON
- ``preview``  — plan builder (Principle III — never mutates target)
- ``transfer`` — plan executor (Move Mode writes)
- ``ui``       — PyQt widgets

The helpers inside this directory use ``__package__``-aware imports
(`from .models import ...` when loaded as part of `gramtrans.Lib`, or
`from models import ...` when loaded via `site.addsitedir(Lib)` from
`gramtrans.py`). Both contexts resolve to the same module instance — there
is NO sys.path manipulation in this `__init__.py` to avoid double-loading
helpers under two names (top-level `models` and `gramtrans.Lib.models`).
"""
