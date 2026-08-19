"""Structural guards for the wizard module split (feature 039, US4).

Four invariants that the 6512-line monolith held only by accident of being one
file, and that the split has to hold on purpose:

1. Every page class is on the SAME Qt base, because the facade imports every
   page module eagerly (T037).
2. The facade re-exports the whole compatibility surface (T038, FR-006).
3. No two item-data role constants claim the same `UserRole + N` offset (T039).
4. `execute_move` is called from exactly one function in the whole package
   (T040, FR-002).

Each is written so it cannot pass vacuously. That is not a stylistic
preference: two of the scans this feature inherited had degraded to
`re.findall(...) == []` over text that no longer contained the thing they
forbade, and a test that passes because it read nothing looks exactly like a
test that passes because nothing is wrong.
"""
from __future__ import annotations

import ast
import os
import re

import pytest

# SC-007 convention: offscreen platform before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GRAMTRANS_NO_THEME", "1")

pytest.importorskip("PyQt6")

from _wizard_source import (  # noqa: E402
    wizard_module_paths,
    wizard_package_source,
)
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402

PAGE_MODULES = [
    "wizard_page_projects",
    "wizard_page_ws",
    "wizard_pages_pickers",
    "wizard_pages_skeleton",
    "wizard_pages_blocks",
    "wizard_page_texts",
    "wizard_pages_deferred",
]

FOUNDATION_MODULES = ["wizard_roles", "wizard_page_base", "wizard_widgets"]


# ===========================================================================
# Guard 1 (T037) -- one Qt base across every page class
# ===========================================================================

def test_the_facade_imports_every_page_module_eagerly():
    """All ten wizard modules must be imported by importing the facade.

    This is the guard on a hazard that is invisible at runtime until it bites.
    `test_wizard_page_flow.py:99/107` and `test_ui_gating.py` install a QWizard
    double and overwrite `QtWidgets.QWizard` / `QWizardPage` in `sys.modules` at
    IMPORT time -- on the real extension module, when real PyQt6 was imported
    first. Every `class _PageX(QtWidgets.QWizardPage)` therefore captures
    whichever base is installed at the moment ITS OWN module is first imported.

    While the wizard was one file there was one such moment and the question
    could not arise. With eleven files it can: a page module imported lazily --
    inside a function, or on first use -- would bind a different base than its
    siblings, and the resulting failures would be Qt-level and mystifying rather
    than a clear ImportError. `_ui_geometry.needs_a_real_qwizard()` exists
    because of this same substitution and documents it from the other side.

    So: assert the modules are already in `sys.modules` after the facade is
    imported, which is what an eager top-level import guarantees.
    """
    import sys

    expected = FOUNDATION_MODULES + PAGE_MODULES
    assert len(expected) == 10, "expected ten split modules, got %d" % len(expected)

    missing = [m for m in expected
               if "gramtrans.Lib.ui." + m not in sys.modules]
    assert not missing, (
        "these wizard modules were NOT imported by importing the facade: %s. "
        "A lazily-imported page module binds `QtWidgets.QWizardPage` at a "
        "different moment than its siblings, which under the suite's QWizard "
        "substitution means a different base class. Import them at the top of "
        "selection_wizard.py." % ", ".join(missing)
    )


def test_every_page_class_shares_one_qwizardpage_base():
    """The classes themselves agree on their Qt ancestor.

    Guard 1's premise, checked directly: whatever `QWizardPage` is in this
    session, all fourteen page classes must descend from the same one. Compared
    by identity, because two distinct classes both *named* `QWizardPage` is
    precisely the failure being excluded.
    """
    pages = [getattr(sw, n) for n in dir(sw)
             if n.startswith("_Page") and isinstance(getattr(sw, n), type)]
    assert len(pages) >= 14, (
        "expected at least 14 page classes on the facade, found %d -- the "
        "guard must not shrink silently" % len(pages)
    )
    bases = set()
    for cls in pages:
        # The QWizardPage in each class's MRO, by identity.
        for anc in cls.__mro__:
            if anc.__name__ == "QWizardPage":
                bases.add(id(anc))
                break
        else:
            raise AssertionError("%s has no QWizardPage ancestor" % cls.__name__)
    assert len(bases) == 1, (
        "page classes are split across %d distinct QWizardPage base objects; "
        "a module was imported at a different time than its siblings"
        % len(bases)
    )


# ===========================================================================
# Guard 2 (T038) -- the facade re-exports the whole compatibility surface
# ===========================================================================

