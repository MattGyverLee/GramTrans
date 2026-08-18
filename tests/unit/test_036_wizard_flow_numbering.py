"""T005 (US2) -- the declared flow, and step numbers that count what is shown.

Feature 036 replaces an unconditional eleven-page `addPage` block and twelve
hand-written `"Step N of 10"` literals with one ordered declaration. Every
assertion here exists because of a way that arrangement can go wrong:

* **A total is a lie the moment a page drops out.** The old titles announced
  ``of 10`` while eleven pages were registered and one of them (Texts) was
  unnumbered. Nothing may display a total again -- not a stale one, not a
  freshly computed one -- because the length of a run is not knowable until the
  run is over (FR-009a, SC-003b).
* **Numbers count entries, not declaration slots.** On a run that skips pages
  the operator must still read 1, 2, 3, ... with no hole where a skipped page
  would have been (FR-009, SC-003, SC-003a).
* **Skipping must never hide a decision.** A skippable page whose
  ``has_content()`` says yes is shown; the predicate is conservative, so
  "unsure" means shown (FR-009c).
* **The two pickers are never skipped.** "Your source has no affixes" is
  information the operator needs, and an absent page does not say it
  (FR-009d).
* **A page that is not in the flow can never acquire a number.** Permanent
  exclusion (`_PageScopeConflict`, `_PagePreview`) and per-run skipping use the
  same mechanism, so neither kind of absent page is numbered (FR-011).
* **One declaration, one order.** Registration order is read off the
  declaration rather than restated beside it, so the two cannot disagree
  (FR-010).

Authority: `specs/036-wizard-ui-polish/contracts/wizard-ui.md` section "Flow and
numbering" and `data-model.md` section 1.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# SC-007 convention: offscreen platform selected before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402


# ===========================================================================
# The declaration of record -- data-model section 1, transcribed
# ===========================================================================
# (attr, short_title, skippable). `has_content` is not spelled out here: the
# predicates are the implementation's business, but their *presence* is not
# (see test_has_content_is_declared_exactly_for_the_skippable_pages).
#
# Affix Picker and Stem Picker are `False` by mandate (FR-009d), not because
# they always have content. Projects, Writing Systems and Finish are `False`
# because they always ask something.
_DECLARED_FLOW = (
    ("_page_projects",        "Projects",                 False),
    ("_page_writing_systems", "Writing Systems",          False),
    ("_page_custom_fields",   "Custom Fields",            True),
    ("_page_phonology",       "Phonology",                True),
    ("_page_items",           "Affix Picker",             False),
    ("_page_stems",           "Stem Picker",              False),
    ("_page_skeleton",        "Morphology Skeleton",      True),
    ("_page_gram_deps",       "Grammatical Dependencies", True),
    ("_page_entry_types",     "Lexical-Entry Types",      True),
    ("_page_rules",           "Rules",                    True),
    ("_page_texts",           "Texts",                    True),
    ("_page_finish",          "Finish / Move",            False),
)

_SHORT_TITLES = {attr: short for attr, short, _ in _DECLARED_FLOW}

# Retained in the codebase, excluded from the flow, never added (FR-011).
_EXCLUDED_ATTRS = ("_page_scope", "_page_preview")


# ===========================================================================
# Harness
# ===========================================================================
# Declared locally rather than imported from `tests/unit/_ui_geometry.py`: that
# helper is owned by another task in this wave, and a shared fixture that
# changes shape under this file would turn a real regression into an import
# error. The duplication is four short functions.

@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _Sink:
    """The four methods a report sink has, remembering what it was told."""

    def __init__(self) -> None:
        self.lines = []

    def Info(self, msg=""):  # noqa: N802
        self.lines.append(("info", msg))

    def Warning(self, msg=""):  # noqa: N802
        self.lines.append(("warn", msg))

    def Error(self, msg=""):  # noqa: N802
        self.lines.append(("error", msg))

    def Blank(self):  # noqa: N802
        self.lines.append(("blank", ""))


def _projects_tree(root: Path, names) -> None:
    """A directory that looks like a FLEx projects root: <name>/<name>.fwdata."""
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")


def _needs_a_real_qwizard():
    """Skip when a sibling module has swapped a QWizard double into PyQt6.

    `test_wizard_page_flow.py` and `test_ui_gating.py` install a Qt double at
    import time and overwrite `QtWidgets.QWizard`/`QWizardPage` on whatever is
    in `sys.modules` -- including the real extension module, when real PyQt6
    was imported first. Constructing a real wizard is then impossible for the
    rest of the session. Copied from `test_034_step1_source_picker.py`.
    """
    if not isinstance(getattr(QtWidgets.QWizard, "WizardStyle", None), type):
        pytest.skip("a PyQt6 double is installed in this session (see docstring)")


@pytest.fixture
def wizard(qapp, tmp_path):
    """A real wizard with nothing bound -- which is how a run starts.

    Nothing here needs a live FLEx project: the flow declaration is fixed at
    construction and the emptiness predicates are injected per test (see
    `_force_empty`).
    """
    _needs_a_real_qwizard()
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    return sw.SelectionWizard(
        None, _Sink(), True,
        source_project_name="",
        projects_root=str(tmp_path),
        source_binder=lambda name: object(),
    )


def _flow(wizard):
    """`flow()` as a list, with a failure message that names what is missing."""
    assert hasattr(wizard, "flow"), (
        "SelectionWizard.flow() does not exist -- it is the declared order "
        "(attr, short_title, skippable, has_content) that FR-010 makes the "
        "single source of page order and skip eligibility"
    )
    return list(wizard.flow())


def _page_id(wizard, page):
    """The wizard's id for `page`, or -1 when it was never added."""
    for pid in wizard.pageIds():
        if wizard.page(pid) is page:
            return pid
    return -1


