"""Plan assembly for the wizard (issue #193: split out of selection_wizard.py).

`_compute_wizard_plan`, the plan-failure-reason plumbing it shares with the
Preview/Finish pages, and the EXCLUDED-LOSSY helpers it calls. Re-exported from
`selection_wizard`, which stays the import surface (`test_039_module_split.py`
guard 2).
"""
from __future__ import annotations

import dataclasses
import logging

from PyQt6 import QtWidgets

_module_log = logging.getLogger(__name__)

if __package__:
    from .. import api as gt_api
    from ..models import (
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        _DEFAULT_CONFLICT_MODES,
    )
    from ..report import RunReport
    from ..selection import (
        PickerState,
        SourceAffixInventory,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_selection,
        collapse_entry_types,
        collapse_phonology,
        entry_types_missing_ref_warnings,
        phonology_uses_untraversed_rules,
    )
    from .wizard_widgets import _page_progress
else:
    import api as gt_api  # type: ignore
    from models import (  # type: ignore
        ExcludedLossy,
        GrammarCategory,
        RunMode,
        _DEFAULT_CONFLICT_MODES,
    )
    from report import RunReport  # type: ignore
    from selection import (  # type: ignore
        PickerState,
        SourceAffixInventory,
        build_phonology_excluded_lossy,
        build_phonology_inventory,
        build_selection,
        collapse_entry_types,
        collapse_phonology,
        entry_types_missing_ref_warnings,
        phonology_uses_untraversed_rules,
    )
    from wizard_widgets import _page_progress  # type: ignore


def _phonology_nc_or_phoneme_trimmed(inventory, checked_by_category) -> bool:
    """True iff the user deselected any NC or phoneme (KL-010-1 guard input)."""
    for cat in (GrammarCategory.NATURAL_CLASSES, GrammarCategory.PHONEMES):
        grp = inventory.group_for(cat)
        if grp is None:
            continue
        all_guids = {r.guid for r in grp.rows}
        if all_guids - set(checked_by_category.get(cat, set())):
            return True
    return False


def _kl010_notice(inventory, checked_rule_guids) -> ExcludedLossy:
    """Coarse Principle-V notice for a kept metathesis/reduplication rule.

    The reference traversal does not follow metathesis/reduplication part
    sequences (KL-010-1), so a trim MIGHT strand a reference we cannot see.
    Surface one honest notice into the shared Move gate rather than transfer
    silently. Attributed to the first such kept rule.
    """
    rule_guids = sorted(inventory.untraversed_rule_guids & set(checked_rule_guids))
    rg = rule_guids[0] if rule_guids else "?"
    label = rg[:8]
    grp = inventory.group_for(GrammarCategory.PHONOLOGICAL_RULES)
    if grp is not None:
        for r in grp.rows:
            if r.guid == rg:
                label = r.label
                break
    return ExcludedLossy(
        category=GrammarCategory.PHONOLOGICAL_RULES,
        entry_guid=rg or "?",
        entry_label=label,
        dep_category=GrammarCategory.PHONOLOGICAL_RULES,
        dep_guid=rg or "?",
        dep_label=label,
        message=(
            f"Reference check is not supported for rule '{label}' "
            "(metathesis/reduplication); trimming phonemes or natural classes "
            "may strand references not verified here (KL-010-1)."
        ),
    )


