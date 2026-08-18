"""T006/T011 -- wizard named-accessor plumbing + no-literal-index guard.

Inserting pages shifts every literal `wizard.page(N)`. The fix routes all
cross-page lookups through named accessors. These tests guard that:
  (a) each accessor returns its stored `_page_*` attribute,
  (b) no literal `.page(<int>)` call survives in the wizard source,
  (c) Custom Fields is declared before Phonology (Feature 016, T011),
  (d) Rules sits between Grammatical Dependencies and Finish.

Feature 036 T006 extends this file in two ways, and the reason for each is a
way the plumbing can now break:

* **Step 1 became two pages** (FR-006). The projects half keeps the
  `page_project_ws()` accessor -- 23 call sites depend on the name -- but now
  returns `_page_projects`; the writing-systems half is reached through a new
  `page_writing_systems()`. Two accessors over one attribute, or one accessor
  answering for both halves, is the failure this table catches.
* **Order moved from `addPage` calls to one declaration** (FR-010). The
  order assertions below used to read literal `addPage(self._page_X)` lines;
  those lines are gone, so they read the declaration instead. Asserting order
  against the thing that no longer fixes it would be coverage in name only.
"""
from __future__ import annotations

import re
from pathlib import Path

import importlib
import importlib.util

import pytest

# Skip at collection time if PyQt6 is genuinely absent OR already stubbed
# (importlib.util.find_spec raises ValueError when PyQt6 is a MagicMock stub).
# This mirrors the guard in test_page_custom_fields.py (b589d6c pattern) and
# prevents pytest.importorskip from pre-loading real PyQt6 into sys.modules on
# a combined run, which would make the setdefault stubs in test_ui_gating.py
# and test_wizard_page_flow.py become no-ops (confirmed latent CI order-dep).
try:
    _pyqt6_spec = importlib.util.find_spec("PyQt6")
except (ValueError, AttributeError):
    _pyqt6_spec = None  # stub installed; treat as absent for real-Qt tests
if _pyqt6_spec is None:
    pytest.skip("PyQt6 not installed or stubbed", allow_module_level=True)

from gramtrans.Lib.ui import selection_wizard as _sw

SelectionWizard = _sw.SelectionWizard

_ACCESSORS = [
    # 036 FR-006: the name is unchanged, the attribute behind it is the
    # projects half of the split step 1 (data-model section 1, entry 1).
    ("page_project_ws",   "_page_projects"),
    ("page_writing_systems", "_page_writing_systems"),  # 036 FR-006: new, entry 2
    ("page_custom_fields","_page_custom_fields"),
    ("page_phonology",    "_page_phonology"),
    ("page_items",        "_page_items"),
    ("page_stems",        "_page_stems"),
    ("page_skeleton",     "_page_skeleton"),
    ("page_gram_deps",    "_page_gram_deps"),
    ("page_entry_types",  "_page_entry_types"),   # spec 021: idx 6
    ("page_rules",        "_page_rules"),          # 018-rules-page: idx 7
    ("page_texts",        "_page_texts"),          # Feature 026
    ("page_preview",      "_page_preview"),        # retained, never in the flow
    ("page_finish",       "_page_finish"),
]


class _StubWizard:
    """Plain object standing in for `self` -- avoids creating an uninitialized
    PyQt6 QObject (which pollutes sip state across the test session)."""


def _stub_with_pages():
    w = _StubWizard()
    for _, attr in _ACCESSORS:
        setattr(w, attr, object())  # unique sentinel per page
    return w


def _call(accessor, w):
    """Invoke the real unbound accessor, naming the attribute it wanted.

    A bare `AttributeError` out of an accessor reads as a broken test; it is
    in fact the accessor reaching for an attribute this table says it should
    not (036 FR-006 renamed the one behind `page_project_ws()`).
    """
    fn = getattr(SelectionWizard, accessor, None)
    assert fn is not None, f"SelectionWizard has no {accessor}() accessor"
    try:
        return fn(w)
    except AttributeError as exc:      # noqa: PERF203 -- one accessor, one message
        raise AssertionError(f"{accessor}() reads the wrong attribute: {exc}")


def test_accessors_return_stored_attributes():
    w = _stub_with_pages()
    for accessor, attr in _ACCESSORS:
        assert _call(accessor, w) is getattr(w, attr), accessor


def test_accessors_are_distinct():
    w = _stub_with_pages()
    got = [_call(acc, w) for acc, _ in _ACCESSORS]
    assert len(set(map(id, got))) == len(_ACCESSORS)  # no accessor aliases another