def _force_empty(wizard, monkeypatch, *attrs):
    """Make the named skippable pages answer "nothing to decide".

    WHY this seam: `nextId()` is specified to walk `flow()` and consult each
    entry's `has_content()`, so handing the wizard a declaration whose
    predicates answer `False` is the only injection a test needs -- no live
    project, no fabricated lexicon, and no reach into a page's internals. It
    also pins the requirement that `nextId()` reads the declaration *at call
    time* rather than baking a page list at construction.

    Returns the patched declaration.
    """
    original = _flow(wizard)          # fails loudly if flow() is absent
    wanted = set(attrs)
    patched = tuple(
        (attr, short, skippable,
         (lambda: False) if attr in wanted else has_content)
        for attr, short, skippable, has_content in original
    )
    monkeypatch.setattr(wizard, "flow", lambda: patched, raising=False)
    return patched


def _walk(wizard, limit=40):
    """Titles in the order a run actually shows them.

    `QWizard.next()` validates and switches; it is not gated on
    `isComplete()` (which only greys the Next *button*), so a run can be walked
    with nothing bound. `validateCurrentPage` is neutralised on the instance so
    that step 1's advance gate (FR-008, its own task and its own test) cannot
    stall a numbering assertion -- sip honours an instance-dict override for
    the C++ virtual call, verified.
    """
    wizard.validateCurrentPage = lambda: True
    wizard.restart()
    titles = []
    while wizard.currentPage() is not None and len(titles) < limit:
        titles.append(wizard.currentPage().title())
        before = wizard.currentId()
        wizard.next()
        if wizard.currentId() == before:
            break                      # last page, or refused
    assert len(titles) < limit, "the walk did not terminate"
    return titles


def _expected_titles(shorts):
    """`Step 1: ...`, `Step 2: ...` -- a number, no total (FR-009a)."""
    return [f"Step {i}: {short}" for i, short in enumerate(shorts, 1)]


# ===========================================================================
# The declaration itself (FR-010)
# ===========================================================================

