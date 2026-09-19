"""Feature 038 -- T072 (Phase 7, US3): the deselection checkbox is wired to
something.

FR-016: "Each pulled-in item MUST be individually deselectable."

THE DEFECT THIS FILE PINS. `_PageGramDeps` renders every pulled-in
dependency with a checkbox, preselects it, tells the user in its own subtitle
to "Deselect anything you do not want", and exposes
`deselected_dep_guids()` -- which returns exactly the preselected GUIDs the
user unchecked. **Nothing called it.** `_compute_wizard_plan` folds in picks
from the custom-fields, phonology, entry-types, rules, skeleton, stems and
texts pages, and never touches this one, so `Selection.excluded_deps` was
`frozenset()` on every plan the wizard has ever built. Unchecking a box
changed nothing at all.

That is the sixth appearance of this feature's recurring shape and the first
one in the UI: a signal that genuinely exists -- the user's own explicit
choice, collected and returned by a method written for the purpose -- read at
a level where it cannot do its job, which here means not read at all.

WHY IT MATTERS MORE NOW THAN IT DID. Before T070 the closure pulled nothing
into the plan, so `excluded_deps` had almost nothing to exclude and the dead
wiring was invisible in outcome as well as in code. T070 makes a selected
affix pull its POS in by default (FR-014). The moment the default is
inclusion, "individually deselectable" stops being decoration and becomes the
user's only way to say no.

The engine half of the same clause is `tests/unit/test_038_pull_in.py`
(T070/T071): `excluded_deps` and `CategoryScope.NONE` suppress a pull-in and
emit `SkipReason.DEPENDENCY_DESELECTED`. This file is the other half -- that
the wizard can actually put a GUID in that set.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PyQt6", reason="wizard plan assembly needs PyQt6")

from gramtrans.Lib.models import GrammarCategory  # noqa: E402
from gramtrans.Lib.selection import (  # noqa: E402
    PickerState,
    SourceAffixInventory,
    build_selection,
)
from gramtrans.Lib.ui import selection_wizard as _sw_mod  # noqa: E402

_compute_wizard_plan = _sw_mod._compute_wizard_plan


def _affix_only_selection():
    return build_selection(
        PickerState(checked_affixes=frozenset({"aff-1"})),
        SourceAffixInventory(unbound_affixes=frozenset({"aff-1"})),
    )


class _FakeWizard:
    """Only the accessors `_compute_wizard_plan` reads.

    Every other page is absent on purpose: `_compute_wizard_plan` guards them
    with `hasattr`, so a fixture this small also proves the new step's own
    guard holds when `page_gram_deps` is missing.
    """

    def __init__(self, deselected=None, *, with_deps_page=True):
        self._deselected = deselected
        self._with_deps_page = with_deps_page
        if with_deps_page:
            self.page_gram_deps = self._page_gram_deps

    def page_project_ws(self):
        m = MagicMock()
        m.context.return_value = object()
        m.ws_mapping.return_value = None
        return m

    def page_items(self):
        m = MagicMock()
        m.collect_selection.return_value = _affix_only_selection()
        return m

    def page_stems(self):
        m = MagicMock()
        m.stem_picks.return_value = frozenset()
        return m

    def page_phonology(self):
        return None

    def page_skeleton(self):
        m = MagicMock()
        m.collect_skeleton_picks.return_value = {
            "pos_guids": set(), "slot_guids": set(), "template_guids": set(),
        }
        return m

    def _page_gram_deps(self):
        m = MagicMock()
        if self._deselected is None:
            del m.deselected_dep_guids  # page predating the method
        else:
            m.deselected_dep_guids.return_value = frozenset(self._deselected)
        return m


def _run(wizard):
    captured = {}

    def _fake_compute_preview(context, selection, ws_mapping):
        captured["selection"] = selection
        return ("READY", object())

    with patch.object(_sw_mod.gt_api, "compute_preview",
                      side_effect=_fake_compute_preview), \
         patch.object(_sw_mod.RunReport, "build_from_plan",
                      return_value=object()), \
         patch.object(_sw_mod, "_phonology_excluded_lossy_for",
                      return_value=[]):
        plan, report = _compute_wizard_plan(wizard)
    return captured["selection"], plan


def test_a_deselected_dependency_reaches_the_selection() -> None:
    """The whole of T072 in one assertion: what the user unchecked arrives in
    the field the engine reads."""
    selection, plan = _run(_FakeWizard({"DEP-1", "dep-2"}))
    assert selection.excluded_deps == frozenset({"dep-1", "dep-2"})
    assert plan is not None


def test_the_guids_are_lower_cased_like_every_other_pick_set() -> None:
    """Not cosmetic. `preview._plan_pulled_in_items` tests membership against
    GUIDs that have been through `categories._guid_str_from`, which
    lower-cases -- so a mixed-case GUID in this set would look correct in the
    Selection, and silently never match the item the user deselected. The
    skeleton, stems and texts steps lower-case for the same reason."""
    selection, _plan = _run(_FakeWizard({"DEP-UPPER-CASE"}))
    assert selection.excluded_deps == frozenset({"dep-upper-case"})
    assert selection.is_dep_excluded("dep-upper-case") is True


def test_checking_everything_leaves_the_exclusion_set_empty() -> None:
    """`deselected_dep_guids()` returns an empty frozenset when the user
    touched nothing, and that must not become an exclusion of anything."""
    selection, _plan = _run(_FakeWizard(frozenset()))
    assert selection.excluded_deps == frozenset()


def test_a_wizard_without_the_deps_page_still_builds_a_plan() -> None:
    """Every fake wizard in the unit suite supplies only the pages it
    exercises; the new step must be as absent-tolerant as its siblings."""
    selection, plan = _run(_FakeWizard(None, with_deps_page=False))
    assert selection.excluded_deps == frozenset()
    assert plan is not None


def test_a_deps_page_without_the_method_still_builds_a_plan() -> None:
    """`hasattr` on the METHOD, not just the page -- the same two-level guard
    `page_skeleton`/`collect_skeleton_picks` and `page_stems`/`stem_picks`
    use."""
    selection, plan = _run(_FakeWizard(None))
    assert selection.excluded_deps == frozenset()
    assert plan is not None


def test_the_deselection_does_not_disturb_the_rest_of_the_selection() -> None:
    """A step that folds in exclusions must not drop what the earlier steps
    put in the Selection -- `dataclasses.replace`, never a fresh build."""
    selection, _plan = _run(_FakeWizard({"dep-1"}))
    assert selection.is_on(GrammarCategory.AFFIXES) is True
    assert selection.affix_picks == frozenset({"aff-1"})


# ===========================================================================
# The OTHER page -- _PageSkeleton owns the node kinds the closure pulls in
# ===========================================================================

class _FakeWizardWithSkeleton(_FakeWizard):
    """`_FakeWizard` plus a skeleton page that answers the new accessor.

    Two pages contribute to `excluded_deps`, and they must UNION rather than
    overwrite: `_PageGramDeps` owns inflection features / classes / stem
    names, `_PageSkeleton` owns POSes, slots and templates -- and the five
    registered closure edges all land on the latter three. A step that read
    only the deps page would make FR-016 true of the dependencies the closure
    does not pull in and false of the ones it does.
    """

    def __init__(self, deselected=None, skeleton_deselected=None):
        super().__init__(deselected)
        self._skeleton_deselected = skeleton_deselected

    def page_skeleton(self):
        m = MagicMock()
        m.collect_skeleton_picks.return_value = {
            "pos_guids": set(), "slot_guids": set(), "template_guids": set(),
        }
        if self._skeleton_deselected is None:
            del m.deselected_skeleton_guids
        else:
            m.deselected_skeleton_guids.return_value = frozenset(
                self._skeleton_deselected)
        return m


def test_a_deselected_pos_from_the_skeleton_page_reaches_the_selection() -> None:
    selection, _plan = _run(
        _FakeWizardWithSkeleton(None, skeleton_deselected={"POS-Verb"}))
    assert selection.excluded_deps == frozenset({"pos-verb"})


def test_both_pages_contribute_to_one_exclusion_set() -> None:
    selection, _plan = _run(_FakeWizardWithSkeleton(
        {"dep-1"}, skeleton_deselected={"slot-9"}))
    assert selection.excluded_deps == frozenset({"dep-1", "slot-9"})


def test_a_skeleton_page_predating_the_accessor_is_tolerated() -> None:
    selection, _plan = _run(_FakeWizardWithSkeleton({"dep-1"}, None))
    assert selection.excluded_deps == frozenset({"dep-1"})


# ===========================================================================
# _PageSkeleton.deselected_skeleton_guids -- against a real populated tree
# ===========================================================================

@pytest.fixture(scope="session")
def qapp():
    """Session-scoped, like every other UI fixture in this suite. A
    function-scoped QApplication tears the ThemeManager singleton's C++ object
    down between tests and the second page construction raises."""
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


# Pages are kept alive for the session: a garbage-collected QWizardPage takes
# its child widgets' C++ objects with it, and the shared ThemeManager holds
# connections into them.
_LIVE_PAGES: list = []


def _skeleton_inventory():
    from gramtrans.Lib.selection import (
        SkeletonInventory,
        SkeletonPosNode,
        SlotNode,
        TemplateNode,
    )
    return SkeletonInventory(
        pos_nodes=(
            SkeletonPosNode(
                pos_guid="pos-verb", label="Verb", preselected=True,
                slots=(
                    SlotNode(slot_guid="slot-filled", label="prefix1",
                             preselected=True, affix_count=1),
                    SlotNode(slot_guid="slot-empty", label="prefix2",
                             preselected=False, affix_count=0),
                ),
                templates=(
                    TemplateNode(template_guid="tpl-1", label="Verb template",
                                 preselected=True,
                                 referenced_slot_guids=("slot-filled",)),
                ),
            ),
        ),
        affix_fills={"slot-filled": frozenset({"aff-1"})},
        affix_picks=frozenset({"aff-1"}),
    )


def _populated_skeleton_page(qapp):
    from gramtrans.Lib.ui.wizard_pages_skeleton import _PageSkeleton
    page = _PageSkeleton()
    _LIVE_PAGES.append(page)
    page._skeleton = _skeleton_inventory()
    page._populate_skeleton_tree(page._skeleton)
    return page


def _tree_item(page, guid):
    from PyQt6 import QtWidgets

    from gramtrans.Lib.ui.wizard_roles import _SKEL_GUID_ROLE
    it = QtWidgets.QTreeWidgetItemIterator(page._tree)
    while it.value():
        item = it.value()
        if item.data(0, _SKEL_GUID_ROLE) == guid:
            return item
        it += 1
    raise AssertionError("no tree item for " + guid)


def test_an_untouched_skeleton_deselects_nothing(qapp) -> None:
    """The negative first: everything preselected is still checked, so the
    accessor must be empty. Without this, an accessor that returned every
    preselected GUID would pass every positive test below."""
    page = _populated_skeleton_page(qapp)
    assert page.deselected_skeleton_guids() == frozenset()


def test_unchecking_a_slot_reports_that_slot(qapp) -> None:
    from PyQt6 import QtCore
    page = _populated_skeleton_page(qapp)
    _tree_item(page, "slot-filled").setCheckState(
        0, QtCore.Qt.CheckState.Unchecked)
    assert "slot-filled" in page.deselected_skeleton_guids()


def test_unchecking_a_template_reports_that_template(qapp) -> None:
    from PyQt6 import QtCore
    page = _populated_skeleton_page(qapp)
    _tree_item(page, "tpl-1").setCheckState(0, QtCore.Qt.CheckState.Unchecked)
    assert "tpl-1" in page.deselected_skeleton_guids()


def test_a_node_that_was_never_preselected_is_not_a_deselection(qapp) -> None:
    """`slot-empty` ships unchecked. Reporting it would tell the engine the
    user REFUSED an item they never saw offered, and `excluded_deps` would
    then suppress a pull-in nobody asked to suppress."""
    page = _populated_skeleton_page(qapp)
    assert "slot-empty" not in page.deselected_skeleton_guids()


def test_the_accessor_is_empty_before_the_page_is_built(qapp) -> None:
    from gramtrans.Lib.ui.wizard_pages_skeleton import _PageSkeleton
    page = _PageSkeleton()
    _LIVE_PAGES.append(page)
    assert page._skeleton is None
    assert page.deselected_skeleton_guids() == frozenset()


def test_a_partially_checked_pos_is_not_a_deselection(qapp) -> None:
    """The trap this accessor had to avoid, pinned rather than described.

    POS rows are `ItemIsAutoTristate`, and the fixture's POS owns one
    never-preselected slot -- so an UNTOUCHED tree already leaves `Verb` at
    `PartiallyChecked`. `collect_skeleton_picks` tests `== Checked` and
    therefore omits it, so a `preselected - picks` implementation would
    report `pos-verb` as refused on a tree nobody touched. Since T070 that
    refusal is acted on: the `AFFIX_TO_POS` pull-in would be suppressed and
    the affix would arrive with no part of speech.
    """
    from PyQt6 import QtCore
    page = _populated_skeleton_page(qapp)
    pos_item = _tree_item(page, "pos-verb")
    assert pos_item.checkState(0) == QtCore.Qt.CheckState.PartiallyChecked
    assert "pos-verb" not in page.collect_skeleton_picks()["pos_guids"]
    assert "pos-verb" not in page.deselected_skeleton_guids()


def test_unchecking_a_pos_outright_reports_it(qapp) -> None:
    """The positive the test above must not be allowed to swallow: an
    explicitly Unchecked POS IS a deselection."""
    from PyQt6 import QtCore
    page = _populated_skeleton_page(qapp)
    _tree_item(page, "pos-verb").setCheckState(
        0, QtCore.Qt.CheckState.Unchecked)
    assert "pos-verb" in page.deselected_skeleton_guids()
