"""End-to-end orchestration helpers (no pytest asserts; reusable).

Drives the api.py engine facade against a live FLEx project pair:

    source (read-only) --compute_preview--> RunPlan --execute_move--> RunReport

All FLEx / flexicon calls are made lazily inside functions so this module
imports cleanly on a host without flexicon (the test module skips in that case).
ASCII-only console output.

Public API
----------
build_full_selection(exclude=frozenset({GrammarCategory.STEMS})) -> Selection
    Every GrammarCategory member set True except those in ``exclude``. All
    pick-sets left empty (engine walks all POSes / transfer-all leaf items).

run_full_transfer(source_name, target_name, target_path) -> (RunPlan, RunReport)
    Opens source RO, binds target, compute_preview, execute_move. Sets the
    GRAMTRANS_DEBUG env var first so export/persist diagnostics fire.

reopen_and_count(target_name) -> dict[str, int]
    Reopens the target fresh (read-only) and returns a few cheap, robust
    inventory counts to prove persistence. Defensive: a missing accessor is
    simply omitted from the returned dict.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from gramtrans.Lib import api
from gramtrans.Lib.debuglog import DEBUG_ENV
from gramtrans.Lib.models import (
    GrammarCategory, RunPlan, RunReport, Selection,
    WSKind, WSMapping, WSMappingEntry,
)


# ---------------------------------------------------------------------------
# Selection builder
# ---------------------------------------------------------------------------

def build_full_selection(
    exclude: frozenset = frozenset({GrammarCategory.STEMS}),
) -> Selection:
    """Build a Selection with EVERY GrammarCategory True except ``exclude``.

    Pick-sets (pos_picks / affix_picks / stem_picks / leaf_item_picks) are left
    empty so the engine walks all POSes and transfers all leaf items.
    Custom Fields is included (it is a normal GrammarCategory member), which is
    what exercises the PATH-CLOSE-REBIND persist branch in execute_move.
    """
    categories = {
        cat: True
        for cat in GrammarCategory
        if cat not in exclude
    }
    return Selection(categories=categories)


# ---------------------------------------------------------------------------
# Project open helpers (lazy flexicon import)
# ---------------------------------------------------------------------------

_FLEX_INITIALIZED = False


def _ensure_flex_initialized() -> None:
    """Make FieldWorks AND the SLDR ready for an OpenProject.

    Standalone (non-FlexTools-host) processes MUST initialize the FieldWorks
    libraries before any OpenProject; the host normally does this at startup.
    Skipping it surfaces as ``RegistryHelper.get_CompanyKey()`` throwing
    ArgumentNullException on the first open. Idempotent + safe to re-call.

    Delegates to ``gramtrans.Lib.flexinit``, which re-verifies the SLDR on every
    call rather than trusting a once-per-process latch. A pytest session runs
    many features' fixtures in one process, so a ``FLExCleanup()`` in any of them
    takes the SLDR down for all the rest; the old latch then suppressed re-init
    and the next open quarantined the project's ``WritingSystemStore/*.ldml``
    files. Test projects are shared, real, and in ``Esperanto``'s case
    read-only-in-the-strong-sense, so this harness must not be the thing that
    damages them.
    """
    global _FLEX_INITIALIZED
    from gramtrans.Lib.flexinit import ensure_flex_initialized  # lazy

    ensure_flex_initialized()
    _FLEX_INITIALIZED = True


def _open_source_readonly(source_name: str):
    """Open the source project read-only and return the flexicon handle.

    Raises RuntimeError with an actionable message on failure (caller turns
    this into a pytest.skip).
    """
    from flexicon import FLExProject  # lazy -- absent on hosts without flexicon

    _ensure_flex_initialized()
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=source_name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001 -- LCM raises a variety of types
        raise RuntimeError(
            "[ERROR] Could not open source project %r read-only: %s"
            % (source_name, exc)
        ) from exc
    return proj


def _dump_plan_composition(plan) -> None:
    """Print per-category actions/skips + duplicate-(category,guid) detection
    for the plan produced by the REAL api path. ASCII-only."""
    from collections import Counter

    def _cat(x):
        c = getattr(x, "category", None)
        return getattr(c, "value", None) or str(c)

    acts = Counter(_cat(a) for a in plan.actions)
    skps = Counter(_cat(s) for s in plan.skips)
    seen = Counter((_cat(a), a.source_guid) for a in plan.actions)
    dups = {k: n for k, n in seen.items() if n > 1}
    print("[PLAN] === actions by category (total=%d) ===" % len(plan.actions))
    for k, n in acts.most_common():
        print("[PLAN]   %-22s %4d" % (k, n))
    print("[PLAN] === skips by category (total=%d) ===" % len(plan.skips))
    for k, n in skps.most_common():
        print("[PLAN]   %-22s %4d" % (k, n))
    print("[PLAN] === duplicate (category,guid) action rows: %d distinct ==="
          % len(dups))
    for (k, g), n in sorted(dups.items(), key=lambda kv: -kv[1])[:8]:
        print("[PLAN]   %dx  %-14s %s" % (n, k, g))


# ---------------------------------------------------------------------------
# Full transfer orchestration
# ---------------------------------------------------------------------------

def _write_report_snapshot(report: RunReport, path: str) -> None:
    """Persist the RunReport as the JSON `census run --run-report` consumes.

    `RunReport.to_snapshot_json` is the single serialiser -- the census reads
    `context.run_id`, `per_category` and (since T024d-a) `matched_to_source`
    out of exactly this shape, so writing anything hand-rolled here would let
    the harness and the census disagree about what a run report is.
    """
    import pathlib

    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_snapshot_json(), encoding="utf-8")
    print("[INFO] run report written: %s" % (target,))


def run_full_transfer(
    source_name: str,
    target_name: str,
    target_path: str,
    *,
    exclude: Optional[frozenset] = None,
    ws_mapping_mode: str = "default-vernacular",
    report_path: Optional[str] = None,
    preview_only: bool = False,
    selection_transform=None,
) -> Tuple[RunPlan, RunReport]:
    """Run a full (all-categories-except-STEMS by default) transfer end to end.

    Sets GRAMTRANS_DEBUG=1 (so export/persist diagnostics fire), opens the
    source read-only, binds the target for write, computes the preview plan,
    and executes the move. Returns ``(plan, report)``.

    The source handle is closed in a finally block; the target handle is
    closed there too (execute_move never closes the caller's handle -- on the
    custom-field path it persists via in-session checkpoints instead).

    Keyword-only options, all defaulting to the pre-T024c behaviour so the
    dozen existing callers are byte-identical:

    ``exclude``
        Passed to `build_full_selection`. ``None`` keeps that function's own
        default (STEMS excluded). T024c passes ``frozenset()`` because a FULL
        copy must not exclude stems -- the census then measures what a full
        copy actually does, not what a stem-less one does.
    ``ws_mapping_mode``
        ``"default-vernacular"`` (the default) maps only source default vern ->
        target default vern. ``"full"`` gives EVERY source writing system an
        entry, creating in the target any tag it lacks. WS handles are
        per-project and not portable (measured: 999000002 is `en` in
        `Ngoreme FLEx` and `ngq` in `Ngoreme Target`), so a source alternative
        with no mapped counterpart is exactly the T024g failure class; "full"
        is what a real full copy needs.
    ``report_path``
        When set, the RunReport snapshot is written there as JSON. T024c needs
        it on disk because `census run --run-report` is a separate process:
        without it the post-transfer census cannot attribute a single match and
        every out-of-scope class stays in `unexplained_shortfall`.
    ``selection_transform``
        Optional ``Selection -> Selection`` applied after
        `build_full_selection`. Feature 038 T070-T072 uses it to set
        `excluded_deps` on an otherwise identical run, so the deselection is
        the only difference between the two plans being compared. ``None``
        (the default) leaves every existing caller byte-identical.
    ``preview_only``
        Stop after `compute_preview` and return ``(plan, None)`` -- NO
        `execute_move`, so nothing is written. Added for feature 038 T067,
        which has to compare the SAME plan built twice (once with
        `CLOSURE_EDGES_VERIFIED` live, once with it emptied) to establish that
        registering a closure edge added edges to the plan and changed nothing
        else. Building the plan through this function rather than a second
        hand-rolled copy of the writing-system setup above is the point: two
        plans are only comparable if everything except the registry was
        identical, and a duplicated harness cannot promise that.
    """
    # Ensure the export/persist diagnostics fire for this run.
    os.environ.setdefault(DEBUG_ENV, "1")

    context = None
    source_handle = _open_source_readonly(source_name)
    try:
        stub = api.initialize_run(
            source_handle,
            source_project_name=source_name,
            source_project_path="",
        )
        choice = api.TargetCandidate(
            project_name=target_name,
            project_path=target_path,
        )
        context = api.bind_target(stub, choice)

        selection = (build_full_selection() if exclude is None
                     else build_full_selection(exclude=exclude))
        if selection_transform is not None:
            # Feature 038 T070-T072: the ONLY way to measure a deselection
            # live is to build the same plan twice and change nothing but the
            # Selection. A caller that hand-rolled the second Selection could
            # not promise "nothing else differs", which is the whole claim.
            selection = selection_transform(selection)
        # Map the source's default vernacular WS -> the target's default
        # vernacular WS (identity for the default vern). This is the DEFAULT
        # mode, kept exactly as it was for every pre-T024c caller.
        # GetDefaultVernacularWS() returns a (language-tag, Name) tuple.
        src_vern_tag = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern_tag = context.target_handle.GetDefaultVernacularWS()[0]
        if ws_mapping_mode == "full":
            # Every source WS gets an entry; a tag the target already has maps
            # to itself, a tag it lacks is created there. Leaving a source
            # alternative unmapped is the T024g failure class: the handle is
            # per-project, so it either throws in
            # `WritingSystemManager.Get` (discarding the whole unit of work) or
            # -- worse -- resolves silently to a DIFFERENT writing system.
            target_ids = {w.Id
                          for w in context.target_handle.WritingSystems.GetAll()}
            entries = tuple(
                WSMappingEntry(
                    source_ws_id=w.Id,
                    source_ws_kind=(WSKind.VERNACULAR if w.Id == src_vern_tag
                                    else WSKind.ANALYSIS),
                    target_ws_id=w.Id,
                    create_in_target=(w.Id not in target_ids),
                )
                for w in source_handle.WritingSystems.GetAll()
            )
            ws_mapping = WSMapping(entries=entries)
        elif ws_mapping_mode == "default-vernacular":
            ws_mapping = WSMapping(entries=(
                WSMappingEntry(
                    source_ws_id=src_vern_tag,
                    source_ws_kind=WSKind.VERNACULAR,
                    target_ws_id=tgt_vern_tag,
                    create_in_target=False,
                ),
            ))
        else:
            raise ValueError(
                "[ERROR] unknown ws_mapping_mode %r -- expected "
                "'default-vernacular' or 'full'" % (ws_mapping_mode,))
        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError(
                "[ERROR] compute_preview did not return PREVIEW_READY; got %r"
                % (state,)
            )
        _dump_plan_composition(plan)

        if preview_only:
            # Principle III: Preview writes nothing, so there is nothing to
            # flush and no report to build. The finally block still closes
            # both handles.
            return plan, None

        report = api.execute_move(context, plan)
        if report_path is not None:
            _write_report_snapshot(report, report_path)
        return plan, report
    finally:
        # The harness IS the host here: on the plain path FLEx only persists
        # writes on CloseProject() (in production gramtrans._run_gui does it),
        # so we close the target to flush before any reopen/count. On the
        # custom-field path execute_move has ALREADY persisted schema+values
        # via in-session checkpoints. The watcher labels a co-held hang in
        # the log after the deadline (it cannot abort the call -- LCM thread
        # affinity forbids off-thread closes); a raised close error is
        # warning-grade here.
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle,
                    api._SCHEMA_CLOSE_TIMEOUT_S,
                    "harness target handle",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] target CloseProject failed/timed out: {exc}")
        try:
            source_handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Persistence-proof inventory counts
# ---------------------------------------------------------------------------

# (label, accessor-chain) pairs. Each accessor chain is applied against the
# open flexicon project; a chain that raises / is absent is skipped (defensive).
# These are intentionally cheap, top-level owning collections that a full
# transfer is expected to grow.
_COUNT_ACCESSORS = (
    ("pos", lambda p: p.lp.PartsOfSpeechOA.PossibilitiesOS.Count),
    ("phonemes", lambda p: p.lp.PhonologicalDataOA.PhonemeSetsOS[0].PhonemesOC.Count),
    ("entries", lambda p: p.lexicon.LexiconNumberOfEntries()),
)


def reopen_and_count(target_name: str) -> dict:
    """Reopen ``target_name`` fresh (read-only) and return inventory counts.

    Returns a dict of ``{label: int}`` for each accessor that resolves without
    error. A missing / renamed accessor is silently omitted so the harness
    survives flexicon API drift. The project is always closed before returning.
    """
    from flexicon import FLExProject  # lazy

    _ensure_flex_initialized()
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=target_name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "[ERROR] Could not reopen target %r for counting: %s"
            % (target_name, exc)
        ) from exc

    counts: dict = {}
    try:
        for label, accessor in _COUNT_ACCESSORS:
            try:
                value = accessor(proj)
            except Exception:  # noqa: BLE001 -- accessor absent / shape differs
                continue
            try:
                counts[label] = int(value)
            except (TypeError, ValueError):
                continue
    finally:
        try:
            proj.CloseProject()
        except Exception:  # noqa: BLE001
            pass
    return counts


def total_count(counts: dict) -> int:
    """Sum of all inventory counts in a ``reopen_and_count`` result."""
    return sum(counts.values())
