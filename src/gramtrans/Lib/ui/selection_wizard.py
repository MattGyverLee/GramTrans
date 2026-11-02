"""Selection Wizard (Phase 3c, plan.md Refinement 3, 2026-07-01).

A QWizard (it replaced the old single-window `main_window.py`, now removed).  The existing
widgets are re-hosted verbatim; no widget logic is rewritten.  How many pages a
run shows is a property of the run, not of this module -- see `flow()`.

Pages: there is no page list here, deliberately. `SelectionWizard.flow()` is the
single declaration of which pages exist, in what order, and which of them may
drop out of a run that has nothing for them to decide (feature 036 FR-010). A
second list in this docstring is how the old one came to describe five pages
while eleven were registered.

Two facts the declaration cannot state and a reader needs:
  * Projects and Writing Systems are two pages (036 FR-006). Binding a pair of
    projects and mapping their writing systems are separate decisions, and the
    second is not answerable until the first is done.
  * Finish / Move is the ONLY write point.

Writing-system rules:
- Enumerate ACTIVE writing systems only (analysis + vernacular active in
  the project; not the full installed superset).
- The two-stage NEEDS_WS_MAPPING handshake is RETIRED -- page-1 handles WS
  once, project-level.

Constitution alignment:
- Principle III: the only write is in the page-5 Finish handler, which
  first queries `plan.excluded_lossy_count()` and blocks/confirms if > 0.
- Principle V: per-item deselection surfaces on page 3; EXCLUDED-LOSSY
  warnings surface on page 4 (StatsPanel).
"""
from __future__ import annotations

import dataclasses
import logging
from contextlib import contextmanager  # noqa: F401
from typing import Optional, Set  # noqa: F401

from PyQt6 import QtCore, QtWidgets

# Module logger. `_log` on the page classes is a REPORT-SINK method (it writes to
# the run report the operator reads); this is the diagnostic channel, for
# tracebacks that belong in the log rather than in the report.
_module_log = logging.getLogger(__name__)

if __package__:
    from .. import api as gt_api
    from ..models import (
        CategoryScope,
        ConflictMode,
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        Selection,
        WSKind,
        WSMapping,
        WSMappingEntry,
        _DEFAULT_CONFLICT_MODES,
    )
    from ..selection import (
        PickerState,
        PosGroupedAffixInventory,
        SourceAffixInventory,
        affix_label_runs,
        build_deps_inventory,
        build_entry_types_inventory,
        build_excluded_lossy_warnings,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_pos_grouped_inventory,
        build_rules_inventory,
        build_selection,
        build_skeleton_inventory,
        build_text_inventory,
        collapse_entry_types,
        collapse_phonology,
        collapse_pos_grouped,
        entry_types_missing_ref_warnings,
        mirror_check_state,
        phonology_uses_untraversed_rules,
    )
    from ..ws_fonts import WsFontRegistry, WsRole
    from .stats_panel import StatsPanel
    from .source_picker import SourcePickerDialog
    from .target_picker import TargetPickerDialog
    from .ws_font_delegate import attach_ws_font_delegate, set_ws_runs
    from .merge_preview_pane import MergePreviewPane, PreviewRequest, _action_to_mode
    from .theme import ThemeCornerBar, install_theme
    from .page_header import PageHeader
    from ..merge_preview import MergePreviewService, OVERWRITE, NEW
    from ..models import SimilarResolution
    from ..preview import render_preview_extra_lines, preview_extra_lines_or_warning
    from ..report import RunReport
    from ..ws_mapping import closest_ws_defaults
else:
    import api as gt_api  # type: ignore
    from models import (  # type: ignore
        CategoryScope,  # noqa: F401
        ConflictMode,  # noqa: F401
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        Selection,  # noqa: F401
        WSKind,  # noqa: F401
        WSMapping,  # noqa: F401
        WSMappingEntry,  # noqa: F401
        _DEFAULT_CONFLICT_MODES,
    )
    from selection import (  # type: ignore
        PickerState,
        PosGroupedAffixInventory,  # noqa: F401
        SourceAffixInventory,
        affix_label_runs,  # noqa: F401
        build_deps_inventory,
        build_entry_types_inventory,  # noqa: F401
        build_excluded_lossy_warnings,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_pos_grouped_inventory,  # noqa: F401
        build_rules_inventory,  # noqa: F401
        build_selection,
        build_skeleton_inventory,  # noqa: F401
        build_text_inventory,  # noqa: F401
        collapse_entry_types,
        collapse_phonology,
        collapse_pos_grouped,  # noqa: F401
        entry_types_missing_ref_warnings,
        mirror_check_state,  # noqa: F401
        phonology_uses_untraversed_rules,
    )
    from ws_fonts import WsFontRegistry, WsRole  # type: ignore  # noqa: F401
    from stats_panel import StatsPanel  # type: ignore
    from source_picker import SourcePickerDialog  # type: ignore  # noqa: F401
    from target_picker import TargetPickerDialog  # type: ignore  # noqa: F401
    from ws_font_delegate import attach_ws_font_delegate, set_ws_runs  # type: ignore  # noqa: F401
    from merge_preview_pane import MergePreviewPane, PreviewRequest, _action_to_mode  # type: ignore  # noqa: F401
    from theme import ThemeCornerBar, install_theme  # type: ignore
    from page_header import PageHeader  # type: ignore
    from merge_preview import MergePreviewService, OVERWRITE, NEW  # type: ignore  # noqa: F401
    from models import SimilarResolution  # type: ignore  (already imported above but needs bare-name alias)  # noqa: F401
    from preview import render_preview_extra_lines, preview_extra_lines_or_warning  # type: ignore
    from report import RunReport  # type: ignore
    from ws_mapping import closest_ws_defaults  # type: ignore  # noqa: F401

if __package__:
    from ..gate import resolve_gate as _resolve_gate
    from ..progress import (
        SourceCounts,
        label_for,
        rate_for,
        reporting,
        warrants_indicator,
    )
    from .progress_indicator import deferred, immediate
else:
    from gate import resolve_gate as _resolve_gate  # type: ignore
    from progress import (  # type: ignore
        SourceCounts,
        label_for,  # noqa: F401
        rate_for,  # noqa: F401
        reporting,  # noqa: F401
        warrants_indicator,  # noqa: F401
    )
    from progress_indicator import deferred, immediate  # type: ignore  # noqa: F401

# ---------------------------------------------------------------------------
# Names this facade still calls, now living in the page modules
# ---------------------------------------------------------------------------
# The split moved the pages out; these are the pieces the facade's own
# remaining code -- _PagePreview, _PageFinish, _compute_wizard_plan and
# SelectionWizard -- reads directly. Ordinary imports, not re-exports.
if __package__:
    from .wizard_page_base import _FlowPage
    from .wizard_plan import (  # noqa: F401
        _PLAN_FAILURE_ATTR, _compute_wizard_plan, _entry_types_missing_ref_for,
        _kl010_notice, _phonology_excluded_lossy_for,
        _phonology_nc_or_phoneme_trimmed, _set_plan_failure_reason,
        _take_plan_failure_reason, _warn_plan_failure,
    )
    from .wizard_page_projects import _PageProjects
    from .wizard_page_texts import _PageTexts
    from .wizard_page_ws import _PageWritingSystems
    from .wizard_pages_blocks import (
        _PageCustomFields,
        _PageEntryTypes,
        _PagePhonology,
        _PageRules,
    )
    from .wizard_pages_deferred import _PageScopeConflict
    from .wizard_pages_pickers import _PageItemPicker, _PageStemPicker
    from .wizard_pages_skeleton import _PageGramDeps, _PageSkeleton
    from .wizard_widgets import _page_progress