def _phonology_excluded_lossy_for(wizard) -> list:
    """Intra-phonology EXCLUDED-LOSSY warnings for the current page state.

    Shared by Preview (StatsPanel channel, T025) and Finish (Move gate, T024)
    so both agree on the entry-centric count. Returns a list of ExcludedLossy;
    empty when there is no phonology page / inventory. Appends the coarse
    KL-010-1 notice (T026b) when a kept metathesis/reduplication rule coincides
    with an NC/phoneme trim.
    """
    phon_page = (wizard.page_phonology()
                 if hasattr(wizard, "page_phonology") else None)
    if phon_page is None or phon_page.inventory() is None:
        return []
    inventory = phon_page.inventory()
    checked = phon_page.collect_phonology_picks()

    # Target GUIDs per category drive the absent-from-target test. Reuse the
    # builder against the target handle (read-only) rather than re-deriving.
    target = None
    try:
        p0 = wizard.page_project_ws()
        ctx = p0.context() if p0 is not None else None
        target = getattr(ctx, "target_handle", None) if ctx is not None else None
    except Exception:  # noqa: BLE001
        target = None
    tgt_by_cat: dict = {}
    if target is not None:
        try:
            tinv = build_phonology_inventory(target)
            tgt_by_cat = {g.category: {r.guid for r in g.rows}
                          for g in tinv.groups}
        except Exception:  # noqa: BLE001
            tgt_by_cat = {}

    warnings = list(build_phonology_excluded_lossy(inventory, checked, tgt_by_cat))

    checked_rules = checked.get(GrammarCategory.PHONOLOGICAL_RULES, set())
    if (phonology_uses_untraversed_rules(inventory, checked_rules)
            and _phonology_nc_or_phoneme_trimmed(inventory, checked)):
        warnings.append(_kl010_notice(inventory, checked_rules))
    return warnings


def _entry_types_missing_ref_for(wizard) -> list:
    """Entry-types inflection-feature missing-ref warnings for the current page state.

    Shared by Finish (Move gate) so the count is aggregated into the single
    consolidated dialog (FR-011). Returns a list of warning dicts; empty when
    there is no entry-types page / inventory.
    """
    et_page = (wizard.page_entry_types()
               if hasattr(wizard, "page_entry_types") else None)
    if et_page is None or et_page.inventory() is None:
        return []
    inventory = et_page.inventory()
    checked = et_page.collect_entry_type_picks()
    target = et_page._get_target()
    return entry_types_missing_ref_warnings(inventory, checked, target=target)


_PLAN_FAILURE_ATTR = "_gt_plan_failure_reason"


def _set_plan_failure_reason(wizard, reason: str) -> None:
    """Record WHY plan assembly returned `(None, None)`, for the caller's dialog.

    `_compute_wizard_plan` must not open dialogs (DR-5) and must not raise
    across the Qt slot that called it, which leaves it only a return value to
    speak with. Without this the operator gets "Plan assembly failed. Check
    project state." for a failure that is neither about project state nor
    something checking it would reveal.
    """
    try:
        setattr(wizard, _PLAN_FAILURE_ATTR, reason)
    except Exception:  # noqa: BLE001 - a fake wizard that rejects attributes
        pass


def _take_plan_failure_reason(wizard) -> str:
    """Read and clear the recorded reason, so it cannot outlive its run."""
    reason = getattr(wizard, _PLAN_FAILURE_ATTR, "") or ""
    try:
        setattr(wizard, _PLAN_FAILURE_ATTR, "")
    except Exception:  # noqa: BLE001
        pass
    return reason


def _warn_plan_failure(parent, wizard) -> None:
    """Pop the dialog for a dry run / preview that produced no plan (DR-5).

    Shared by `_PagePreview._on_preview` and `_PageFinish._on_dry_run` so the
    two cannot drift apart (issue #8). Two failures, two messages, because "no
    target bound" and "plan assembly failed" send the operator to different
    places (FR-042). Dialog only: any state the caller drops on failure stays
    in the caller.
    """
    context = wizard.page_project_ws().context()
    if context is None:
        QtWidgets.QMessageBox.warning(
            parent, "GramTrans", "No target project bound. Go back to page 1."
        )
    else:
        # G1: assembly failure -- Move stays disabled, no partial state.
        QtWidgets.QMessageBox.warning(
            parent, "GramTrans",
            _take_plan_failure_reason(wizard)
            or "Plan assembly failed. Check project state.",
        )