def test_flow_declares_the_twelve_pages_in_order(wizard):
    """Order and skip eligibility, exactly as data-model section 1 fixes them."""
    got = [(attr, short, skippable) for attr, short, skippable, _ in _flow(wizard)]
    assert got == list(_DECLARED_FLOW)


def test_flow_entries_are_four_tuples(wizard):
    """`(attr, short_title, skippable, has_content)` -- nothing more."""
    for entry in _flow(wizard):
        assert len(entry) == 4, entry
        attr, short, skippable, _ = entry
        assert isinstance(attr, str) and attr
        assert isinstance(short, str) and short
        assert isinstance(skippable, bool)


def test_flow_declares_no_position_and_no_length(wizard):
    """A declaration that carried positions would be a total in disguise.

    Positions depend on which pages a given run shows, so an integer in the
    declaration could only be a slot number -- and a slot number is what
    produced the `of 10` the flow no longer has any way to state (FR-010).
    """
    for entry in _flow(wizard):
        assert not any(isinstance(field, int) and not isinstance(field, bool)
                       for field in entry), entry


def test_has_content_is_declared_exactly_for_the_skippable_pages(wizard):
    """`None` if and only if the page cannot drop out (data-model section 1).

    A skippable page with no predicate could never be skipped; an unskippable
    page with one invites a caller to consult it and skip anyway.
    """
    for attr, _short, skippable, has_content in _flow(wizard):
        if skippable:
            assert callable(has_content), attr
            # Called with no arguments, by `nextId()`, possibly on every
            # `completeChanged` -- so it takes none.
            assert isinstance(has_content(), bool), attr
        else:
            assert has_content is None, attr


def test_the_affix_and_stem_pickers_are_declared_unskippable(wizard):
    """FR-009d, stated on its own because it is the row most likely to 'improve'."""
    skippable = {attr: skip for attr, _s, skip, _h in _flow(wizard)}
    assert skippable["_page_items"] is False
    assert skippable["_page_stems"] is False


def test_every_declared_attr_resolves_to_a_page_added_once(wizard):
    """The declaration names real pages, and names each exactly once."""
    attrs = [attr for attr, _s, _k, _h in _flow(wizard)]
    assert len(attrs) == len(set(attrs)), f"duplicate attr in flow(): {attrs}"
    for attr in attrs:
        page = getattr(wizard, attr, None)
        assert page is not None, f"flow() names {attr}, which the wizard has not"
        assert _page_id(wizard, page) != -1, f"{attr} was declared but never added"


def test_the_flow_is_the_only_source_of_registration_order(wizard):
    """FR-010: registration is read off the declaration, not restated beside it."""
    by_object = {id(getattr(wizard, attr)): attr
                 for attr, _s, _k, _h in _flow(wizard)}
    registered = [by_object.get(id(wizard.page(pid))) for pid in wizard.pageIds()]
    assert registered == [attr for attr, _s, _k, _h in _flow(wizard)]


# ===========================================================================
# Numbering -- a full run (FR-009, SC-003)
# ===========================================================================

def test_a_full_run_numbers_every_page_consecutively_from_one(wizard):
    titles = _walk(wizard)
    assert titles == _expected_titles([short for _a, short, _k in _DECLARED_FLOW])


def test_no_title_shown_in_a_full_run_carries_a_total(wizard):
    """SC-003b / FR-009a: `of 10` is gone and cannot come back as `of 12`."""
    for title in _walk(wizard):
        assert re.search(r"of \d+", title) is None, title


def test_every_page_in_a_full_run_is_numbered(wizard):
    """SC-004: Texts was registered and unnumbered; nothing shown may be anonymous.

    The eleventh page carried no number at all while the other ten announced
    "of 10" -- which is how the flow came to be both mis-numbered and
    inconsistent at once. A page the operator is looking at, with a position in
    the run they are walking, that declines to say what that position is.
    """
    for title in _walk(wizard):
        assert re.match(r"^Step \d+: \S", title), title


# ===========================================================================
# Numbering -- a skipping run (FR-009b, SC-003a)
# ===========================================================================

