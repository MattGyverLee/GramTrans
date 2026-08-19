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

from PyQt6 import QtCore, QtWidgets

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
# Shared bases (feature 039 T027)
# ---------------------------------------------------------------------------
# Each method below existed in several byte-identical copies before the split.
# The counts are measured, not estimated: `_get_source` had nine copies of which
# seven were structurally identical, `_get_target` nine of which eight were, the
# two pick accessors two each, and the whole-block cluster four each. Where the
# copies' docstrings differed, the most informative wording is the one kept --
# it is the one that says WHY, and losing it is the actual cost of deduplicating
# by hand (FR-010).


class _ProjectHandlesMixin:
    """`_get_source()` / `_get_target()` for the pages that read the project pair.

    Both walk the same path: this page -> its wizard -> `page_project_ws()` ->
    that page's `context()`. Both return None rather than raising at every step,
    because a page is constructed standalone by a good deal of the unit suite and
    by `_PagePreview`'s host, and "no source bound yet" is a normal state on
    every page before step 1 is complete -- not an error.

    Depends on nothing but those two duck-typed calls, which is why no page class
    has to import `_PageProjects` to reach it.

    Applied to `_PageItemPicker`, `_PageStemPicker`, `_PageSkeleton`,
    `_PageGramDeps`, `_PageCustomFields`, `_PageRules`, `_PagePhonology` and
    `_PageTexts`. `_PageEntryTypes` overrides BOTH methods -- see the comments on
    its overrides in `wizard_pages_blocks.py`; the divergence is real, predates
    the split, and changing it would be a behaviour change.
    """

    def _get_source(self):
        """Return the source project handle from page 0, or None.

        Prefers `context().source_handle` -- the handle bound when the operator
        chose a source on step 1 -- and falls back to the page's `_host`, which
        is what the FlexTools path supplies directly.
        """
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is not None:
                h = getattr(ctx, "source_handle", None)
                if h is not None:
                    return h
            return getattr(p0, "_host", None)
        except Exception:  # noqa: BLE001
            return None

    def _get_target(self):
        """Return the target project handle from page-0 context, or None.

        FR-018(e): the RunContext, set when the operator picks a target on step
        1, exposes `.target_handle`. With no context or no target yet this
        returns None so the inventory builder is called with `target=None` --
        the Target column renders blank instead of the page failing to build.
        """
        try:
            w = self.wizard()
            if w is None:
                return None
            p0 = w.page_project_ws()
            if p0 is None:
                return None
            ctx = p0.context()
            if ctx is None:
                return None
            return getattr(ctx, "target_handle", None)
        except Exception:  # noqa: BLE001
            return None


class _PickDerivedMixin:
    """`_get_affix_picks()` / `_get_stem_picks()` for the two pick-derived pages.

    `_PageSkeleton` and `_PageGramDeps` do not enumerate the source project;
    they derive their contents from what was picked on the affix and stem pages.
    Both reach those picks the same way -- through the wizard's named accessors,
    never by importing the picker classes -- and both treat any failure as "no
    picks", so a page whose predecessor is not yet built renders empty instead of
    refusing to build.
    """

    def _get_affix_picks(self) -> frozenset:
        """Retrieve affix_picks from the item-picker page (index 1)."""
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_items = w.page_items()
            if page_items is None:
                return frozenset()
            sel = page_items.collect_selection()
            return sel.affix_picks
        except Exception:  # noqa: BLE001
            return frozenset()

    def _get_stem_picks(self) -> frozenset:
        """019: retrieve stem_picks from the dedicated Stems page (mirror of
        _get_affix_picks). The skeleton builder itself stays AFFIX-ONLY per
        FR-013; this accessor exists for parity and downstream use.
        """
        try:
            w = self.wizard()
            if w is None:
                return frozenset()
            page_stems = w.page_stems()
            if page_stems is None:
                return frozenset()
            return page_stems.stem_picks()
        except Exception:  # noqa: BLE001
            return frozenset()


