"""Base classes shared by the wizard's page classes (feature 039, T008).

Why this module exists
----------------------
`_FlowPage` is the base every page in `SelectionWizard.flow()` derives from, and
it is the reason the flow declaration can stay a single list: each page resolves
its own successor from it at call time. It relocated here verbatim because it
references nothing outside `QtWidgets` -- it is the one part of the old monolith
with no coupling at all to the rest of it.

The three mixins below exist for a different reason: measurement. Feature 039
counted the duplication in the 6512-line `selection_wizard.py` and found ~505
lines of it that were exactly, not approximately, repeated:

* `_get_source` / `_get_target` appeared nine times each, with seven and eight
  of those copies structurally identical.
* the whole-block checkbox cluster -- seven methods -- appeared four times over,
  differing only in docstring wording and the name of a loop variable.
* `_get_affix_picks` / `_get_stem_picks` appeared twice each, byte-equivalent.

`_BlockPage` is domain-justified as well as DRY-motivated: the four pages that
carry the duplicated cluster are exactly the four "independent block" (Model-B)
pages of `specs/wizard-selection-roadmap.md`, whose selection model *is*
wholesale NONE/ALL over one tree. The base is the model, written once.

What is deliberately absent
---------------------------
* The four block pages' `collect_*` APIs. Their contracts genuinely differ --
  `leaf_item_picks() -> dict`, `collect_rules_picks() -> Optional[frozenset]`
  (where `None` means transfer-all), `collect_phonology_picks() -> dict`,
  `collect_entry_type_picks() -> dict` -- and a base method that had to be
  overridden four ways would be a shared name, not shared behaviour.
* `deselected_needed_guids()`, which only two of the four pages have.
* `_PageSkeleton`. It has an `_on_item_changed` and it uses `_mirroring`, but
  for template-slot semantics, not whole-block semantics. Giving it
  `_BlockPage` would be pattern-matching on method names.
* No dual-mode `if __package__:` guard: like `wizard_roles`, this module imports
  `QtCore`/`QtWidgets` and nothing from the package, so the two import paths are
  already identical (feature 039 FR-007).
"""
from __future__ import annotations

from PyQt6 import QtWidgets

# ---------------------------------------------------------------------------
# Flow-aware page base (T013, FR-009b)
# ---------------------------------------------------------------------------