def test_a_run_that_skips_every_skippable_page_still_counts_from_one(
        wizard, monkeypatch):
    """SC-003a: the shortest possible run reads 1, 2, 3, 4, 5 -- no holes.

    Everything that may drop out does. What is left is the five pages that
    always ask something, and their numbers are the numbers of what is shown,
    not of the slots they occupy in the declaration.
    """
    skippable = [attr for attr, _s, skip, _h in _flow(wizard) if skip]
    _force_empty(wizard, monkeypatch, *skippable)

    titles = _walk(wizard)
    assert titles == _expected_titles([
        "Projects", "Writing Systems", "Affix Picker", "Stem Picker",
        "Finish / Move",
    ])


def test_a_partly_empty_run_drops_only_the_empty_pages(wizard, monkeypatch):
    """FR-009c: a skippable page whose `has_content()` is true is never dropped.

    Phonology and Texts report empty; every other skippable page reports
    content. The two go, the rest stay, and the numbers close up over the gap.
    """
    _force_empty(wizard, monkeypatch, "_page_phonology", "_page_texts")

    titles = _walk(wizard)
    expected_shorts = [short for attr, short, _k in _DECLARED_FLOW
                       if attr not in ("_page_phonology", "_page_texts")]
    assert titles == _expected_titles(expected_shorts)
    # The pages after the hole moved *up*; nothing kept a stale number.
    # Phonology is declared fourth, so with it dropped the Affix Picker --
    # declared fifth -- becomes the run's FOURTH step. Derived from the expected
    # list as well as asserted literally, so this cannot go stale the way the
    # flow's old "of 10" titles did.
    assert titles[expected_shorts.index("Affix Picker")] == (
        f"Step {expected_shorts.index('Affix Picker') + 1}: Affix Picker"
    )
    assert "Step 4: Affix Picker" in titles
    assert "Step 10: Finish / Move" in titles


def test_a_skippable_page_with_content_survives_its_empty_neighbours(
        wizard, monkeypatch):
    """The conservative direction of FR-009c, isolated.

    Custom Fields and Rules are empty on either side of pages that are not.
    Nothing may generalise "this neighbourhood is empty" into a skip.
    """
    _force_empty(wizard, monkeypatch, "_page_custom_fields", "_page_rules")

    titles = _walk(wizard)
    assert "Custom Fields" not in " | ".join(titles)
    assert "Rules" not in " | ".join(titles)
    for short in ("Phonology", "Morphology Skeleton",
                  "Grammatical Dependencies", "Lexical-Entry Types", "Texts"):
        assert any(t.endswith(f": {short}") for t in titles), short


def test_the_pickers_are_shown_even_when_the_source_has_none(
        wizard, monkeypatch):
    """FR-009d: `skippable is False` outranks any emptiness answer.

    A source with no affixes and no stems is a real project, and the operator
    has to be told so on a page that says it. Here the pickers are *told* they
    are empty and must be shown regardless -- which is the assertion that
    survives someone later wiring predicates onto them.
    """
    every_attr = [attr for attr, _s, _k, _h in _flow(wizard)]
    wanted = set(every_attr) - {"_page_projects", "_page_writing_systems",
                                "_page_finish"}
    original = _flow(wizard)
    patched = tuple(
        (attr, short, skippable,
         (lambda: False) if attr in wanted else has_content)
        for attr, short, skippable, has_content in original
    )
    monkeypatch.setattr(wizard, "flow", lambda: patched, raising=False)

    titles = _walk(wizard)
    assert titles == _expected_titles([
        "Projects", "Writing Systems", "Affix Picker", "Stem Picker",
        "Finish / Move",
    ])