class _BlockPage(_FlowPage):
    """The Model-B "independent block" page: one tree, wholesale NONE/ALL.

    `specs/wizard-selection-roadmap.md` names two selection models. This is the
    second: the page owns one tree of group headers over checkable item rows,
    plus a single whole-block tristate checkbox that reflects and drives them.
    Nothing on the page derives from an earlier page's picks.

    The cluster below depends on exactly three attributes, all set by the
    subclass's own `__init__`:

      * `self._tree`         -- the QTreeWidget of groups and items
      * `self._whole_block`  -- the tristate QCheckBox
      * `self._mirroring`    -- the reentrancy flag that stops a programmatic
                               `setCheckState` from being read back as a user
                               edit

    and on one class attribute, `_kind_role`.

    NOT in this base, on purpose: each page's `collect_*` API. Their contracts
    genuinely differ -- `leaf_item_picks() -> dict`,
    `collect_rules_picks() -> Optional[frozenset]` where `None` means
    transfer-all rather than nothing, `collect_phonology_picks() ->
    dict[GrammarCategory, set]`, `collect_entry_type_picks() -> dict` -- so a
    base method overridden four different ways would share a name and nothing
    else. `deselected_needed_guids()`, which only two of the four have, is out
    for the same reason.
    """

    # Which item-data role this page's tree keys its "group" / "item"
    # distinction on. It was the ONLY thing that varied across the four
    # otherwise-identical `_iter_item_rows` copies, so it is the only thing the
    # base takes as a parameter. Subclasses set it; `None` means the page has
    # not declared one, and `_iter_item_rows` then yields nothing rather than
    # comparing every row against None and silently matching the wrong ones.
    _kind_role = None

    def _iter_item_rows(self):
        """Yield (group_item, item) for every checkable item row in the tree.

        One level of groups over one level of items, which is the shape all four
        block pages build. `_PageEntryTypes` overrides this: its trees nest, so
        it walks the full depth.
        """
        if self._kind_role is None:
            return
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group.data(0, self._kind_role) != "group":
                continue
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, self._kind_role) == "item":
                    yield group, item

    def _on_whole_block_clicked(self, _checked: bool = False) -> None:
        """User toggled the whole-block checkbox: check-all or uncheck-all.

        Ignores Qt's cycled tristate state and decides from the tree so the
        behaviour is deterministic (partial => check-all, full => uncheck-all).
        """
        if not self._has_any_item():
            self._refresh_whole_block()
            return
        want_checked = not self._all_items_checked()
        self._set_all_items(want_checked)
        self._refresh_whole_block()

    def _set_all_items(self, checked: bool) -> None:
        state = (QtCore.Qt.CheckState.Checked if checked
                 else QtCore.Qt.CheckState.Unchecked)
        self._mirroring = True
        try:
            for _grp, item in self._iter_item_rows():
                item.setCheckState(0, state)
        finally:
            self._mirroring = False

    def _refresh_whole_block(self) -> None:
        """Reflect the aggregate item state on the whole-block tristate box.

        Empty block (no items at all) => unchecked + disabled, NOT vacuously
        fully-selected, per the edge-case invariant in the contract
        (Acceptance 1.3). A block with nothing in it has nothing selected; a box
        that read "all" would offer to transfer a set the page cannot describe.
        """
        self._mirroring = True
        try:
            if not self._has_any_item():
                self._whole_block.setEnabled(False)
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
                return
            self._whole_block.setEnabled(True)
            checked = sum(
                1 for _g, it in self._iter_item_rows()
                if it.checkState(0) == QtCore.Qt.CheckState.Checked
            )
            total = sum(1 for _ in self._iter_item_rows())
            if checked == 0:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Unchecked)
            elif checked == total:
                self._whole_block.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                self._whole_block.setCheckState(
                    QtCore.Qt.CheckState.PartiallyChecked
                )
        finally:
            self._mirroring = False

    def _on_item_changed(self, item, column) -> None:
        if self._mirroring or column != 0:
            return
        self._refresh_whole_block()

    def _has_any_item(self) -> bool:
        for _ in self._iter_item_rows():
            return True
        return False

    def _all_items_checked(self) -> bool:
        any_item = False
        for _g, item in self._iter_item_rows():
            any_item = True
            if item.checkState(0) != QtCore.Qt.CheckState.Checked:
                return False
        return any_item

    def whole_block_on(self) -> bool:
        """True iff any item row in this block is currently checked."""
        for _g, item in self._iter_item_rows():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                return True
        return False