else:
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_plan import (  # type: ignore
        _PLAN_FAILURE_ATTR, _compute_wizard_plan, _entry_types_missing_ref_for,  # noqa: F401
        _kl010_notice, _phonology_excluded_lossy_for,  # noqa: F401
        _phonology_nc_or_phoneme_trimmed, _set_plan_failure_reason,  # noqa: F401
        _take_plan_failure_reason, _warn_plan_failure,
    )
    from wizard_page_projects import _PageProjects  # type: ignore
    from wizard_page_texts import _PageTexts  # type: ignore
    from wizard_page_ws import _PageWritingSystems  # type: ignore
    from wizard_pages_blocks import (  # type: ignore
        _PageCustomFields,
        _PageEntryTypes,
        _PagePhonology,
        _PageRules,
    )
    from wizard_pages_deferred import _PageScopeConflict  # type: ignore
    from wizard_pages_pickers import _PageItemPicker, _PageStemPicker  # type: ignore
    from wizard_pages_skeleton import _PageGramDeps, _PageSkeleton  # type: ignore
    from wizard_widgets import _page_progress  # type: ignore


# ---------------------------------------------------------------------------
# Compatibility re-exports (feature 039 FR-006)
# ---------------------------------------------------------------------------
# `selection_wizard` is the name ~20 test modules import and bind names
# off, and the name of the one production import there is
# (`SelectionWizard`, at `gramtrans.py:249`). Splitting the pages out
# must not change what `selection_wizard.X` resolves to, so every
# relocated name is re-exported here -- and `test_039_module_split.py`
# guard 2 asserts the list is complete rather than trusting it to stay
# so.
#
# Eagerly, never lazily. `test_wizard_page_flow.py:99/107` replaces
# `QtWidgets.QWizard`/`QWizardPage` in `sys.modules` at import time, so
# each `class _PageX(QtWidgets.QWizardPage)` captures whichever base is
# installed at ITS OWN module's import moment. Importing every page
# module here, from one place, is what keeps that base identical across
# all of them; a lazy import added later would silently produce a page
# on a different base than its siblings. See
# `_ui_geometry.needs_a_real_qwizard()`, which documents the hazard.
if __package__:
    from .wizard_page_base import (
        _BlockPage, _PickDerivedMixin, _ProjectHandlesMixin,  # noqa: F401
    )
    from .wizard_page_ws import (
        _enumerate_active_ws_ids, _enumerate_ws_by_kind,  # noqa: F401
    )
    from .wizard_pages_blocks import (
        _ET_MODE_NEW, _ET_MODE_OVERWRITE, _PHON_MODE_NEW,  # noqa: F401
        _PHON_MODE_OVERWRITE,  # noqa: F401
    )
    from .wizard_pages_deferred import (
        _CATEGORY_TOGGLES, _CONFLICT_LABELS, _CUSTOM_FIELDS_ONLY,  # noqa: F401
        _GOLD_RESERVED, _SCHEMA_CATEGORIES, _SCOPE_LABELS, _allowed_modes,  # noqa: F401
    )
    from .wizard_roles import (
        _CF_GUID_ROLE, _CF_KIND_ROLE, _CF_LEVEL_LABELS, _CF_STATUS_ROLE,  # noqa: F401
        _DEPS_CAT_ROLE, _DEPS_STATUS_ROLE, _ET_CAT_ROLE, _ET_GUID_ROLE,  # noqa: F401
        _ET_KIND_ROLE, _ET_STATUS_ROLE, _GUID_ROLE, _IS_PRODUCES,  # noqa: F401
        _ITEM_CAT_ROLE, _ITEM_STATUS_ROLE, _KIND_ROLE, _PHON_CAT_ROLE,  # noqa: F401
        _PHON_GUID_ROLE, _PHON_KIND_ROLE, _PHON_STATUS_ROLE, _ROLE_ROLE,  # noqa: F401
        _RULES_GUID_ROLE, _RULES_KIND_ROLE, _RULES_STATUS_LABELS,  # noqa: F401
        _RULES_STATUS_ROLE, _SKEL_CAT_ROLE, _SKEL_GUID_ROLE,  # noqa: F401
        _SKEL_KIND_ROLE, _SKEL_OWNER_ROLE, _SKEL_READ_ONLY,  # noqa: F401
        _SKEL_STATUS_ROLE, _STATUS_LABELS,  # noqa: F401
    )
    from .wizard_widgets import (
        _PREVIEW_PANE_MIN_WIDTH, _TREE_PANE_MIN_WIDTH,  # noqa: F401
        _carry_full_values_in_tooltips, _count_affixes_in_node,  # noqa: F401
        _elide_over_narrow_columns, _item_views_of, _make_group_item,  # noqa: F401
        _make_tree_pane_splitter, _operation_failed_note,  # noqa: F401
        _set_item_text_with_tooltip, _show_failure_row, _source_counts_of,  # noqa: F401
    )