def test_nextId_resolves_the_next_shown_page_without_navigating(
        wizard, monkeypatch):
    """FR-009b: the hook is `nextId()`, so Next is right before the click.

    Qt asks `nextId()` to decide whether Next is enabled, which can be on
    every `completeChanged` -- so it has to answer from the declaration rather
    than by walking anything expensive.
    """
    _force_empty(wizard, monkeypatch, "_page_custom_fields", "_page_phonology")

    ws_page = wizard.page_writing_systems()
    assert ws_page.nextId() == _page_id(wizard, wizard.page_items()), (
        "with Custom Fields and Phonology empty, the page after Writing "
        "Systems is the Affix Picker"
    )
    # The last page in the declaration ends the run.
    assert wizard.page_finish().nextId() == -1


def test_nextId_never_returns_a_skipped_page(wizard, monkeypatch):
    """Whatever `nextId()` answers is a page the run will show."""
    _force_empty(wizard, monkeypatch, "_page_skeleton", "_page_gram_deps",
                 "_page_entry_types")
    dropped = {wizard._page_skeleton, wizard._page_gram_deps,
               wizard._page_entry_types}

    for attr, _s, _k, _h in _flow(wizard):
        page = getattr(wizard, attr)
        nid = page.nextId()
        if nid != -1:
            assert wizard.page(nid) not in dropped, attr


# ===========================================================================
# The pages that are never in the flow (FR-011)
# ===========================================================================

def test_the_excluded_pages_are_absent_from_the_flow(wizard):
    attrs = {attr for attr, _s, _k, _h in _flow(wizard)}
    for attr in _EXCLUDED_ATTRS:
        assert attr not in attrs, (
            f"{attr} is retained for back-compat and must never be in flow()"
        )


def test_the_excluded_pages_are_never_added_to_the_wizard(wizard):
    """Retained and reachable by accessor, but not part of any run."""
    for attr in _EXCLUDED_ATTRS:
        page = getattr(wizard, attr, None)
        assert page is not None, f"{attr} was removed, not excluded"
        assert _page_id(wizard, page) == -1, f"{attr} was added to the wizard"
    assert wizard.page_preview() is wizard._page_preview


def test_the_excluded_pages_carry_no_step_number(qapp):
    """`_PageScopeConflict` still says `Step 3 of 5` today -- a stale total.

    Renumbering it would be the wrong repair: it is not in the flow, so it has
    no number to state. Same for the preview page.
    """
    for factory in (sw._PageScopeConflict, sw._PagePreview):
        title = factory().title()
        assert re.search(r"[Ss]tep \d", title) is None, (factory.__name__, title)
        assert re.search(r"of \d+", title) is None, (factory.__name__, title)


def test_no_step_of_total_literal_survives_in_the_wizard_source():
    """The twelve hand-written `Step N of M` literals, as a source-level guard.

    A run-time walk only sees the pages a run shows; this catches a literal on
    a page nothing navigated to (which is exactly how `Step 3 of 5` survived).
    """
    src = Path(sw.__file__).read_text(encoding="utf-8")
    offenders = re.findall(r"Step \d+ of \d+", src)
    assert offenders == [], f"hard-coded step totals remain: {offenders}"


# ===========================================================================
# The step-1 split (FR-006, FR-007)
# ===========================================================================

def test_the_projects_page_keeps_its_accessor_and_owns_the_context(wizard):
    """`page_project_ws()` retains its name and its 23 call sites."""
    page = wizard.page_project_ws()
    assert page is wizard._page_projects
    assert callable(page.context)
    assert page.title() == "Step 1: Projects"


def test_the_writing_systems_page_owns_the_mapping(wizard):
    """FR-006: the tables, `ws_mapping()` and `selected_ws_ids()` move to page 2."""
    ws_page = wizard.page_writing_systems()
    assert ws_page is wizard._page_writing_systems
    assert ws_page is not wizard.page_project_ws()
    assert callable(ws_page.ws_mapping)
    assert callable(ws_page.selected_ws_ids)


def test_the_projects_page_no_longer_answers_for_writing_systems(wizard):
    """One owner, so no caller can read a mapping from the page that lost it."""
    page = wizard.page_project_ws()
    assert not hasattr(page, "ws_mapping")
    assert not hasattr(page, "selected_ws_ids")