# Every name `selection_wizard` exposed on `main` before the split, minus the
# one deliberate removal. Written out rather than computed: a list derived from
# the module it is checking would agree with anything.
#
# `MERGE_KEEP` is the single sanctioned drop (feature 039 T032). It was imported
# and never read, no test binds `selection_wizard.MERGE_KEEP`, and
# `Lib/merge_preview.py` remains its home.
COMPAT_SURFACE = (
    'CategoryScope', 'ConflictMode', 'ExcludedLossy', 'GrammarCategory',
    'MIN_WINDOW_HEIGHT', 'MIN_WINDOW_WIDTH', 'MergePreviewPane',
    'MergePreviewService', 'NEW', 'OVERWRITE', 'Optional', 'PageHeader',
    'PickerState', 'PosGroupedAffixInventory', 'PreviewRequest', 'QtCore',
    'QtWidgets', 'RunMode', 'RunReport', 'Selection', 'SelectionWizard',
    'Set', 'SimilarResolution', 'SourceAffixInventory', 'SourceCounts',
    'SourcePickerDialog', 'StatsPanel', 'TargetPickerDialog',
    'ThemeCornerBar', 'WSKind', 'WSMapping', 'WSMappingEntry',
    'WsFontRegistry', 'WsRole', '_CATEGORY_TOGGLES', '_CF_GUID_ROLE',
    '_CF_KIND_ROLE', '_CF_LEVEL_LABELS', '_CF_STATUS_ROLE',
    '_CONFLICT_LABELS', '_CUSTOM_FIELDS_ONLY', '_DEFAULT_CONFLICT_MODES',
    '_DEPS_CAT_ROLE', '_DEPS_STATUS_ROLE', '_ET_CAT_ROLE', '_ET_GUID_ROLE',
    '_ET_KIND_ROLE', '_ET_MODE_NEW', '_ET_MODE_OVERWRITE', '_ET_STATUS_ROLE',
    '_FlowPage', '_GOLD_RESERVED', '_GUID_ROLE', '_IS_PRODUCES',
    '_ITEM_CAT_ROLE', '_ITEM_STATUS_ROLE', '_KIND_ROLE', '_PHON_CAT_ROLE',
    '_PHON_GUID_ROLE', '_PHON_KIND_ROLE', '_PHON_MODE_NEW',
    '_PHON_MODE_OVERWRITE', '_PHON_STATUS_ROLE', '_PLAN_FAILURE_ATTR',
    '_PREVIEW_PANE_MIN_WIDTH', '_PageCustomFields', '_PageEntryTypes',
    '_PageFinish', '_PageGramDeps', '_PageItemPicker', '_PagePhonology',
    '_PagePreview', '_PageProjects', '_PageRules', '_PageScopeConflict',
    '_PageSkeleton', '_PageStemPicker', '_PageTexts', '_PageWritingSystems',
    '_ROLE_ROLE', '_RULES_GUID_ROLE', '_RULES_KIND_ROLE',
    '_RULES_STATUS_LABELS', '_RULES_STATUS_ROLE', '_SCHEMA_CATEGORIES',
    '_SCOPE_LABELS', '_SKEL_CAT_ROLE', '_SKEL_GUID_ROLE', '_SKEL_KIND_ROLE',
    '_SKEL_OWNER_ROLE', '_SKEL_READ_ONLY', '_SKEL_STATUS_ROLE',
    '_STATUS_LABELS', '_TREE_PANE_MIN_WIDTH', '_action_to_mode',
    '_allowed_modes', '_carry_full_values_in_tooltips',
    '_compute_wizard_plan', '_count_affixes_in_node', '_count_says_content',
    '_elide_over_narrow_columns', '_entry_types_missing_ref_for',
    '_enumerate_active_ws_ids', '_enumerate_ws_by_kind', '_item_views_of',
    '_kl010_notice', '_make_group_item', '_make_tree_pane_splitter',
    '_module_log', '_operation_failed_note', '_page_progress',
    '_phonology_excluded_lossy_for', '_phonology_nc_or_phoneme_trimmed',
    '_resolve_gate', '_safe_compute_wizard_plan', '_safe_path',
    '_set_item_text_with_tooltip', '_set_plan_failure_reason',
    '_show_failure_row', '_source_counts_of', '_take_plan_failure_reason',
    'affix_label_runs', 'attach_ws_font_delegate',
    'build_deps_inventory', 'build_entry_types_inventory',
    'build_excluded_lossy_warnings', 'build_phonology_excluded_lossy',
    'build_phonology_inventory', 'build_pos_grouped_inventory',
    'build_rules_inventory', 'build_selection', 'build_skeleton_inventory',
    'build_text_inventory', 'closest_ws_defaults', 'collapse_entry_types',
    'collapse_phonology', 'collapse_pos_grouped',
    'entry_types_missing_ref_warnings', 'gt_api',
    'install_theme', 'label_for',
    'mirror_check_state', 'phonology_uses_untraversed_rules', 'rate_for',
    'reporting', 'set_ws_runs', 'warrants_indicator',
)