def _compute_wizard_plan(wizard) -> tuple:
    """Assemble the transfer plan from all wizard page selections.

    Returns (plan, report) on success, (None, None) on any failure.
    Does not display QMessageBox -- callers own all UI dialogs (DR-5).

    DR-4 step order:
    1. Context None-guard.
    2. affix_selection = page_items.collect_selection().
    3. build_selection + _replace_conflict_modes.
    4. dataclasses.replace stamp with similar_resolutions (single call -- SC-005).
    5. similar_resolutions stamp BEFORE phonology merge block (P1 ordering);
       the page-pick merges that follow are sub-steps 5a-5h.
    6. ws_mapping from page0.
    7. gt_api.compute_preview; return (None, None) on payload-None or failure.
    8. RunReport.build_from_plan; return (payload, report).
    """
    # A reason from a previous run must not be reported against this one.
    _set_plan_failure_reason(wizard, "")

    # Step 1: context None-guard (no QMessageBox here -- caller owns dialogs).
    context = wizard.page_project_ws().context()
    if context is None:
        return (None, None)

    # Step 2: affix selection (single collect_selection call -- SC-005).
    page_items = wizard.page_items()
    affix_selection = page_items.collect_selection()

    # Step 3: build selection + apply Layer-1 conflict-mode defaults.
    selection = build_selection(
        PickerState(
            checked_affixes=affix_selection.affix_picks,
            checked_templates=affix_selection.template_picks,
        ),
        SourceAffixInventory(
            unbound_affixes=affix_selection.affix_picks,
            template_to_slots={t: () for t in affix_selection.template_picks},
        ),
        category_scopes={},
    )._replace_conflict_modes(dict(_DEFAULT_CONFLICT_MODES))

    # Steps 4-5: stamp similar_resolutions BEFORE the phonology merge (P1 ordering).
    # Uses the already-collected affix_selection -- no second collect_selection call.
    selection = dataclasses.replace(
        selection,
        similar_resolutions=affix_selection.similar_resolutions,
    )

    # Step 5a: custom-fields merge (US2/T014 -- fold leaf_item_picks into selection).
    cf_page = wizard.page_custom_fields() if hasattr(wizard, "page_custom_fields") else None
    if cf_page is not None:
        cf_picks = cf_page.leaf_item_picks()
        if cf_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.CUSTOM_FIELDS] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(cf_picks)
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )
        elif cf_page.whole_block_on():
            # Fully selected => include CUSTOM_FIELDS category (transfer-all).
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.CUSTOM_FIELDS] = True
            selection = dataclasses.replace(selection, categories=merged_categories)

    # Step 5b: phonology collapse-merge (applied AFTER resolution stamp per DR-4/P1).
    phon_page = wizard.page_phonology()
    if phon_page is not None and phon_page.inventory() is not None:
        collapsed = collapse_phonology(
            phon_page.inventory(), phon_page.collect_phonology_picks()
        )
        if collapsed["categories"]:
            merged_categories = dict(selection.categories)
            merged_categories.update(collapsed["categories"])
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(collapsed["leaf_item_picks"])
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5c: entry-types collapse-merge (spec 021, applied after phonology).
    et_page = (wizard.page_entry_types()
               if hasattr(wizard, "page_entry_types") else None)
    if et_page is not None and et_page.inventory() is not None:
        collapsed = collapse_entry_types(
            et_page.inventory(), et_page.collect_entry_type_picks()
        )
        if collapsed["categories"]:
            merged_categories = dict(selection.categories)
            merged_categories.update(collapsed["categories"])
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf.update(collapsed["leaf_item_picks"])
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5d: rules block collapse-merge (018-rules-page T019).
    # collect_rules_picks() returns:
    #   None         => key absent (transfer ALL, SC-004 untouched default)
    #   frozenset()  => whole block OFF, zero rules transferred (SC-005)
    #   frozenset({..}) => individual trim subset
    rules_page = wizard.page_rules() if hasattr(wizard, "page_rules") else None
    if rules_page is not None and rules_page.inventory() is not None:
        rules_picks = rules_page.collect_rules_picks()
        if rules_picks is None:
            # Untouched / fully-checked => include category, key absent (transfer all)
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.ADHOC_COMPOUND_RULES] = True
            selection = dataclasses.replace(selection, categories=merged_categories)
        else:
            # Trimmed or whole-block-OFF: include category + emit frozenset (may be empty)
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.ADHOC_COMPOUND_RULES] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf[GrammarCategory.ADHOC_COMPOUND_RULES] = rules_picks
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5e: POS/grammar-category wiring (fix/wizard-pos-grammar-wiring).
    # The Skeleton page pre-checks exactly the POSes the picked affixes' MSAs
    # attach to (SkeletonPosNode.preselected). Fold those POS GUIDs into the
    # Selection as pos_picks + flag GRAM POS, so the verb-vertical POS closure
    # (_select_source_poses -> _plan_pos_closure) walks precisely those POSes,
    # creates them in the target, and affix/stem MSAs resolve to a real POS via
    # _resolve_target_pos instead of None ("no grammatical info").  This is
    # dependency-driven and minimal: it never flags the leaf GRAM_CATEGORIES
    # pass (which would enumerate EVERY source POS), and an empty pos_guids set
    # (skeleton not built / no attaching POS) leaves the selection untouched --
    # we never flag POS with empty picks, which would walk every source POS.
    skel_page = wizard.page_skeleton() if hasattr(wizard, "page_skeleton") else None
    if skel_page is not None and hasattr(skel_page, "collect_skeleton_picks"):
        pos_guids = skel_page.collect_skeleton_picks().get("pos_guids") or set()
        if pos_guids:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.POS] = True
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                pos_picks=frozenset(g.lower() for g in pos_guids),
            )

    # Step 5f: stems -- fold the dedicated Stems page picks into the selection.
    # The leaf dispatch enumerates STEMS via selection.leaf_picks_for(STEMS)
    # (i.e. leaf_item_picks[GrammarCategory.STEMS]); mirror that contract here.
    # GUIDs are lower-cased to match categories._guid_str_from() on the source
    # side.  Empty picks leave STEMS off (nothing to transfer).
    stem_page = wizard.page_stems() if hasattr(wizard, "page_stems") else None
    if stem_page is not None and hasattr(stem_page, "stem_picks"):
        stem_picks = stem_page.stem_picks()
        if stem_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.STEMS] = True
            merged_leaf = dict(selection.leaf_item_picks)
            merged_leaf[GrammarCategory.STEMS] = frozenset(
                g.lower() for g in stem_picks
            )
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                leaf_item_picks=merged_leaf,
            )

    # Step 5g: texts -- fold the dedicated Texts page picks into the selection
    # (Feature 026, FR-001). The preview/transfer TEXTS hook enumerates the
    # source's texts filtered by selection.text_picks; mirror that contract
    # here. GUIDs are lower-cased to match the source-side _text_guid()
    # normalization. Empty picks leave TEXTS off (nothing to transfer).
    texts_page = wizard.page_texts() if hasattr(wizard, "page_texts") else None
    if texts_page is not None and hasattr(texts_page, "text_picks"):
        text_picks = texts_page.text_picks()
        if text_picks:
            merged_categories = dict(selection.categories)
            merged_categories[GrammarCategory.TEXTS] = True
            selection = dataclasses.replace(
                selection,
                categories=merged_categories,
                text_picks=frozenset(g.lower() for g in text_picks),
            )

    # Step 5h: grammatical-dependency deselection (feature 038 T072, FR-016).
    # `_PageGramDeps` preselects every dependency it derived from the affix
    # picks and invites the user to uncheck what they do not want;
    # `deselected_dep_guids()` returns exactly the GUIDs they unchecked. Until
    # this step existed NOTHING called it, so `Selection.excluded_deps` was
    # empty on every plan the wizard has ever built and the checkbox changed
    # nothing. `preview._plan_pulled_in_items` (T070/T071) is the reader:
    # a GUID in this set suppresses the pull-in and emits
    # `SkipReason.DEPENDENCY_DESELECTED` instead of transferring the object.
    # GUIDs are lower-cased for the same reason the skeleton/stems/texts steps
    # do it -- the engine compares against `categories._guid_str_from` output.
    #
    # TWO pages contribute, not one. `_PageGramDeps` owns the inflection
    # features / classes / stem names; `_PageSkeleton` owns the POSes, slots
    # and templates -- which are precisely the far endpoints of the five
    # registered closure edges, so leaving them out would make "individually
    # deselectable" true of the deps the closure does not pull in and false of
    # the ones it does. Step 5e above reads the skeleton page's CHECKED POSes
    # into `pos_picks`; this reads its UNCHECKED ones, which since T070 is a
    # different statement (omission no longer prevents a pull-in).
    _deselected: set = set()
    deps_page = (wizard.page_gram_deps()
                 if hasattr(wizard, "page_gram_deps") else None)
    if deps_page is not None and hasattr(deps_page, "deselected_dep_guids"):
        _deselected |= set(deps_page.deselected_dep_guids() or ())
    if skel_page is not None and hasattr(skel_page, "deselected_skeleton_guids"):
        _deselected |= set(skel_page.deselected_skeleton_guids() or ())
    if _deselected:
        selection = dataclasses.replace(
            selection,
            excluded_deps=frozenset(g.lower() for g in _deselected),
        )

    # Step 6: WS mapping -- from the writing-systems page, which owns it since
    # the FR-006 split. `page_project_ws()` no longer answers for the mapping,
    # and the hasattr guards keep the fake wizards in the unit suite (which
    # supply only the pages they exercise) working unchanged.
    #
    # `WSMapping` validates 1:1 in its `__post_init__`, so building it is a step
    # that can FAIL on what the operator chose rather than on project state --
    # two source writing systems pointed at one target. That must arrive as this
    # function's documented `(None, None)`, with the reason kept for the caller's
    # dialog: raising here escapes the Qt slot that called us, and an exception
    # crossing a slot boundary is either a dead button or an abort (see
    # `standalone/crashlog.py`). Dry run was a dead button for exactly this.
    ws_page = wizard.page_writing_systems() \
        if hasattr(wizard, "page_writing_systems") else None
    try:
        ws_mapping = ws_page.ws_mapping() \
            if ws_page is not None and hasattr(ws_page, "ws_mapping") else None
    except ValueError as exc:
        _set_plan_failure_reason(
            wizard,
            f"The writing-system mapping on the Writing Systems step is not "
            f"one-to-one: {exc}\n\nGo back to Writing Systems and give each "
            f"source writing system its own target, or SKIP one of them.",
        )
        return (None, None)

    # FR-023 row 12 -- "Building the transfer plan...". The indicator covers
    # steps 7 and 8, which is where the wait is: everything above is dict merges
    # over trees the operator has already populated, while `compute_preview`
    # walks the source for every selected category.
    #
    # The total is the declared unit -- selected categories -- and it is knowable
    # here and not earlier, because the merges above are what decide which
    # categories are in. It is a `len()` over a dict already in hand, so no count
    # is paid for it (FR-014d).
    #
    # No intermediate ticks, deliberately: `compute_preview` is one engine call
    # and takes no sink, so there is no inside for a walk to report from. The
    # single tick on success is what leaves the last frame reading complete
    # rather than stalled; a failure never reaches it and the bar is dismissed
    # where it stood (FR-020).
    n_categories = sum(1 for on in selection.categories.values() if on)
    with _page_progress(wizard, "plan_assembly", n_categories) as prog:
        # Step 7: compute preview; return (None, None) on failure or None payload.
        state, payload = gt_api.compute_preview(context, selection, ws_mapping)
        if payload is None:
            return (None, None)
        prog.tick(n_categories)

        # Step 8: build run report and return.
        phon_warnings = _phonology_excluded_lossy_for(wizard)
        # QC P1 (cycle-1 review, feature 024): surface the plan's projected drops
        # (Lib/references.py `decide_reference`, run read-only during AFFIXES/
        # STEMS plan_action) here too, so the wizard's Preview report is
        # symmetric with both Move and the main-window Preview path.
        # Feature 024 (T023, FR-013): per-object FidelityStatus, mirroring the
        # Move-mode wiring in `Lib/transfer.py.execute`.
        if __package__:
            from ..categories import compute_fidelity_by_guid
        else:
            from categories import compute_fidelity_by_guid  # type: ignore
        _plan_dropped = getattr(payload, "dropped_items", ())
        report = RunReport.build_from_plan(
            payload, RunMode.PREVIEW, extra_excluded_lossy=phon_warnings,
            extra_dropped_items=_plan_dropped,
            fidelity_by_guid=compute_fidelity_by_guid(_plan_dropped),
        )
    return (payload, report)