else:
    from wizard_page_base import (  # type: ignore
        _BlockPage, _PickDerivedMixin, _ProjectHandlesMixin,  # noqa: F401
    )
    from wizard_page_ws import (  # type: ignore
        _enumerate_active_ws_ids, _enumerate_ws_by_kind,  # noqa: F401
    )
    from wizard_pages_blocks import (  # type: ignore
        _ET_MODE_NEW, _ET_MODE_OVERWRITE, _PHON_MODE_NEW,  # noqa: F401
        _PHON_MODE_OVERWRITE,  # noqa: F401
    )
    from wizard_pages_deferred import (  # type: ignore
        _CATEGORY_TOGGLES, _CONFLICT_LABELS, _CUSTOM_FIELDS_ONLY,  # noqa: F401
        _GOLD_RESERVED, _SCHEMA_CATEGORIES, _SCOPE_LABELS, _allowed_modes,  # noqa: F401
    )
    from wizard_roles import (  # type: ignore
        _CF_GUID_ROLE, _CF_KIND_ROLE, _CF_LEVEL_LABELS, _CF_STATUS_ROLE,  # noqa: F401
        _DEPS_CAT_ROLE, _DEPS_STATUS_ROLE, _ET_CAT_ROLE, _ET_GUID_ROLE,  # noqa: F401
        _ET_KIND_ROLE, _ET_STATUS_ROLE, _GUID_ROLE, _IS_PRODUCES,  # noqa: F401
        _ITEM_CAT_ROLE, _ITEM_STATUS_ROLE, _KIND_ROLE, _PHON_CAT_ROLE,  # noqa: F401
        _PHON_GUID_ROLE, _PHON_KIND_ROLE, _PHON_STATUS_ROLE, _ROLE_ROLE,  # noqa: F401
        _RULES_GUID_ROLE, _RULES_KIND_ROLE, _RULES_STATUS_LABELS,  # noqa: F401
        _RULES_STATUS_ROLE, _SKEL_CAT_ROLE, _SKEL_GUID_ROLE,  # noqa: F401
        _SKEL_KIND_ROLE, _SKEL_OWNER_ROLE, _SKEL_READ_ONLY,  # noqa: F401
        _SKEL_STATUS_ROLE, _STATUS_LABELS,  # noqa: F401
    )
    from wizard_widgets import (  # type: ignore
        _PREVIEW_PANE_MIN_WIDTH, _TREE_PANE_MIN_WIDTH,  # noqa: F401
        _carry_full_values_in_tooltips, _count_affixes_in_node,  # noqa: F401
        _elide_over_narrow_columns, _item_views_of, _make_group_item,  # noqa: F401
        _make_tree_pane_splitter, _operation_failed_note,  # noqa: F401
        _set_item_text_with_tooltip, _show_failure_row, _source_counts_of,  # noqa: F401
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# T024 / FR-029: the window floor, as ONE declared value for the wizard as a
# whole. 1100 px had been the floor since feature 004 widened the window for the
# tree-beside-preview layout, and it was never a measurement -- it is the width
# that layout happened to want on the machine it was built on. A 1366x768
# laptop, which is what a field linguist actually has, can show 1100 px only by
# surrendering every other window.
#
# Named rather than inlined because FR-029 is a structural claim as well as a
# behavioural one: no page negotiates its own floor, so no page can quietly
# become the real arbiter of how narrow the window may get. The per-pane
# minimums below are deliberately far smaller and their sum is checked against
# this number by the US3 test module.
MIN_WINDOW_WIDTH = 900

# Unchanged by feature 036 (US3 lowers the width only) and named here so the
# pair reads as one geometry decision instead of one constant and one literal.
MIN_WINDOW_HEIGHT = 680


# ---------------------------------------------------------------------------
# Skip-predicate helper: does a cheap count justify showing a page?
# ---------------------------------------------------------------------------
# Read only by `SelectionWizard`'s own `flow()` predicates, which is why it
# stayed in the facade when the pages moved out. (Before feature 039 this
# carried a second, stale copy of the `_allowed_modes` divider, which described
# a function three hundred lines further down.)

def _count_says_content(count) -> bool:
    """Turn a cheap count into "show this page?" -- unknown means show.

    `None` out of `SourceCounts` means "could not be had cheaply", never "zero".
    Treating it as zero would skip a page whose contents were merely
    unmeasurable, which is the one direction FR-009c does not tolerate.
    """
    return True if count is None else count > 0


# ---------------------------------------------------------------------------
# Shared phonology EXCLUDED-LOSSY channel (spec 010 US5 — T024/T025/T026b)
# ---------------------------------------------------------------------------


class _PagePreview(QtWidgets.QWizardPage):
    """Preview / StatsPanel. NOT IN THE FLOW.

    Retained and reachable through `page_preview()` for back-compat, but absent
    from `SelectionWizard.flow()` and never registered: the dry run and its
    report live on the Finish page. Like `_PageScopeConflict` it therefore
    carries NO step number -- "(inactive)" is the whole of what its title has to
    say, and giving it a number would claim a position in a run it is not part
    of (T015, FR-011).

    Re-hosts the existing StatsPanel widget verbatim.

    It keeps no plan of its own: `_PageFinish` computes and caches the plan it
    moves (feature 015), and since this page is never registered, Qt never asks
    it `isComplete()` -- the old `_cached_plan` / `cached_plan()` /
    `isComplete()` trio was dead and was removed (issue #9).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Preview (inactive)")
        self.setSubTitle(
            "Review the planned transfer before committing. "
            "Warnings (entries with missing references) are highlighted."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self._preview_btn = QtWidgets.QPushButton("Compute Preview", self)
        self._preview_btn.clicked.connect(self._on_preview)
        layout.addWidget(self._preview_btn)
        self._stats = StatsPanel(self)
        layout.addWidget(self._stats, 1)

    def _on_preview(self) -> None:
        """Thin wrapper delegating to _compute_wizard_plan (DR-5, FR-005)."""
        wizard = self.wizard()
        if wizard is None:
            return
        plan, report = _safe_compute_wizard_plan(wizard)
        if plan is None:
            # DR-5: wrapper owns QMessageBox dialogs.
            _warn_plan_failure(self, wizard)
            return
        # Issue #162: Preview-only extra lines, shown before any Move.
        self._stats.set_report(report, preview_extra_lines_or_warning(
            plan, render_preview_extra_lines))


# ---------------------------------------------------------------------------
# Module-level plan assembler (DR-4, FR-004)
# ---------------------------------------------------------------------------

def _safe_compute_wizard_plan(wizard) -> tuple:
    """`_compute_wizard_plan`, with the Qt slot boundary enforced.

    Both callers are clicked buttons, and a slot is called from C++: an
    exception raised in one has no Python frame above it to catch, so PyQt6
    answers it with `sys.excepthook` and then `qFatal()`/`abort()`. Depending on
    the build that is either a window that vanishes with no dialog or a button
    that silently does nothing -- both of which this code has already shipped
    (`standalone/crashlog.py` documents the abort; a non-1:1 WS mapping raising
    out of step 6 was the dead Dry-run button).

    `_compute_wizard_plan` already documents "(None, None) on any failure", so
    this adds no new contract -- it makes the existing one true even for a step
    that was written to raise. The reason is logged and carried to the dialog:
    swallowing it silently is what made the original defect take a rebuild and a
    Windows Error Reporting record to find.
    """
    try:
        return _compute_wizard_plan(wizard)
    except Exception as exc:  # noqa: BLE001 - a slot must not raise into C++
        _module_log.exception("plan assembly failed")
        _set_plan_failure_reason(
            wizard,
            _take_plan_failure_reason(wizard)
            or f"GramTrans could not build the transfer plan.\n\n"
               f"{type(exc).__name__}: {exc}",
        )
        return (None, None)



# ---------------------------------------------------------------------------
# Page 5 -- Finish / Move
# ---------------------------------------------------------------------------

class _PageFinish(_FlowPage):
    """Page 5: Finish / Move.

    The ONLY write point.  The Finish handler:
    1. Queries `plan.excluded_lossy_count()`.
    2. When > 0: blocks and pops the summary dialog.
       Confirm -> write; cancel -> stay on wizard.
    3. Executes the move via `gt_api.execute_move`.
    4. Shows the RunReport (MOVE) in the StatsPanel.
    """

    # Issue #11: the dry-run button's label, and its hint once re-entry has
    # discarded a previously computed plan. ASCII only.
    _DRY_RUN_TEXT = "Dry run (preview plan)"
    _DRY_RUN_CLEARED_TEXT = "Dry run (plan cleared - re-run)"

    def __init__(self, report_sink, modify_allowed: bool, parent=None,
                 confirmation_gate=None):
        super().__init__(parent)
        self._report_sink = report_sink
        self._modify_allowed = modify_allowed
        self._move_done = False
        # Feature 034 exceptions 2 and 3. The gate answers two questions for
        # this page: what the subtitle says about reversibility, and whether a
        # Move may proceed. `None` resolves to the FlexTools default, whose
        # subtitle is byte-identical to the literal that used to be inline
        # here and whose confirm() returns True with no UI (SC-013).
        self._gate = _resolve_gate(confirmation_gate)
        # Unnumbered: this run assigns the number on entry, because a
        # position is a fact about the run and not about the page
        # (SelectionWizard._apply_step_number). The literal that used to
        # be here stated a total across a flow that could skip pages.
        self.setTitle("Finish / Move")
        # Exception 3: gate-supplied, because "changes can be undone in FLEx
        # with Ctrl+Z" is true under FlexTools and false in the standalone,
        # and FR-027 forbids the application claiming otherwise.
        self.setSubTitle(self._gate.finish_page_subtitle())
        # data-model section 6: `None` on CONSTRUCTION, not merely on entry. A
        # page built but not yet entered used to have no `_cached_plan` attribute
        # at all, so every guard that asked about it had to reach through a
        # getattr default -- and a guard whose subject may be absent is one
        # refactor away from reading absence as permission.
        self._cached_plan = None
        self._build_ui()
        # DR-1: Move starts disabled unconditionally; enabled only after dry run.
        self._set_execute_enabled(False)

    def initializePage(self) -> None:
        """Re-arm the guard on every Finish page entry.

        DR-2a cleared the cached plan and disabled Move here. Feature 036 T036
        adds the third thing entry has to undo: the report on SCREEN (FR-041).
        Any route back to this page has passed through pages where a selection
        could change, so the plan the previous dry run described may no longer be
        the plan the current selections would produce -- and a StatsPanel still
        full of that run's numbers presents it as current. The cached plan and the
        displayed report are two halves of one authorisation and are dropped
        together.

        Issue #11: when this entry discards a plan that actually existed, the
        dry-run button says so, so the operator can see the earlier result was
        invalidated. First entry (no plan yet) keeps the plain label.
        """
        if self._cached_plan is not None:
            self._dry_run_btn.setText(self._DRY_RUN_CLEARED_TEXT)
        self._cached_plan = None
        self._stats.clear()
        self._set_execute_enabled(False)

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        if not self._modify_allowed:
            warn = QtWidgets.QLabel(
                "[WARN] GramTrans is running in read-only (preview-only) mode. "
                "Move is disabled.",
                self,
            )
            warn.setWordWrap(True)
            layout.addWidget(warn)
        self._dry_run_btn = QtWidgets.QPushButton(self._DRY_RUN_TEXT, self)
        self._dry_run_btn.clicked.connect(self._on_dry_run)
        layout.addWidget(self._dry_run_btn)
        self._move_btn = QtWidgets.QPushButton("Execute Move", self)
        self._move_btn.setEnabled(False)
        self._move_btn.clicked.connect(self._on_move)
        layout.addWidget(self._move_btn)
        # T035 / FR-039: the reason lives next to the control it is about, so it
        # cannot describe a state the button is no longer in.
        self._move_reason = QtWidgets.QLabel("", self)
        self._move_reason.setWordWrap(True)
        layout.addWidget(self._move_reason)
        self._stats = StatsPanel(self)
        layout.addWidget(self._stats, 1)

    # ------------------------------------------------------------------
    # T035 / FR-039 + FR-044 -- a dead control that says why it is dead
    # ------------------------------------------------------------------

    @property
    def execute_disabled_reason(self) -> str:
        """Why Execute is unavailable, or `""` when it is available.

        THE THREE REASONS, IN THE ORDER THAT MATTERS TO THE OPERATOR
        ------------------------------------------------------------
        1. **Read-only** (FR-044) first, because it is the only one they cannot
           act on from here. Telling someone to run a dry run when no dry run
           could ever arm the button is worse than saying nothing: they do the
           work and the button stays dead. This reason therefore outlives a
           successful dry run.
        2. **Already executed** (FR-043). The plan has been written; a second
           write of the same plan would duplicate every object it created.
        3. **No dry run yet** (FR-039), the ordinary case: Preview-before-Mutate
           has not been satisfied for the CURRENT selections.

        Derived, never stored. A stored string is a second source of truth about
        the button's state and drifts from it the first time an enablement path
        forgets to update it -- which is exactly how a dead control comes to
        carry a stale explanation.
        """
        if not self._modify_allowed:
            return (
                "Execute is unavailable: GramTrans is running in read-only "
                "(preview-only) mode, so it cannot write to the target project."
            )
        if self._move_done:
            return (
                "Execute is unavailable: this plan has already been written to "
                "the target project. Close the wizard and start a new run to "
                "transfer anything further."
            )
        if self._cached_plan is None:
            return (
                "Execute is unavailable: a successful dry run of the current "
                "selections is required first. Click the Dry run button."
            )
        return ""

    def _may_execute(self) -> bool:
        """The FR-038/FR-043/FR-044 conjunction, in one place.

        A cached plan, write permission, and no completed Execute this session.
        `_on_dry_run` used to consult only `modify_allowed`, so a second dry run
        after a completed move re-armed the button and the same selections could
        be written twice -- `_move_done` was already recorded and simply not
        read.
        """
        return (
            self._cached_plan is not None
            and self._modify_allowed
            and not self._move_done
        )

    def _set_execute_enabled(self, enabled: bool) -> None:
        """Set the button's state and its explanation together.

        One method, so the two cannot disagree. The reason goes onto the control
        itself (tooltip and accessible description, for a pointer and for a
        screen reader) and onto the label beneath it, because a tooltip alone is
        invisible to an operator who has not thought to hover over a button that
        looks broken.
        """
        self._move_btn.setEnabled(bool(enabled))
        reason = "" if enabled else self.execute_disabled_reason
        self._move_btn.setToolTip(reason)
        self._move_btn.setAccessibleDescription(reason)
        self._move_reason.setText(f"<i>{reason}</i>" if reason else "")
        self._move_reason.setVisible(bool(reason))

    def _refresh_execute_state(self) -> None:
        """Re-derive both halves from the current guard state."""
        self._set_execute_enabled(self._may_execute())

    def _on_dry_run(self) -> None:
        """DR-5, G1, FR-006: compute the plan and show report; enable Move on success."""
        wizard = self.wizard()
        if wizard is None:
            return
        plan, report = _safe_compute_wizard_plan(wizard)
        if plan is None:
            # T036 / FR-041 + FR-042: a dry run that produced nothing must not
            # leave the PREVIOUS run's report on screen. Without this the only
            # report visible after a failure is the stale one, next to a message
            # box saying the run failed -- and once the box is dismissed there is
            # nothing left to say the numbers are old.
            self._cached_plan = None
            self._stats.clear()
            self._refresh_execute_state()
            # DR-5: caller owns QMessageBox.
            _warn_plan_failure(self, wizard)
            return
        # Issue #162: real Preview -- extra lines. Cache only once shown.
        self._cached_plan = None
        try:
            self._stats.set_report(report, preview_extra_lines_or_warning(
                plan, render_preview_extra_lines))
            self._cached_plan = plan
        finally:
            self._refresh_execute_state()
        # Issue #11: a fresh plan exists again, so the "cleared" hint is over.
        self._dry_run_btn.setText(self._DRY_RUN_TEXT)

    def _on_move(self) -> None:
        wizard = self.wizard()
        if wizard is None:
            return
        # DR-6: read cached plan from self (set by dry run), not preview page.
        plan = self._cached_plan
        if plan is None:
            QtWidgets.QMessageBox.warning(
                self, "GramTrans",
                "No plan available. Run a dry run on the Finish page first."
            )
            return
        # FR-043 / FR-044: the same conjunction that decides whether the button
        # is live decides whether the write happens, so the guard does not depend
        # on the button being the only way in. A disabled button stops a click; it
        # does not stop Enter on a focused control, a programmatic `click()`, or a
        # future affordance -- and a second write of an already-written plan
        # duplicates every object it created.
        if not self._may_execute():
            QtWidgets.QMessageBox.warning(
                self, "GramTrans", self.execute_disabled_reason
            )
            self._refresh_execute_state()
            return
        context = wizard.page_project_ws().context()
        if context is None:
            return

        # T017: Aggregate EXCLUDED-LOSSY from the plan + skeleton/deps deselections.
        # plan.excluded_lossy_count() covers warnings emitted during preview planning.
        # Additionally, check skeleton page (index 2) and deps page (index 3) for
        # slots/deps the user deselected that a picked affix needs.
        el_count = plan.excluded_lossy_count()

        # Extra skeleton EXCLUDED-LOSSY (T017)
        skel_page = wizard.page_skeleton()
        if skel_page is not None and hasattr(skel_page, "deselected_filled_slot_guids"):
            deselected_slots = skel_page.deselected_filled_slot_guids()
            if deselected_slots and skel_page._skeleton is not None:
                # Build affix_slot_map from skeleton
                affix_slot_map = {
                    affix_guid: list(slot_guids)
                    for affix_guid, slot_guids in (
                        (ag, frozenset(
                            sg for sg, fills in skel_page._skeleton.affix_fills.items()
                            if ag in fills
                        ))
                        for ag in skel_page._skeleton.affix_picks
                    )
                }
                # target slot guids (blank; skeleton doesn't have live target here)
                extra_warnings = build_excluded_lossy_warnings(
                    affix_slot_map=affix_slot_map,
                    deselected_slot_guids=set(deselected_slots),
                    target_slot_guids=set(),
                )
                el_count += len(extra_warnings)

        # Extra phonology EXCLUDED-LOSSY + KL-010-1 guard (spec 010 T024/T026b).
        # Aggregated into the SAME el_count so a single consolidated dialog
        # covers skeleton/deps AND phonology (FR-011 — no second dialog).
        el_count += len(_phonology_excluded_lossy_for(wizard))

        # Extra entry-types missing-ref warnings (spec 021 T024 / FR-010/FR-011).
        # Kept ILexEntryInflType whose infl-feat ref is absent from target; counted
        # into the SAME consolidated dialog -- never a separate prompt.
        el_count += len(_entry_types_missing_ref_for(wizard))

        # Consolidated single confirmation dialog (FR-011 / T017).
        if el_count > 0:
            answer = QtWidgets.QMessageBox.question(
                self,
                "GramTrans -- Missing references",
                (
                    f"{el_count} entr{'y' if el_count == 1 else 'ies'} will transfer "
                    f"with missing references (deliberately excluded dependencies).\n\n"
                    "These entries will have null fields in the target project.\n\n"
                    "Proceed with Move?"
                ),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return  # User cancelled -- no write occurs.

        # Feature 034 exception 2 (FR-017, FR-024): the host's confirmation
        # gate, consulted ONCE, immediately before the write and after the
        # EXCLUDED-LOSSY dialog -- so a user who backs out of that one is
        # never asked to type a project name they have already decided not to
        # write to. Under FlexTools this returns True with no UI, so the
        # sequence here is unchanged. A False return aborts with no write and
        # leaves the wizard and every selection intact (FR-025).
        #
        # Preview never reaches this line: it is on the Move path only, which
        # is what FR-024 requires.
        target_name = getattr(context, "target_project_name", "") or ""
        if not self._gate.confirm(target_name):
            return  # Gate refused -- no write occurs.

        # FR-023 row 13 -- "Writing to the target project...". The unit is the
        # planned action and the total is `len()` over the plan already in hand,
        # so the write's size is known before a single object is created. This is
        # the operation the operator most needs told about: it is the only one
        # that changes their project, and the only one they must not interrupt.
        #
        # Like row 12 this is one engine call with no sink, so the tick lands on
        # success (see the comment there). A failure below dismisses the
        # indicator through `reporting()` and then says what went wrong, in that
        # order -- a modal indicator left up over a message box would block the
        # only control that can acknowledge it (FR-020).
        n_actions = len(getattr(plan, "actions", ()) or ())
        try:
            with _page_progress(self, "move_write", n_actions) as prog:
                report = gt_api.execute_move(context, plan)
                prog.tick(n_actions)
        except gt_api.PreviewStale as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        self._stats.set_report(report)
        self._move_done = True
        # DR-2b, G3: invalidate Finish page's own cached plan (post-move).
        # Move non-repeatability: a double-click or re-entry cannot re-execute
        # the same plan and create duplicate LCM objects. initializePage also
        # clears on re-entry (DR-2a), so this provides belt-and-suspenders safety.
        self._cached_plan = None
        # Both halves after the state above, so the reason the operator now reads
        # is FR-043's ("already written"), not FR-039's.
        self._refresh_execute_state()
        self.completeChanged.emit()


# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------

class SelectionWizard(QtWidgets.QWizard):
    """The GramTrans selection wizard (Phase 3c, Refinement 3).

    Page order, skip eligibility and per-run numbering all come from `flow()`;
    no count of pages is stated here or anywhere else (036 FR-009a).

    All existing widgets are re-hosted
    verbatim; no widget logic is rewritten.

    Constructor args:
        host_project: the FlexTools host's open FLExProject (the SOURCE).
        report_sink:  FlexTools report object (.Info / .Warning / .Error / .Blank).
        modify_allowed: True when FlexTools is running write-enabled.
        source_project_name: display name of the source project.
        projects_root: feature 034 exception 4 (FR-001) -- where the host says
            FLEx projects live. Keyword-only and defaulted, so the FlexTools
            call is unchanged and `list_target_candidates` keeps its historical
            C:\\ProgramData\\SIL\\FieldWorks\\Projects default. The standalone
            passes the location FieldWorks itself records.
        confirmation_gate: feature 034 exceptions 2 and 3 (FR-017) -- the
            host's answer to "may I write?", consulted once by `_PageFinish`
            immediately before `gt_api.execute_move` and never on the Preview
            path. Also supplies the Finish page's subtitle, because whether a
            Move can be undone is a fact about the host, not about the wizard.
            `None` resolves to `Lib/gate.AlwaysSatisfiedGate`: True with no UI,
            and today's subtitle byte for byte (SC-013).
        source_binder: feature 034 exception 7 -- for a host that has no open
            project of its own. A callable taking a project name and returning
            an open **read-only** handle, supplied by the host because the host
            is what must close it again. When given, `host_project` may be
            `None` and `source_project_name` empty, and step 1 grows a "Pick
            source project..." button beside the target's. `None` (every
            FlexTools call) means the source is host-supplied: no button, no
            picker, no change to the page (SC-013).
    """

    def __init__(
        self,
        host_project,
        report_sink,
        modify_allowed: bool,
        *,
        source_project_name: str,
        parent: Optional[QtWidgets.QWidget] = None,
        projects_root: str = "",
        confirmation_gate=None,
        source_binder=None,
    ) -> None:
        super().__init__(parent)
        # Install the palette/text-size theme BEFORE any page is constructed.
        # The pages snapshot the *application* font into per-item QFonts while
        # they build their trees (bolded section headers etc.), so a scale
        # applied afterwards would leave those items at the size that was in
        # force when the tree was built -- the first paint would come up
        # unscaled even though the user had saved a larger text size.
        install_theme()
        self._host = host_project
        self._report = report_sink
        self._modify_allowed = modify_allowed
        # T014: filled once, here, from whatever source the host already has
        # open (None under the standalone, whose source is picked on step 1 and
        # which calls `refresh_source_counts` from there). Every page-skip
        # predicate reads this snapshot, so nothing on a navigation path ever
        # queries the project (D5b).
        self.refresh_source_counts(host_project)

        # T040 / FR-001. The title used to read "GramTrans -- Selection Wizard
        # (Phase 3c)". "Phase 3c" is OUR development milestone: it tells the
        # operator nothing about the tool and, worse, reads as a beta warning on
        # software they are about to point at their language data. What a title
        # bar owes them is what the application is and what this window does.
        # No phase, no milestone, no iteration designation -- a source-level test
        # keeps one from creeping back.
        self.setWindowTitle("GramTrans -- copy grammar between FieldWorks projects")
        self.setModal(True)
        self.resize(1300, 760)
        # 036 T024/FR-029: the floor is the declared constant, and the height is
        # the one feature 004 set. The default size above is unchanged: US3
        # lowers how narrow the window CAN go, not how wide it opens.
        self.setMinimumSize(
            QtCore.QSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        )
        # ClassicStyle renders pages using the widget palette instead of forcing
        # a white page (AeroStyle/ModernStyle default on Windows). Under an OS
        # dark theme the forced-white page left every QLabel white-on-white
        # (illegible); ClassicStyle keeps text/background consistent with the
        # palette in both light and dark themes.  The reasoning is stronger now
        # that the palette is ours (Lib/ui/theme.py) rather than the OS's: a
        # style that forces its own white page would ignore the dark scheme the
        # user selected in-app, not merely the one Windows reported.
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ClassicStyle)

        stub = gt_api.initialize_run(
            host_handle=host_project,
            source_project_name=source_project_name,
            source_project_path=_safe_path(host_project),
            projects_root=projects_root,
        )

        # Create pages. The ORDER they are registered in, and which of them a
        # given run shows, is `flow()` and nothing else (FR-010) -- the numbered
        # comment block that used to sit here restated the `addPage` order beside
        # it, which is exactly the second source of truth that let the titles
        # drift to "of 10" across eleven registered pages.
        #
        # _PagePreview and _PageScopeConflict are constructed and retained for
        # back-compat (`page_preview()`, `page_scope`) but are absent from
        # `flow()` and therefore never registered and never numbered (FR-011).
        self._page_projects = _PageProjects(
            stub, host_project,
            source_binder=source_binder, report_sink=report_sink,
        )
        self._page_writing_systems = _PageWritingSystems()
        self._page_custom_fields = _PageCustomFields()
        self._page_phonology = _PagePhonology()
        self._page_items = _PageItemPicker()
        self._page_stems = _PageStemPicker()
        self._page_skeleton = _PageSkeleton()
        self._page_gram_deps = _PageGramDeps()
        self._page_entry_types = _PageEntryTypes()   # spec 021
        # _PageScopeConflict kept but NOT added to the wizard (conflict UI deferred FR-012).
        self._page_scope = _PageScopeConflict()
        # 018-rules-page: Rules page sits after Lexical-entry types (021, not yet added)
        # and before Preview (FR-007).  Positioned after _PageGramDeps per spec order.
        self._page_rules = _PageRules()
        self._page_texts = _PageTexts()        # Feature 026 texts-wordforms
        self._page_preview = _PagePreview()
        self._page_finish = _PageFinish(
            report_sink, modify_allowed, confirmation_gate=confirmation_gate
        )

        # T009 / FR-010: registration is READ OFF the declaration. The eleven
        # hand-written `addPage` lines that used to be here carried their own
        # index comments, so the declaration and the registration were two
        # statements of the same fact and could disagree -- and did.
        #
        # `_page_id_by_attr` is filled here so `nextId()` can turn a declared
        # attr into a Qt page id by dict lookup. Qt may call `nextId()` on every
        # `completeChanged`, and searching `pageIds()` on each call would make
        # the cheap predicates pointless (FR-009c, D5b).
        self._page_id_by_attr: dict = {}
        for attr, _short, _skippable, _has_content in self.flow():
            page = getattr(self, attr)
            self._page_id_by_attr[attr] = self.addPage(page)

        # Provisional numbers, so a page carries a plausible title before any
        # run has entered it (the wizard is inspectable at construction). Entry
        # overwrites them with the position this run actually reached
        # (`_apply_step_number`); nothing derives or displays a total (FR-009a).
        self._apply_declared_step_numbers()

        self.setOption(QtWidgets.QWizard.WizardOption.HaveHelpButton, False)

        # T041 / FR-004 + FR-012. Qt stops drawing the subtitle, and each page's
        # own header draws it instead. `setSubTitle(...)` remains the string of
        # record everywhere -- this is a change of RENDERER, not a second copy of
        # the text to keep in step. Qt's renderer elides; the header's wraps, and
        # a description that ends mid-word with no ellipsis is FR-013's defect.
        self.setOption(QtWidgets.QWizard.WizardOption.IgnoreSubTitles, True)
        for attr, _short, _skippable, _has_content in self.flow():
            page = getattr(self, attr, None)
            if page is not None and hasattr(page, "install_header"):
                page.install_header(PageHeader(page))

        # T042 / FR-005 + D8. ONE strip for the whole wizard, moved into the
        # current page's header slot on every transition.
        #
        # WHY ONE, AND NOT ONE PER PAGE
        # -----------------------------
        # The obvious implementation -- give each header its own strip -- would
        # register `ZoomIn`, `ZoomOut` and `Ctrl+0` twelve times inside one
        # window. Qt resolves an ambiguous shortcut by firing NOTHING, so all
        # three keys would go quietly dead while every button still worked: a
        # failure nobody would attribute to the header refactor. One instance
        # means one registration, which is what FR-005 asks for.
        #
        # It is created after the pages exist because it is moved INTO one of
        # their headers immediately, and the headers are installed just above.
        self._theme_bar = ThemeCornerBar(self)
        self.currentIdChanged.connect(self._install_theme_bar_on_current_page)
        self._install_theme_bar_on_current_page()

    # =====================================================================
    # The declared flow (T009, FR-010; data-model section 1)
    # =====================================================================

    def flow(self):
        """The ordered flow: `(attr, short_title, skippable, has_content)` x 12.

        THE SINGLE SOURCE OF PAGE ORDER AND SKIP ELIGIBILITY (FR-010).
        Registration reads it (`__init__`), numbering reads it
        (`_apply_step_number`), and skipping reads it (`_FlowPage.nextId`), so
        the three cannot disagree about what a run contains.

        WHAT IS DELIBERATELY ABSENT
        ---------------------------
        **Positions, and any length.** A position is (pages shown before this
        one in *this run*) + 1, so an integer in this table could only be a slot
        number -- and a slot number displayed as a position is how eleven
        registered pages came to announce "of 10". Nothing here derives a total
        and nothing displays one (FR-009a). The operator may also go back and
        pick an affix, which re-admits Morphology Skeleton and shifts every
        position after it: the length of a run is not knowable until the run is
        over.

        `skippable` / `has_content`
        ---------------------------
        `has_content` is `None` if and only if `skippable` is False, so an
        unskippable page carries no predicate for a caller to consult and skip
        on anyway. Where it is present it is a zero-argument callable that Qt
        may invoke on every `completeChanged`; each one is a field read or a
        `len()`, never an inventory build (FR-009c, D5b).

        The Affix and Stem pickers are unskippable **by mandate** (FR-009d), not
        because they always have content: "your source has no affixes" is
        something the operator needs told, and an absent page does not say it.
        Projects, Writing Systems and Finish are unskippable because they always
        ask something.
        """
        return (
            ("_page_projects",        "Projects",                 False, None),
            ("_page_writing_systems", "Writing Systems",          False, None),
            ("_page_custom_fields",   "Custom Fields",            True,
             self._has_custom_fields),
            ("_page_phonology",       "Phonology",                True,
             self._has_phonology),
            ("_page_items",           "Affix Picker",             False, None),
            ("_page_stems",           "Stem Picker",              False, None),
            ("_page_skeleton",        "Morphology Skeleton",      True,
             self._has_item_picks),
            ("_page_gram_deps",       "Grammatical Dependencies", True,
             self._has_gram_deps),
            ("_page_entry_types",     "Lexical-Entry Types",      True,
             self._has_entry_types),
            ("_page_rules",           "Rules",                    True,
             self._has_rules),
            ("_page_texts",           "Texts",                    True,
             self._has_texts),
            ("_page_finish",          "Finish / Move",            False, None),
        )

    def flow_page_id(self, attr: str) -> int:
        """Qt's id for a declared page, or -1 before it has been registered."""
        return getattr(self, "_page_id_by_attr", {}).get(attr, -1)

    # =====================================================================
    # The emptiness predicates (T014, FR-009c / FR-009d / D5b)
    # =====================================================================
    # THE CONSERVATIVE RULE IS ABSOLUTE. Every predicate below returns True
    # when it does not know. An empty page that is shown costs the operator one
    # Next click and says on the page that it has nothing to decide; a non-empty
    # page that is skipped silently drops a decision they were entitled to make.
    # The two errors are not symmetric, so unknown means SHOWN.
    #
    # Cost matters here in a way it does not elsewhere: Qt calls `nextId()` to
    # decide whether Next is enabled, which can be on every `completeChanged`.
    # Nothing below queries a project. The five source-derived pages read a
    # `SourceCounts` snapshot filled once at bind (`Lib/progress.py`), and the
    # two selection-derived pages read the picker trees the operator just
    # touched. No inventory is built -- building one to find out whether a page
    # would be empty is precisely the expensive walk US1 exists to cover, and
    # FR-009c forbids paying for it here.

    def source_counts(self) -> "SourceCounts":
        """The cheap-count snapshot of the currently bound source."""
        return self._source_counts

    def refresh_source_counts(self, source) -> None:
        """Re-snapshot the counts because the source binding changed.

        Called from `_PageProjects._bind_source_handle` (the standalone's
        re-pick) and once from `__init__` (FlexTools, whose source is the host's
        already-open project). Filling it anywhere else would mean a count was
        read on a page-navigation path, which is the cost D5b rules out.
        """
        self._source_counts = (
            SourceCounts(source) if source is not None else SourceCounts.unknown()
        )

    def _has_custom_fields(self) -> bool:
        """Row 3: source custom-field definitions across the owner classes."""
        return _count_says_content(self._source_counts.custom_fields)

    def _has_phonology(self) -> bool:
        """Row 4: phoneme sets + natural classes + phonological rules."""
        return _count_says_content(self._source_counts.phonology)

    def _has_entry_types(self) -> bool:
        """Row 9: variant types + complex-form types."""
        return _count_says_content(self._source_counts.entry_types)

    def _has_rules(self) -> bool:
        """Row 10: ad-hoc prohibitions."""
        return _count_says_content(self._source_counts.rules)

    def _has_texts(self) -> bool:
        """Row 11: `TextsNumberOfTexts()`."""
        return _count_says_content(self._source_counts.texts)

    def _has_item_picks(self) -> bool:
        """Row 7: "the operator picked at least one affix or stem".

        The declared proxy for Morphology Skeleton. Deliberately NOT "the
        skeleton inventory would come back empty": answering that means
        building the inventory, which is the multi-second walk the page already
        shows a progress indicator for.

        Before either picker has been populated the answer is unknown, not
        "no" -- an unbound run has picked nothing simply because it has not been
        asked yet -- so both pages are shown. A page whose proxy says "maybe"
        and whose inventory then comes back empty says so and keeps its number
        (spec edge case).
        """
        items = getattr(self, "_page_items", None)
        stems = getattr(self, "_page_stems", None)
        populated = (getattr(items, "_inventory", None) is not None
                     or getattr(stems, "_stem_inventory", None) is not None)
        if not populated:
            return True                     # unknown -> show
        try:
            if items is not None and len(items.picker_state().checked_affixes):
                return True
            if stems is not None and len(stems.stem_picks()):
                return True
        except Exception:  # noqa: BLE001 -- a broken tree read is "unknown"
            return True
        return False

    def _has_gram_deps(self) -> bool:
        """Return whether the selected items have grammatical dependencies.

        Dependency enumeration is cached per source and picker selection so
        Qt can ask this predicate repeatedly without rebuilding the inventory.
        An unavailable or failed enumeration is treated as unknown and keeps
        the page visible.
        """
        items = getattr(self, "_page_items", None)
        stems = getattr(self, "_page_stems", None)
        try:
            affix_picks = items.collect_selection().affix_picks if items else frozenset()
            stem_picks = stems.stem_picks() if stems else frozenset()
            populated = (getattr(items, "_inventory", None) is not None
                         or getattr(stems, "_stem_inventory", None) is not None)
            if not populated:
                return True
            source = self._page_projects.context().source_handle
            if source is None:
                return True
        except Exception:  # noqa: BLE001 -- a broken read is "unknown"
            return True

        cache_key = (id(source), frozenset(affix_picks), frozenset(stem_picks))
        cached = getattr(self, "_gram_deps_content_cache", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        if not affix_picks and not stem_picks:
            result = False
        else:
            try:
                deps = build_deps_inventory(
                    source, frozenset(affix_picks), stem_picks=frozenset(stem_picks)
                )
                result = bool(deps.infl_features or deps.infl_classes or deps.stem_names)
            except Exception:  # noqa: BLE001 -- unknown means show
                return True
        self._gram_deps_content_cache = (cache_key, result)
        return result

    # -- Step numbering (T012, FR-009 / FR-009a) -----------------------------

    def _short_title_for_page(self, page) -> str:
        """The declared, unnumbered title of `page`, or "" when undeclared.

        Undeclared is a real answer, not a failure: `_PageScopeConflict` and
        `_PagePreview` are retained and never in the flow, so they have no
        number to state and must never be given one (FR-011).
        """
        for attr, short, _skippable, _has_content in self.flow():
            if getattr(self, attr, None) is page:
                return short
        return ""

    def _apply_declared_step_numbers(self) -> None:
        """Number every declared page by its slot, as a pre-run placeholder.

        Only correct for a run that shows everything -- which is why entry
        recomputes it. It exists because the wizard is inspectable before it is
        walked, and a page whose title read "Projects" with no number in a
        numbered flow would look like the un-numbered page SC-004 removed.
        """
        for i, (attr, short, _skippable, _has) in enumerate(self.flow(), 1):
            page = getattr(self, attr, None)
            if page is not None:
                page.setTitle(f"Step {i}: {short}")

    def _apply_step_number(self, page_id: int) -> None:
        """Title `page_id` as "Step {n}: {short}" for this run's n.

        n counts the pages this run has actually SHOWN, so a run that skipped
        Phonology reads 1, 2, 3 with no hole where it would have been (SC-003a).
        Qt's own visited stack is the counter: it does not yet contain `page_id`
        when `initializePage` fires (verified against Qt 6.7), and Back pops it,
        so retracing a run reproduces the numbers the operator saw.
        """
        page = self.page(page_id)
        if page is None:
            return
        short = self._short_title_for_page(page)
        if not short:
            return          # not in the flow -> not numbered (FR-011)
        visited = list(self.visitedIds())
        position = (visited.index(page_id) + 1) if page_id in visited \
            else len(visited) + 1
        page.setTitle(f"Step {position}: {short}")

    def initializePage(self, page_id: int) -> None:  # noqa: N802 -- Qt naming
        """Number the page being entered, then let it initialise itself.

        The number is assigned HERE rather than in each page's own
        `initializePage` because it is a fact about the run, not about the page,
        and because five of the twelve pages have no `initializePage` at all.

        The header's description is re-rendered for the same reason (T041):
        `subTitle()` is the string of record and a page may restate it as it
        initialises, so the render happens on entry rather than once at install.
        """
        self._apply_step_number(page_id)
        page = self.page(page_id)
        if page is not None and hasattr(page, "refresh_header_description"):
            page.refresh_header_description()
        super().initializePage(page_id)

    def context(self):
        """Return the bound RunContext (available after page 1 is completed)."""
        return self._page_projects.context()

    # -- Named page accessors (spec 010 P-1) ---------------------------------
    # Pages MUST reference each other through these, never by literal index:
    # inserting a page (e.g. Phonology at index 1) shifts every literal
    # `wizard.page(N)` silently. Each accessor returns the stored attribute.
    def page_project_ws(self):
        """The projects page. 036 FR-006 renamed the attribute, not the name.

        25 call sites reach the source handle and the bound context through
        this accessor; the page it returns no longer owns the writing-system
        mapping (see `page_writing_systems`).
        """
        return self._page_projects

    def page_writing_systems(self):
        """The writing-systems page -- `ws_mapping()` and `selected_ws_ids()`.

        New in 036 (FR-006). One owner: reading a mapping off
        `page_project_ws()` is no longer possible, so no caller can silently get
        a stale or empty one from the half that lost it.
        """
        return self._page_writing_systems

    def page_custom_fields(self):
        return self._page_custom_fields

    def page_phonology(self):
        return self._page_phonology

    def page_items(self):
        return self._page_items

    def page_stems(self):
        return self._page_stems

    def page_skeleton(self):
        return self._page_skeleton

    def page_gram_deps(self):
        return self._page_gram_deps

    def page_entry_types(self):
        return self._page_entry_types

    def page_rules(self):
        """Named accessor for _PageRules (018-rules-page P-1 pattern)."""
        return self._page_rules

    def page_texts(self):
        """Named accessor for _PageTexts (Feature 026, P-1 pattern)."""
        return self._page_texts

    def page_preview(self):
        return self._page_preview

    def page_finish(self):
        return self._page_finish

    def theme_bar(self):
        """Named accessor for the one theme / text-size control strip.

        Kept under its historical name: callers reach it to ask about zoom and
        colour mode, which is still what it is for. What changed is where it
        lives -- a header slot on the current page, not a floating overlay.
        """
        return self._theme_bar

    # -- The one control strip, moved between page headers (T042, FR-005) ----
    # No geometry hooks any more. `resizeEvent` and `showEvent` used to exist
    # solely to re-pin a bar that nothing laid out; the header's layout does
    # that now, at every width and every text scale, without being told.

    def _install_theme_bar_on_current_page(self, *_args) -> None:
        """Move the strip into the current page's header controls slot.

        Every guard here is a real state this runs in. `currentIdChanged` fires
        during construction (before `_theme_bar` exists) and again after the
        last page, with id -1; a page outside the flow has no header; and Qt
        rebuilds its page stack on every transition, so the move has to happen
        on each one rather than once at the start.

        `set_controls` detaches the strip from the previous page's slot first,
        so exactly one header holds it at any moment and the others collapse
        their controls cell to nothing.
        """
        bar = getattr(self, "_theme_bar", None)
        if bar is None:
            return
        page = self.currentPage()
        header = page.header() if hasattr(page, "header") else None
        if header is None:
            return
        header.set_controls(bar)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe_path(flex_project) -> str:
    for attr in ("ProjectPath", "ProjectFilename", "ProjectFolder"):
        try:
            v = getattr(flex_project, attr)
            return v() if callable(v) else str(v)
        except Exception:
            continue
    return ""