def test_the_compat_surface_list_is_not_trivially_small():
    """A guard on the guard.

    If `COMPAT_SURFACE` were ever trimmed to a handful of names, the
    parametrized test below would still pass for each of them and report
    nothing wrong. The surface measured on `main` was 154 names.
    """
    assert len(COMPAT_SURFACE) > 140, (
        "COMPAT_SURFACE has shrunk to %d entries; it was measured at 153 "
        "(154 on main, less the sanctioned MERGE_KEEP drop). Shrinking the "
        "list weakens the guard without failing it."
        % len(COMPAT_SURFACE)
    )
    assert len(set(COMPAT_SURFACE)) == len(COMPAT_SURFACE), "duplicate entries"


@pytest.mark.parametrize("name", COMPAT_SURFACE)
def test_the_facade_still_re_exports(name):
    """FR-006: `selection_wizard.X` resolves for every name it used to.

    ~20 test modules import this module and bind names off it, and exactly one
    production site imports it (`SelectionWizard`, at `gramtrans.py:249`). The
    split is only safe if that surface is unchanged, and "unchanged" has to be
    asserted rather than assumed -- a name dropped from the re-export block
    fails at the caller's import, in a different file, at a later date.
    """
    assert hasattr(sw, name), (
        "selection_wizard.%s no longer resolves. If the name moved to a "
        "wizard_* module, add it to the facade's compatibility re-export "
        "block; if its removal is intended, delete it from COMPAT_SURFACE in "
        "the same commit and say why." % name
    )


def test_merge_keep_is_the_only_sanctioned_removal():
    """The one name the split deliberately stopped re-exporting (T032)."""
    assert not hasattr(sw, "MERGE_KEEP"), (
        "MERGE_KEEP is back on the facade. It was dropped as an unused import; "
        "if something needs it, import it from Lib.merge_preview directly."
    )


# ===========================================================================
# Guard 3 (T039) -- no two role constants claim the same UserRole offset
# ===========================================================================

def _role_offsets():
    """{offset: [constant names]} parsed out of wizard_roles.py.

    Parsed from source rather than read off the module so the offsets are the
    ones a reader of the file sees. `Qt.ItemDataRole.UserRole` is a large
    integer; two constants colliding is a fact about the `+ N`, and reading the
    resolved values would work too but would report `327` where the file says
    `+ 71`.
    """
    src = None
    for p in wizard_module_paths():
        if p.stem == "wizard_roles":
            src = p.read_text(encoding="utf-8")
            break
    assert src is not None, "wizard_roles.py not found"

    offsets: dict[int, list[str]] = {}
    for node in ast.parse(src).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        v = node.value
        if not (isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add)
                and isinstance(v.right, ast.Constant)
                and isinstance(v.right.value, int)):
            continue
        if "UserRole" not in ast.unparse(v.left):
            continue
        offsets.setdefault(v.right.value, []).append(target.id)
    return offsets


def test_role_constants_are_parsed_at_all():
    """Non-vacuity: an empty offset map would make the collision test pass."""
    offsets = _role_offsets()
    total = sum(len(v) for v in offsets.values())
    assert total >= 25, (
        "only %d UserRole offsets parsed out of wizard_roles.py; the file "
        "declared 28 at the time of the split, so the collision check below "
        "would be inspecting almost nothing" % total
    )


def test_no_two_role_constants_share_a_userrole_offset():
    """Every item-data role gets its own `UserRole + N`.

    Before the split this was violated and nothing could see it:
    `_RULES_GUID_ROLE`/`_RULES_KIND_ROLE`/`_RULES_STATUS_ROLE` sat on
    `UserRole + 70/71/72` and `_ET_GUID_ROLE`/`_ET_KIND_ROLE`/`_ET_CAT_ROLE`/
    `_ET_STATUS_ROLE` on `+ 70/71/72/73` -- declared 800 lines apart in a
    6512-line file. It was harmless only for as long as `_PageRules` and
    `_PageEntryTypes` owned disjoint trees, which is a property of today's UI
    rather than a rule anything enforced. One tree carrying both kinds of row,
    or one page reusing the other's helper, and the two would read each other's
    data with no error at all -- item data is untyped.

    Collecting the constants into one module is what made this checkable; this
    is the check.
    """
    offsets = _role_offsets()
    clashes = {n: sorted(names) for n, names in sorted(offsets.items())
               if len(names) > 1}
    assert not clashes, (
        "these UserRole offsets are claimed by more than one role constant: "
        + "; ".join("+%d -> %s" % (n, ", ".join(names))
                    for n, names in clashes.items())
        + ". Item data is untyped, so two constants on one offset means two "
          "pages can silently read each other's rows. Move one block to a free "
          "offset."
    )


