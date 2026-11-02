"""Issue #187 -- `_resolve_target_lex_ref_type` no longer exposes `allow_create`.

Move creates missing relation types only through `_create_target_lex_ref_type`
inside `_evaluate_lexical_relation` (issue #163). The duplicate create leg on
the resolver was dead in production and is removed.
"""
from __future__ import annotations

from pathlib import Path


def test_issue187_no_allow_create_keyword_in_production_resolver():
    categories_py = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "gramtrans"
        / "Lib"
        / "categories.py"
    )
    text = categories_py.read_text(encoding="utf-8")
    _, after_def = text.split("def _resolve_target_lex_ref_type", 1)
    signature = after_def.split('"""', 1)[0]
    assert "allow_create" not in signature