def test_no_literal_page_index_calls_in_wizard_source():
    """Regression guard: cross-page lookups must not use literal .page(<int>)."""
    src = Path(_sw.__file__).read_text(encoding="utf-8")
    offenders = re.findall(r"\.page\(\d+\)", src)
    assert offenders == [], f"literal page-index calls found: {offenders}"


def test_custom_fields_accessor_exists():
    """Feature 016 T011: page_custom_fields accessor must be present."""
    assert hasattr(SelectionWizard, "page_custom_fields"), (
        "SelectionWizard missing page_custom_fields accessor"
    )


def test_writing_systems_accessor_exists():
    """036 FR-006: the writing-systems half of the split step 1 is reachable."""
    assert hasattr(SelectionWizard, "page_writing_systems"), (
        "SelectionWizard missing page_writing_systems accessor (036 FR-006); "
        "ws_mapping() and selected_ws_ids() live behind it"
    )


def _declared_position(src, attr):
    """Where the flow declaration names `attr`, as a source offset (-1: absent).

    036 FR-010 makes one ordered declaration the single source of page order,
    and data-model section 1 gives each entry's `attr` as a *string*. The
    quoted attribute name is therefore what fixes the order -- the literal
    `addPage(self._page_X)` block these assertions used to read is gone.
    """
    for quoted in (f'"{attr}"', f"'{attr}'"):
        pos = src.find(quoted)
        if pos != -1:
            return pos
    return -1


def _assert_declared_before(first, second):
    src = Path(_sw.__file__).read_text(encoding="utf-8")
    a, b = _declared_position(src, first), _declared_position(src, second)
    assert a != -1, f"{first} is not named in the flow declaration"
    assert b != -1, f"{second} is not named in the flow declaration"
    assert a < b, f"{first} must be declared before {second}"


def test_custom_fields_declared_before_phonology():
    """Custom Fields precedes Phonology in the flow declaration (entries 3, 4)."""
    _assert_declared_before("_page_custom_fields", "_page_phonology")


def test_the_split_step_1_pages_lead_the_declaration():
    """036 FR-006: projects, then writing systems, then everything else."""
    _assert_declared_before("_page_projects", "_page_writing_systems")
    _assert_declared_before("_page_writing_systems", "_page_custom_fields")


# ============================================================================
# T022 -- _PageRules registered at addPage index 6, _page_finish at 7,
#         page_rules() accessor returns _PageRules, appears before _PagePhonology
#         (appears AFTER phonology in order, actually before _page_finish).
# ============================================================================

def test_rules_accessor_exists():
    """T022: page_rules() accessor must be present on SelectionWizard."""
    assert hasattr(SelectionWizard, "page_rules"), (
        "SelectionWizard missing page_rules accessor (018-rules-page T018)"
    )


def test_rules_accessor_returns_page_rules_type():
    """T022: page_rules() returns the stored _page_rules attribute."""
    from gramtrans.Lib.ui import selection_wizard as sw_mod
    _PageRules = sw_mod._PageRules
    w = _StubWizard()
    w._page_rules = object()  # sentinel
    result = SelectionWizard.page_rules(w)
    assert result is w._page_rules


def test_rules_page_declared_before_page_finish():
    """T022, read off the declaration now that it is what fixes the order."""
    _assert_declared_before("_page_rules", "_page_finish")


def test_rules_page_declared_after_gram_deps():
    """T022: Grammatical Dependencies precedes Rules (entries 8, 10)."""
    _assert_declared_before("_page_gram_deps", "_page_rules")


def test_finish_is_declared_last():
    """Nothing may be declared after Finish / Move -- it ends every run."""
    src = Path(_sw.__file__).read_text(encoding="utf-8")
    finish = _declared_position(src, "_page_finish")
    assert finish != -1, "_page_finish is not named in the flow declaration"
    for attr in ("_page_projects", "_page_writing_systems", "_page_custom_fields",
                 "_page_phonology", "_page_items", "_page_stems", "_page_skeleton",
                 "_page_gram_deps", "_page_entry_types", "_page_rules",
                 "_page_texts"):
        pos = _declared_position(src, attr)
        assert pos != -1, f"{attr} is not named in the flow declaration"
        assert pos < finish, f"{attr} must be declared before _page_finish"


def test_page_rules_appears_before_page_finish_accessor():
    """T022: page_rules accessor appears in source before page_finish accessor."""
    src = Path(_sw.__file__).read_text(encoding="utf-8")
    rules_acc = src.find("def page_rules(")
    finish_acc = src.find("def page_finish(")
    assert rules_acc != -1, "page_rules() accessor not found in wizard source"
    assert finish_acc != -1, "page_finish() accessor not found in wizard source"
    assert rules_acc < finish_acc, (
        "page_rules() accessor should appear before page_finish() accessor"
    )