# ===========================================================================
# Guard 4 (T040) -- one write point across the whole package
# ===========================================================================

def test_execute_move_is_called_from_exactly_one_function_package_wide():
    """Constitution Principle III, as a package-wide structural claim (FR-002).

    `test_036_finish_guard.py:623` already scans `selection_wizard.py` for this
    and stays as it is. That scan was a whole-wizard scan when the wizard was
    one file; it is now a one-eleventh scan, and this test is the other ten
    elevenths. Complementary, not a replacement: the in-file version knows
    which function is allowed to call it, and this one knows that no other file
    has started to.
    """
    callers = []
    for p in wizard_module_paths():
        tree = ast.parse(p.read_text(encoding="utf-8"))

        # Map every call to `<anything>.execute_move(...)` to its enclosing
        # top-level function or method.
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "execute_move"):
                    callers.append("%s:%s" % (p.name, node.name))
                    break

    # Non-vacuity: the scan must find the one caller it expects, or it is not
    # scanning anything. A count of zero is a broken test, not a clean bill.
    assert callers, (
        "no `.execute_move(...)` call found anywhere in the wizard package. "
        "The Move write point cannot have vanished; the scan is broken."
    )
    unique = sorted(set(callers))
    assert unique == ["selection_wizard.py:_on_move"], (
        "expected exactly one write point, `_PageFinish._on_move` in "
        "selection_wizard.py; found %s. Principle III's Preview-before-Mutate "
        "guarantee rests on there being one place a Move can be issued from."
        % unique
    )


def test_the_write_point_is_on_the_finish_page():
    """`_on_move` belongs to `_PageFinish`, not to some other class.

    Guard 4 matches on function name; this pins the owner, so a second
    `_on_move` added to another class cannot satisfy it.
    """
    src = None
    for p in wizard_module_paths():
        if p.stem == "selection_wizard":
            src = p.read_text(encoding="utf-8")
    owners = []
    for cls in ast.parse(src).body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == "_on_move":
                owners.append(cls.name)
    assert owners == ["_PageFinish"], (
        "expected `_on_move` on _PageFinish alone; found it on %s" % owners
    )


# ===========================================================================
# Size budget (FR-003 / SC-008), checked here so it cannot drift unnoticed
# ===========================================================================

def test_no_wizard_module_exceeds_the_size_budget():
    """FR-003: no module becomes the place where everything lands again.

    The whole point of the split was that one file had grown to 6512 lines
    while every feature that touched it noted the fact and added to it anyway.
    A budget that is only written down repeats that.
    """
    over = []
    for p in wizard_module_paths():
        n = len(p.read_text(encoding="utf-8").splitlines())
        if n > 1750:
            over.append("%s (%d L)" % (p.name, n))
    assert not over, (
        "these wizard modules exceed the 1750-line budget: %s" % ", ".join(over)
    )


def test_the_package_source_scan_covers_every_module():
    """`wizard_package_source()` really is the whole package.

    The two broadened scans in `test_036_wizard_flow_numbering.py` and
    `test_wizard_page_order.py` are only as good as this.
    """
    src = wizard_package_source()
    for p in wizard_module_paths():
        assert ("# === %s ===" % p.name) in src, (
            "%s is missing from the package source scan" % p.name
        )
    assert len(wizard_module_paths()) == 11, (
        "expected the facade plus ten wizard_* modules; got %d"
        % len(wizard_module_paths())
    )
    # And it must contain real code, not just banners. 19 top-level classes at
    # the time of the split: 14 pages, SelectionWizard, _FlowPage, _BlockPage
    # and the two mixins. The floor is deliberately below that, so adding a
    # class does not fail the guard and deleting most of them does.
    n_classes = len(re.findall(r"^class ", src, re.M))
    assert n_classes >= 15, (
        "package source holds only %d top-level class definitions; expected "
        "~19. The scan is reading the wrong files." % n_classes
    )