class _FlowPage(QtWidgets.QWizardPage):
    """A page that resolves its successor from `SelectionWizard.flow()`.

    WHY `nextId()` AND NOT A FILTERED PAGE LIST
    -------------------------------------------
    `QWizardPage.nextId()` is Qt's own hook for a conditional flow, and Qt calls
    it to decide whether Next is even *enabled*. Resolving the successor here
    means the button is right before the click, rather than the alternative --
    registering only the pages a run "will" need, which has to guess before the
    operator has picked anything and cannot change its mind afterwards.

    Back needs nothing: Qt replays its own stack of visited pages, so an
    operator returning through a run that skipped pages retraces exactly the
    pages they saw.

    `flow()` is read at CALL TIME, never cached. The operator may go back and
    pick an affix after Morphology Skeleton was skipped for having none, and the
    page then re-enters the flow -- a baked list could not.
    """

    # -- The page header (T041, FR-004 / FR-012) ---------------------------
    # Every page in the flow carries one. `subTitle()` stays the string of
    # record -- the wizard sets `IgnoreSubTitles` so Qt stops drawing it, and
    # the header renders it instead in a label that WRAPS. Qt's own subtitle
    # does not wrap: it elides, which is how a description could end mid-word
    # with nothing to say it had been cut (FR-013).

    def header(self):
        """This page's laid-out header row, or None before one is installed.

        Returns None rather than raising for a page constructed standalone --
        a good deal of the unit suite builds pages with no wizard at all, and
        a header is something the wizard installs, not something a page makes
        for itself.
        """
        return getattr(self, "_page_header", None)

    def install_header(self, header) -> None:
        """Adopt `header` as row 0 of this page's own layout.

        Laid out, never positioned. That is the whole of FR-004: a box layout
        allocates disjoint x-intervals to the description and the controls, so
        a description grown to any wrapped height cannot intersect the strip --
        it grows the header's height instead. The floating bar this replaces
        had no layout relationship with anything, so nothing could move out of
        its way and it painted an opaque background to stay legible on top of
        whatever it covered.

        Idempotent: installing twice on one page is a no-op, so a second call
        cannot stack two header rows.
        """
        if getattr(self, "_page_header", None) is not None:
            return
        layout = self.layout()
        if layout is None:
            return
        self._page_header = header
        header.setParent(self)
        insert = getattr(layout, "insertWidget", None)
        if callable(insert):
            insert(0, header)
        else:                       # not a box layout: better appended than lost
            layout.addWidget(header)
        header.set_description(self.subTitle())

    def refresh_header_description(self) -> None:
        """Re-render `subTitle()` into the header. Cheap; safe before install.

        Called on page entry because `subTitle()` is not frozen at construction
        -- the Finish page takes its subtitle from the host's confirmation gate,
        and a page may restate itself in `initializePage`.
        """
        header = self.header()
        if header is not None:
            header.set_description(self.subTitle())

    def nextId(self) -> int:  # noqa: N802 -- Qt naming
        """The next page this run will SHOW, or -1 to end the run.

        Walks the declaration forward from this page and returns the first entry
        that is either unskippable or whose `has_content()` says yes. A
        predicate that raises is treated as "yes" for the same reason `None` is
        (FR-009c): a page that is wrongly shown costs a click, a page that is
        wrongly skipped costs a decision.
        """
        wizard = self.wizard()
        if wizard is None or not hasattr(wizard, "flow"):
            # Constructed standalone (several unit tests do) or hosted by a
            # wizard that predates the declaration: fall back to Qt's
            # registration order rather than refusing to navigate.
            return super().nextId()
        entries = list(wizard.flow())
        here = -1
        for idx, (attr, _short, _skippable, _has) in enumerate(entries):
            if getattr(wizard, attr, None) is self:
                here = idx
                break
        if here == -1:
            return super().nextId()

        for attr, _short, skippable, has_content in entries[here + 1:]:
            page_id = wizard.flow_page_id(attr)
            if page_id == -1:
                continue                    # declared but not registered
            if not skippable or has_content is None:
                return page_id              # FR-009d outranks any emptiness
            try:
                if has_content():
                    return page_id
            except Exception:  # noqa: BLE001 -- unsure means shown
                return page_id
        return -1                           # last shown page ends the run


# ---------------------------------------------------------------------------
# Shared bases (feature 039 T008 declares them; T027 fills them in)
# ---------------------------------------------------------------------------
# Declared here in the relocation commit and left empty on purpose. US1 and US2
# are reviewable as pure relocations -- `git diff -M` renders their hunks as
# renames -- and a commit that both moved code and rewrote it would forfeit
# that. The method bodies arrive in US3 (T027), together with the deletion of
# the copies they replace, so the dedup is one self-contained diff.


class _ProjectHandlesMixin:
    """`_get_source()` / `_get_target()`, written once (T027).

    Depends on the page being hosted by a wizard exposing `page_project_ws()`,
    and on that page exposing `context()` and `_host`. Nothing else.
    """


class _PickDerivedMixin:
    """`_get_affix_picks()` / `_get_stem_picks()`, written once (T027).

    For the two pages whose contents derive from earlier picks rather than from
    the source project directly.
    """


class _BlockPage(_FlowPage):
    """The Model-B "independent block" page: one tree, wholesale NONE/ALL (T027).

    Depends on exactly three attributes, all set by the subclass's own
    `__init__`: `self._tree`, `self._whole_block`, `self._mirroring`.
    """

    # Which item-data role the subclass's tree keys its "group" / "item"
    # distinction on. The only thing that varied across the four otherwise
    # identical `_iter_item_rows` copies, so it is the only thing the base
    # takes as a parameter. Subclasses set it; `None` means the page has not
    # declared one and `_iter_item_rows` yields nothing.
    _kind_role = None
