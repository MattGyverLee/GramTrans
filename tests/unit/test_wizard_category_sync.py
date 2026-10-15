"""Issue #39: the Selection-UI category sets must not drift from models.py.

Coverage Part B added FEATURE_STRUCT_TYPES, POS_INFLECTABLE_FEATS and
PHON_FEAT_TYPES (plus complex/open INFLECTION_FEATURES handling) to the engine,
registry, dispatch tuples and conflict-mode/GOLD sets, but the wizard's
`_SCHEMA_CATEGORIES` and its `_GOLD_RESERVED` mirror were hand-copied lists
that nobody updated. These tests pin them to models.py, which is
authoritative.

models.py keeps its Layer-1 kind buckets as locals inside
`_build_default_conflict_modes`, and both MULTI_INSTANCE and GOLD_RESERVED
resolve to ConflictMode.UPDATE, so the buckets cannot be told apart at runtime.
The sets are therefore read from the function's source with `ast`.
"""
from __future__ import annotations

import ast
import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from gramtrans.Lib import models  # noqa: E402
from gramtrans.Lib.models import GrammarCategory  # noqa: E402
from gramtrans.Lib.ui import main_window, selection_wizard, wizard_pages_deferred  # noqa: E402

_PART_B = {
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.FEATURE_STRUCT_TYPES,
    GrammarCategory.POS_INFLECTABLE_FEATS,
    GrammarCategory.PHON_FEAT_TYPES,
}


def _models_bucket(name: str) -> set:
    """Return the GrammarCategory members in local set `name` of
    models._build_default_conflict_modes."""
    tree = ast.parse(inspect.getsource(models._build_default_conflict_modes))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
            and isinstance(node.value, ast.Set)
        ):
            out = set()
            for elt in node.value.elts:
                assert isinstance(elt, ast.Attribute), ast.dump(elt)
                out.add(GrammarCategory[elt.attr])
            return out
    raise AssertionError(f"models.py no longer defines a `{name}` set literal")


def test_gold_reserved_mirrors_models():
    assert set(wizard_pages_deferred._GOLD_RESERVED) == _models_bucket("gold_reserved")


def test_part_b_kind_classification():
    multi = _models_bucket("multi_instance")
    gold = _models_bucket("gold_reserved")
    for cat in (GrammarCategory.FEATURE_STRUCT_TYPES,
                GrammarCategory.POS_INFLECTABLE_FEATS,
                GrammarCategory.PHON_FEAT_TYPES):
        assert cat in multi
        assert cat not in wizard_pages_deferred._GOLD_RESERVED
    assert GrammarCategory.INFLECTION_FEATURES in gold
    assert GrammarCategory.INFLECTION_FEATURES in wizard_pages_deferred._GOLD_RESERVED


def test_schema_categories_surface_part_b():
    assert _PART_B <= set(wizard_pages_deferred._SCHEMA_CATEGORIES)
    assert len(set(wizard_pages_deferred._SCHEMA_CATEGORIES)) == len(
        wizard_pages_deferred._SCHEMA_CATEGORIES
    )


def test_schema_categories_have_a_kind_and_default_mode():
    classified = _models_bucket("multi_instance") | _models_bucket("gold_reserved")
    for cat in wizard_pages_deferred._SCHEMA_CATEGORIES:
        assert cat in classified, cat
        assert cat in models._DEFAULT_CONFLICT_MODES
        # The scope rows label themselves from the enum value.
        assert cat.value.replace("_", " ").strip()


def test_main_window_copy_matches_wizard():
    # main_window keeps a literal copy (importing the Qt page module from it
    # would break test_ui_gating's PyQt6 stub); equality is the guard.
    assert list(main_window._SCHEMA_CATEGORIES) == list(
        wizard_pages_deferred._SCHEMA_CATEGORIES
    )
    assert selection_wizard._SCHEMA_CATEGORIES is wizard_pages_deferred._SCHEMA_CATEGORIES
    assert selection_wizard._GOLD_RESERVED is wizard_pages_deferred._GOLD_RESERVED
