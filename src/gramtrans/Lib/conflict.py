"""Phase 2 — per-field conflict detection and resolution.

This module is the seam between the Preview-phase planner
(`Lib/preview.py`) and the user-interactive resolver
(`Lib/ui/conflict_dialog.py` in production, FakeConflictResolver in
tests).  Per constitution Principle III (Preview-Before-Mutate), every
ConflictPrompt is produced during planning, BEFORE any LCM mutation.

Public surface:
- `UserCancelled`: raised by `ConflictResolver.resolve` if the user
  dismisses the dialog. The caller MUST catch this and exit before any
  `transfer.execute()` call.
- `ConflictResolver`: Protocol — the interactive prompt's contract.
  Production impl: `Lib/ui/conflict_dialog.py.ConflictDialog`.
- `detect_conflicts(...)`: producer (T017, Phase 3 / US1).
- `_deterministic_merge(...)`: research.md R4 (T018, US1).
- `load_prior_decision(...)`: US3 prior-run recall (T040).
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol

_log = logging.getLogger(__name__)

if __package__:
    from .residue import strip_residue_props
    from .models import (
        ConflictPrompt,
        MergeDecision,
        MergeDecisionLog,
        MergeResolution,
    )
else:
    from residue import strip_residue_props  # type: ignore
    from models import (
        ConflictPrompt,
        MergeDecision,
        MergeDecisionLog,
        MergeResolution,
    )


# Property-name patterns that are NEVER merge-eligible (scalar fields
# whose "merge" semantics are not defined: ints, bools, GUID refs).
# When detected, the ConflictPrompt is emitted with merge_eligible=False
# and the UI hides the MERGE button -- only TAKE_SOURCE / KEEP_TARGET /
# SKIP / EDIT_CUSTOM remain.
_NON_MERGEABLE_TYPES = (int, bool, type(None))


class UserCancelled(Exception):
    """The user dismissed an interactive dialog without completing it.

    Phase 2 (FR-213) requires this to be raised by ConflictResolver /
    WSResolver implementations.  The outermost MainFunction catches it
    and returns before any transfer.execute() call, so the target
    project is left bit-identical.
    """


class ConflictResolver(Protocol):
    """Production: PyQt ConflictDialog.  Tests: FakeConflictResolver.

    The protocol is structural -- any object exposing a compatible
    `resolve(...)` method satisfies it.  No runtime check is performed.
    """

    def resolve(self, prompts):
        """Block until the user has answered every prompt.

        Args:
            prompts: tuple[ConflictPrompt, ...].

        Returns:
            tuple[MergeDecision, ...] of the same length and order.

        Raises:
            UserCancelled: if the user dismisses the dialog.
        """
        ...


# ============================================================================
# T017 -- detect_conflicts: produce ConflictPrompt list from a (src, tgt) pair
# ============================================================================

def _is_merge_eligible(value) -> bool:
    """research.md R4: scalars (int/bool/None) are NOT merge-eligible.
    Strings, lists, tuples, sets, dicts (multistrings live as dicts of
    ws_handle -> str), and arbitrary objects with __eq__ are eligible.
    """
    return not isinstance(value, _NON_MERGEABLE_TYPES)


def detect_conflicts(
    src_props,
    tgt_pre_props,
    target_guid: str,
    target_class_name: str,
    prior_log: Optional[MergeDecisionLog] = None,
):
    """Produce a ConflictPrompt tuple from a source/target syncable-props pair.

    Per FR-216 / contracts/conflict-prompt.md:
    - Iterate the INTERSECTION of keys (a key present only on one side
      is not a conflict; Phase 1's source-wins or target-preserved
      applies automatically).
    - Suppress identical-valued pairs (structural equality).
    - For surviving conflicts, attach `prior_log`'s matching decision
      as `prior_decision` when present (US3 recall).
    - Determine `merge_eligible` per type.
    - Return tuple ordered alphabetically by `field_name`.

    Args:
        src_props: dict of source's syncable properties.
        tgt_pre_props: dict of target's pre-overwrite syncable properties.
        target_guid: target object's GUID (string).
        target_class_name: target's LCM ClassName.
        prior_log: optional MergeDecisionLog from a prior run's residue.

    Returns:
        tuple[ConflictPrompt, ...] sorted by field_name.
    """
    if not isinstance(src_props, dict) or not isinstance(tgt_pre_props, dict):
        return ()
    # Build prior-decision lookup once.
    prior_by_field = {}
    if prior_log is not None:
        for d in prior_log.decisions:
            prior_by_field[d.field_name] = d
    prompts = []
    for key in sorted(set(src_props) & set(tgt_pre_props)):
        right = src_props[key]
        left = tgt_pre_props[key]
        if left == right:
            continue  # FR-216: identical -> no prompt
        prompts.append(
            ConflictPrompt(
                target_guid=target_guid,
                target_class_name=target_class_name,
                field_name=key,
                left_value=left,
                right_value=right,
                prior_decision=prior_by_field.get(key),
                merge_eligible=_is_merge_eligible(left) and _is_merge_eligible(right),
            )
        )
    return tuple(prompts)


# ============================================================================
# T018 -- _deterministic_merge: research.md R4 semantics
# ============================================================================

class _MergeNotEligible(Exception):
    """Raised when callers try to merge two scalars."""


def _deterministic_merge(left, right, run_id: str):
    """research.md R4 deterministic merge semantics:

    - str: <left>\\n--- merged GT-<run_id> ---\\n<right>
    - dict (multistring-shaped: {ws_handle: str}): recurse per-key,
      passing through left/right slots when only one side has them.
    - list / tuple / set: set-union preserving left order followed by
      right-only entries.
    - int / bool / None: not eligible -> raise _MergeNotEligible.

    Args:
        left: target's pre-overwrite value.
        right: source's value.
        run_id: GT-YYYYMMDD-HHMMSS run id, embedded in the separator.

    Returns:
        The merged value of the same type as the inputs.

    Raises:
        _MergeNotEligible: if either side is a scalar (int/bool/None).
    """
    if isinstance(left, _NON_MERGEABLE_TYPES) or isinstance(right, _NON_MERGEABLE_TYPES):
        raise _MergeNotEligible(
            f"cannot merge scalar values: left={type(left).__name__} "
            f"right={type(right).__name__}"
        )
    if isinstance(left, str) and isinstance(right, str):
        return f"{left}\n--- merged {run_id} ---\n{right}"
    if isinstance(left, dict) and isinstance(right, dict):
        out = {}
        for k in sorted(set(left) | set(right)):
            if k in left and k in right:
                out[k] = _deterministic_merge(left[k], right[k], run_id)
            elif k in left:
                out[k] = left[k]
            else:
                out[k] = right[k]
        return out
    if isinstance(left, (list, tuple, set, frozenset)) and isinstance(
        right, (list, tuple, set, frozenset)
    ):
        seen = set()
        out_list = []
        for item in list(left) + list(right):
            try:
                key = item
                if key in seen:
                    continue
                seen.add(key)
            except TypeError:
                # Unhashable item -- fall back to linear search.
                if item in out_list:
                    continue
            out_list.append(item)
        if isinstance(left, tuple):
            return tuple(out_list)
        if isinstance(left, (set, frozenset)):
            return type(left)(out_list)
        return out_list
    # Mixed types -- last resort: stringify and concat.
    return f"{left!r}\n--- merged {run_id} ---\n{right!r}"


# ============================================================================
# Conflict-collection helper used by MainFunction (US1 wiring)
# ============================================================================
# Per research.md R1, the planner does not itself capture tgt_pre_props
# (which would double the LCM read for every overwritten object).
# Instead, MainFunction calls this helper after build_run_plan to walk
# plan.overwrites once, capture pre-props + src_props for each, and emit
# ConflictPrompts.  The resolver then runs once on the whole tuple; the
# resolution is folded into an InteractiveSession that execute() consumes.

# Mapping from GrammarCategory.value to the Operations attribute pair
# (source-side accessor, target-side accessor, target-object lookup
# function name) used to fetch syncable properties.  For categories that
# don't have a simple ApplySyncableProperties surface (Templates / Slots /
# MSAs / PhEnvironments), we fall back to None and skip conflict detection.
_OW_OPS = {
    "pos":       ("POS",       "POS",       "_find_target_pos_by_guid"),
    "entry":     ("LexEntry",  "LexEntry",  "_find_target_entry_by_guid"),
    "sense":     ("Senses",    "Senses",    "_find_target_sense_by_guid"),
    "allomorph": ("Allomorphs", "Allomorphs", "_find_target_allo_by_guid"),
}


def _unwrap(obj):
    """flexicon sometimes returns wrapper objects with a .concrete attr
    holding the underlying LCM interface; unwrap before any ICmObject cast.
    Mirrors transfer.py._unwrap."""
    return obj.concrete if hasattr(obj, "concrete") else obj


def _find_target_entry_by_guid(target, guid):
    from SIL.LCModel import ICmObject  # lazy
    for te in target.LexEntry.GetAll():
        concrete = _unwrap(te)
        if str(ICmObject(concrete).Guid).lower() == guid.lower():
            return concrete
    return None


def _find_target_sense_by_guid(target, guid, owner_entry_guid=""):
    from SIL.LCModel import ICmObject  # lazy
    entry = _find_target_entry_by_guid(target, owner_entry_guid) if owner_entry_guid else None
    if entry is not None:
        for s in target.LexEntry.GetSenses(entry):
            concrete = _unwrap(s)
            if str(ICmObject(concrete).Guid).lower() == guid.lower():
                return concrete
    return None


def _find_target_allo_by_guid(target, guid, owner_entry_guid=""):
    from SIL.LCModel import ICmObject  # lazy
    entry = _find_target_entry_by_guid(target, owner_entry_guid) if owner_entry_guid else None
    if entry is not None:
        for a in target.Allomorphs.GetAll(entry):
            concrete = _unwrap(a)
            if str(ICmObject(concrete).Guid).lower() == guid.lower():
                return concrete
    return None


def _find_target_pos_by_guid(target, guid):
    from SIL.LCModel import ICmObject  # lazy
    for p in target.POS.GetAll(recursive=True):
        concrete = _unwrap(p)
        if str(ICmObject(concrete).Guid).lower() == guid.lower():
            return concrete
    return None


def _is_live_project(project) -> bool:
    """True iff `project` is a live flexicon `FLExProject`, judged by its
    `lp` (the LCM LangProject) being a real .NET object.

    Delegates to the single `_is_dotnet_object` definition in `Lib/texts.py`
    (imported lazily, as categories.py/reversals.py do). Never raises."""
    if __package__:
        from . import texts as _texts
    else:
        import texts as _texts  # type: ignore
    try:
        lp = getattr(project, "lp", None)
    except Exception:  # noqa: BLE001 -- a fake may raise on attribute access
        return False
    return _texts._is_dotnet_object(lp)


def collect_overwrite_conflicts(plan, source, target, prior_logs_by_guid=None):
    """Walk plan.overwrites; for every category whose ops surface supports
    GetSyncableProperties, capture src_props + tgt_pre_props and call
    detect_conflicts.  Returns a flat tuple of ConflictPrompt across all
    overwrites.

    `prior_logs_by_guid` (US3 recall): optional dict[str -> MergeDecisionLog]
    threaded into detect_conflicts per object.

    NOTE: this helper is for caller-side MVP collection BEFORE execute()
    runs.  It performs LCM reads but no writes; safe to call during
    Preview phase or just before Move (the user prompt happens between
    this call and execute()).
    """
    prior_logs_by_guid = prior_logs_by_guid or {}
    # Liveness test asks the OBJECT, not the process (#57; the bug class of
    # f9676ad / 201d9cd). This used to bail only on `ImportError` from
    # `from SIL.LCModel import ICmObject` -- a fact about the PROCESS. Once
    # anything has imported flexicon the import succeeds, the bail is dead,
    # and a mocked source/target reaches `ICmObject(fake)`, which raises
    # `TypeError` out of this function instead of returning ().
    if not (_is_live_project(source) and _is_live_project(target)):
        # Not a live LCM project pair -- caller is presumably running unit
        # tests with mocked source/target.  Bail.
        return ()
    from SIL.LCModel import ICmObject  # lazy; both projects are live
    prompts = []
    # Build source-entry index once for entry/sense/allomorph lookups.
    src_entry_by_guid = {}
    for se in source.LexEntry.GetAll():
        concrete = _unwrap(se)
        src_entry_by_guid[str(ICmObject(concrete).Guid).lower()] = concrete
    for ow in getattr(plan, "overwrites", ()):
        cat = ow.category.value
        ops_info = _OW_OPS.get(cat)
        if ops_info is None:
            continue
        src_ops_name, tgt_ops_name, finder_name = ops_info
        src_ops = getattr(source, src_ops_name, None)
        tgt_ops = getattr(target, tgt_ops_name, None)
        if src_ops is None or tgt_ops is None:
            continue
        finder = globals().get(finder_name)
        if finder is None:
            continue
        # Look up source object.
        if cat == "pos":
            # T106: identity-only, and DELIBERATELY so. `ow.target_guid` is
            # already a DESTINATION GUID -- the same value this function uses a
            # few lines down as a destination identity key
            # (`prior_logs_by_guid.get(ow.target_guid)`), and every producer of
            # a POS overwrite either verified the GUID present in the target or
            # took it from the matched destination object itself. Routing it
            # through the natural key would re-derive a decision Preview
            # already recorded, and could override a T091 reuse with a fresh
            # name match. Principle III.
            tgt_obj = finder(target, ow.target_guid)
            src_obj = None
            for p in source.POS.GetAll(recursive=True):
                concrete = _unwrap(p)
                if str(ICmObject(concrete).Guid).lower() == ow.source_guid.lower():
                    src_obj = concrete
                    break
        elif cat == "entry":
            tgt_obj = finder(target, ow.target_guid)
            src_obj = src_entry_by_guid.get(ow.source_guid.lower())
        elif cat == "sense":
            tgt_obj = finder(target, ow.target_guid, ow.owner_guid)
            src_entry = src_entry_by_guid.get(ow.owner_guid.lower())
            src_obj = None
            if src_entry is not None:
                for s in source.LexEntry.GetSenses(src_entry):
                    concrete = _unwrap(s)
                    if str(ICmObject(concrete).Guid).lower() == ow.source_guid.lower():
                        src_obj = concrete
                        break
        elif cat == "allomorph":
            tgt_obj = finder(target, ow.target_guid, ow.owner_guid)
            src_entry = src_entry_by_guid.get(ow.owner_guid.lower())
            src_obj = None
            if src_entry is not None:
                for a in source.Allomorphs.GetAll(src_entry):
                    concrete = _unwrap(a)
                    if str(ICmObject(concrete).Guid).lower() == ow.source_guid.lower():
                        src_obj = concrete
                        break
        else:
            continue
        if src_obj is None or tgt_obj is None:
            continue
        try:
            src_props = src_ops.GetSyncableProperties(src_obj)
            # Issue #87: compare the target without our own [GT-Tag] line.
            tgt_pre_props = strip_residue_props(
                tgt_ops.GetSyncableProperties(tgt_obj)
            )
        except (AttributeError, TypeError):
            continue
        prior_log = prior_logs_by_guid.get(ow.target_guid)
        for p in detect_conflicts(
            src_props=src_props,
            tgt_pre_props=tgt_pre_props,
            target_guid=ow.target_guid,
            target_class_name=cat,
            prior_log=prior_log,
        ):
            prompts.append(p)
    return tuple(prompts)


def load_prior_log(tgt_object):
    """T040 / US3 -- read the target object's residue tag and recover the
    MergeDecisionLog from its `merge=` segment, or None if absent /
    unparseable.

    Per FR-215 graceful degradation: a corrupted tag returns None so
    the caller falls back to fresh-prompt behaviour for that field.

    Args:
        tgt_object: an LCM object exposing `LiftResidue` (str-typed on
            ILexEntry / IMoAffixAllomorph / IMoInflAffMsa per Phase 1.3c)
            or `Description` (multistring on Carrier-B objects).

    Returns:
        MergeDecisionLog or None.
    """
    if __package__:
        from .residue import ImportResidueTag
    else:
        from residue import ImportResidueTag
    if tgt_object is None:
        return None
    # Try LiftResidue first (Carrier A); fall back to Description (Carrier B).
    lift = getattr(tgt_object, "LiftResidue", None)
    text = None
    if isinstance(lift, str) and lift:
        text = lift
    elif lift is not None and hasattr(lift, "get_String"):
        # Multistring LiftResidue: pull best-available text.
        try:
            ts = lift.BestAnalysisAlternative
            text = (ts.Text or "") if ts is not None else ""
        except (AttributeError, TypeError):
            text = ""
    if not text:
        desc = getattr(tgt_object, "Description", None)
        if desc is not None:
            try:
                ts = desc.BestAnalysisAlternative
                text = (ts.Text or "") if ts is not None else ""
            except (AttributeError, TypeError):
                text = ""
    if not text:
        return None
    tag = ImportResidueTag.parse(text)
    if tag is None:
        return None
    return tag.decode_merge_log()


def load_prior_decision(tgt_object, field_name: str):
    """T040 / US3 -- recover the prior-run MergeDecision for `field_name`
    on `tgt_object`, or None if absent.

    Convenience wrapper around `load_prior_log` for callers that want a
    per-field lookup.
    """
    log = load_prior_log(tgt_object)
    if log is None:
        return None
    for d in log.decisions:
        if d.field_name == field_name:
            return d
    return None


def build_session_from_resolutions(prompts, decisions):
    """Helper: given a tuple of ConflictPrompts and the matching tuple of
    MergeDecisions returned by a ConflictResolver, build an
    InteractiveSession with merge_decisions_by_guid populated.

    Args:
        prompts: tuple[ConflictPrompt, ...] -- the input the resolver received.
        decisions: tuple[MergeDecision, ...] -- same length, same order.

    Returns:
        InteractiveSession.

    Raises:
        ValueError: if lengths differ.
    """
    if __package__:
        from .models import InteractiveSession
    else:
        from models import InteractiveSession
    if len(prompts) != len(decisions):
        raise ValueError(
            f"prompts/decisions length mismatch: {len(prompts)} vs {len(decisions)}"
        )
    decisions_by_guid = {}
    for p, d in zip(prompts, decisions):
        log = decisions_by_guid.setdefault(p.target_guid, [])
        log.append(d)
    # Build MergeDecisionLog per target_guid.
    if __package__:
        from .models import MergeDecisionLog
    else:
        from models import MergeDecisionLog
    out = {
        guid: MergeDecisionLog(target_guid=guid, decisions=tuple(decs))
        for guid, decs in decisions_by_guid.items()
    }
    return InteractiveSession(merge_decisions_by_guid=out)


# ============================================================================
# 022-disposition-model: per-item disposition computation (T015-T017, T020-T022)
# ============================================================================

import enum as _enum


class ItemDisposition(_enum.Enum):
    """Per-item outcome computed during the Preview / plan phase (022 FR-005).

    IGNORE   : item was never selected by the user; it never enters the plan.
    SKIP     : selected, present in target, all user-editable fields in sync
               (2-way: source == target; or 3-way: baseline unchanged too).
               No write occurs.
    ADD      : not present in target; will be added regardless of intent.
    UPDATE   : present; >=1 diverged field; UPDATE intent governs write
               (non-destructive: source wins where diverged, preserves where
               source is empty).
    OVERWRITE: present; >=1 diverged field; OVERWRITE intent governs write
               (destructive: source wins unconditionally, may blank target).
    """
    IGNORE = "ignore"
    SKIP = "skip"
    ADD = "add"
    UPDATE = "update"
    OVERWRITE = "overwrite"


def _is_empty(value) -> bool:
    """Return True if `value` is semantically empty for UPDATE skip-write decisions.

    Empty means:
    - None
    - str: empty or whitespace-only, OR the flexicon empty-sentinel "***" (after
      strip).  A value that strips to "***" is treated as unset (FR-003 P1-1/P1-2).
    - dict (multistring): empty dict, OR every value is itself _is_empty (all-empty
      multistring like {"en":"","fr":""} must be treated as empty — P1-1).
    - list/tuple/set/frozenset: zero-length.
    Non-empty scalars (int 0, bool False) are considered non-empty because they
    carry intentional data.
    """
    _EMPTY_SENTINEL = "***"
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped == _EMPTY_SENTINEL
    if isinstance(value, dict):
        if len(value) == 0:
            return True
        # Multistring: empty iff every value is itself empty (P1-1).
        return all(_is_empty(v) for v in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) == 0
    return False


def compute_field_diff(src_props: dict, tgt_props: dict) -> dict:
    """Return a dict of {field_name: (src_value, tgt_value)} for fields that differ.

    Only keys present in BOTH dicts are compared (intersection).  A key absent
    from one side is not a conflict (source-wins or target-preserved by caller).
    """
    if not isinstance(src_props, dict) or not isinstance(tgt_props, dict):
        return {}
    diff = {}
    for key in sorted(set(src_props) & set(tgt_props)):
        if src_props[key] != tgt_props[key]:
            diff[key] = (src_props[key], tgt_props[key])
    return diff


def _is_multistring(value) -> bool:
    """True for a {ws_id: text} multistring dict as GetSyncableProperties emits
    it (every value a str or None). Nested-structure dicts (feature specs etc.)
    are NOT multistrings and are compared whole."""
    return isinstance(value, dict) and all(
        v is None or isinstance(v, str) for v in value.values()
    )


def _text_eq(a, b) -> bool:
    """Exact equality, deliberately: the Preview planner's per-WS comparison
    (`categories._compare_multistring_per_ws`) compares text exactly, and the
    Merge writer must not disagree with what Preview promised. Unicode
    normalisation, if adopted, belongs in both places at once."""
    return a == b


def _merge_delta(src_val, tgt_val, ws_map=None):
    """The ONE real-Merge write decision for a single field (issue #22 Part 1).

    Returns the value to hand to ``ApplySyncableProperties`` for this field,
    or None when Merge must not write it:

    - empty source (None / "" / "***" / {} / [] / all-empty multistring)
      -> None: never blank a target from an empty source;
    - multistring -> only the NON-EMPTY source alternatives whose text differs
      from the target's alternative at the (``ws_map``-translated) target WS.
      Target-only alternatives are never in the delta, and an alternative that
      already matches is not re-written, so a source ``{"en": "x"}`` against a
      target ``{"en": "x", "fr": "z"}`` is NOT a divergence (it used to be:
      the whole-dict compare made every re-run an UPDATE);
    - anything else -> the source value when it differs from the target.

    A target key that is absent (flexicon omits empty fields from
    GetSyncableProperties) is treated as empty, so a source-only key is filled.
    """
    if _is_empty(src_val):
        return None
    if _is_multistring(src_val):
        tgt_alts = tgt_val if isinstance(tgt_val, dict) else {}
        delta = {}
        for ws_id, text in src_val.items():
            if _is_empty(text):
                continue
            tgt_ws = ws_map.get(ws_id, ws_id) if ws_map else ws_id
            if _text_eq(text, tgt_alts.get(tgt_ws)):
                continue
            delta[ws_id] = text
        return delta or None
    if _text_eq(src_val, tgt_val):
        return None
    return src_val


def compute_merge_fillable(src_props: dict, tgt_props: dict, ws_map=None) -> dict:
    """Return {field: (value_to_write, tgt_value)} for every field the UPDATE
    (real Merge) write semantic writes.

    Iterates the SOURCE keys (a key absent from the target is an empty target
    field -- audit blind spot 6) and applies :func:`_merge_delta` per field.
    :func:`apply_update_semantic` writes exactly this dict, and
    :func:`compute_disposition` resolves UPDATE vs SKIP from it, so disposition
    and writer agree by construction.

    It is used ONLY on the UPDATE path; the OVERWRITE path continues to rely on
    :func:`compute_field_diff` and is unaffected (Part 2 of issue #22).
    """
    if not isinstance(src_props, dict) or not isinstance(tgt_props, dict):
        return {}
    fillable = {}
    for key in sorted(src_props):
        tgt_val = tgt_props.get(key)
        delta = _merge_delta(src_props[key], tgt_val, ws_map=ws_map)
        if delta is not None:
            fillable[key] = (delta, tgt_val)
    return fillable


def compute_disposition(
    src_props,
    tgt_props,
    intent,
    prior_baseline=None,
    ws_map=None,
) -> "ItemDisposition":
    """Compute the per-item ItemDisposition (022 FR-005, T015, T020, T022).

    Args:
        src_props: dict of source's syncable properties (or None if item is
            new / not-yet-fetched).  None -> ADD.
        tgt_props: dict of target's syncable properties.  None -> ADD (not
            present in target).
        intent: ConflictMode — the user's chosen transfer intent for the
            category (LINK / UPDATE / OVERWRITE / ADD_NEW).
        prior_baseline: optional dict of the target's props at the time of the
            PRIOR run (from residue snapshot).  When provided, enables 3-way
            comparison: a field that matches *both* the baseline and the current
            target is "untouched" and contributes no divergence (auto-SKIP).
            When absent, 2-way comparison only (first-run behaviour, T022).
        ws_map: optional {source_ws_id: target_ws_id}; the same mapping the
            UPDATE writer receives, so the per-alternative comparison here
            matches the one :func:`apply_update_semantic` performs.

    Returns:
        ItemDisposition.

    Note: IGNORE is NOT computed here -- IGNORE is the disposition for items
    that were never selected and thus never enter the plan.  Callers that
    enumerate unselected items must assign IGNORE themselves.
    """
    # Lazy import to avoid a top-level circular dependency.
    if __package__:
        from .models import ConflictMode as _ConflictMode
    else:
        from models import ConflictMode as _ConflictMode  # type: ignore

    # Item not present in target -> ADD (regardless of intent).
    if tgt_props is None or src_props is None:
        return ItemDisposition.ADD

    # UPDATE (real Merge, issue #22 Part 1) without a baseline: the disposition
    # is decided by the SAME per-field delta the writer applies, so UPDATE
    # means "apply_update_semantic will write >= 1 field" and SKIP means it
    # would write nothing (identical, empty-source-only, or target-only-alt
    # differences). The intersection diff below is not consulted -- it can
    # neither see a source-only key nor tell an empty source from a change.
    if intent == _ConflictMode.UPDATE and prior_baseline is None:
        if compute_merge_fillable(src_props, tgt_props, ws_map=ws_map):
            return ItemDisposition.UPDATE
        return ItemDisposition.SKIP

    # Compute effective diff.
    if prior_baseline is not None:
        # 3-way: suppress fields where target matches baseline (untouched, T020).
        # A field is "diverged" only if it changed since the prior run in the
        # source direction, i.e. src != tgt AND (tgt changed since baseline OR
        # src changed since baseline).  Simplest safe interpretation: exclude
        # fields where tgt == baseline (no change in target since last run).
        raw_diff = compute_field_diff(src_props, tgt_props)
        diff = {
            k: v
            for k, v in raw_diff.items()
            if prior_baseline.get(k) != tgt_props.get(k)  # target drifted from baseline
            or src_props.get(k) != prior_baseline.get(k)   # source changed since baseline
        }
    else:
        # 2-way: any src != tgt is diverged (first-run behaviour, T022).
        diff = compute_field_diff(src_props, tgt_props)

    if not diff:
        # Zero diverged fields by intersection diff.  Under UPDATE (real Merge),
        # a source-only or empty-target field that a non-empty source would fill
        # is still a reason to write, but the intersection diff never sees it.
        # Detect those fillable fields so the item resolves to UPDATE, not SKIP.
        # (OVERWRITE and LINK/ADD_NEW keep SKIP here -- their behaviour is
        # unchanged.)
        if intent == _ConflictMode.UPDATE and compute_merge_fillable(
            src_props, tgt_props, ws_map=ws_map
        ):
            return ItemDisposition.UPDATE
        # Zero diverged fields -> SKIP (no write needed).
        return ItemDisposition.SKIP

    # >=1 diverged field: disposition follows intent.
    if intent in (_ConflictMode.LINK, _ConflictMode.ADD_NEW):
        # LINK / ADD_NEW: no field-level writes to existing items -> SKIP
        # (the item IS present; LINK writes nothing to it).
        return ItemDisposition.SKIP
    if intent == _ConflictMode.UPDATE:
        return ItemDisposition.UPDATE
    if intent == _ConflictMode.OVERWRITE:
        return ItemDisposition.OVERWRITE
    # Unknown intent: conservative SKIP.
    return ItemDisposition.SKIP


def _unapplied_parts(key, written, readback, ws_map=None):
    """Return a description of what of `written` is NOT on the read-back, or
    "" when everything requested landed.

    `readback` is a fresh ``GetSyncableProperties`` of the target taken after
    the writes. flexicon omits empty fields from that dict, so a key we wrote
    with a non-empty value that is still absent did not land. For a
    multistring only the alternatives we wrote are checked (at their
    ``ws_map``-translated target WS); a list is checked for containment.
    """
    if key not in readback:
        return "field absent on read-back"
    got = readback[key]
    if _is_multistring(written):
        got_alts = got if isinstance(got, dict) else {}
        missing = []
        for ws_id, text in written.items():
            tgt_ws = ws_map.get(ws_id, ws_id) if ws_map else ws_id
            if not _text_eq(text, got_alts.get(tgt_ws)):
                missing.append(tgt_ws)
        return ("writing system(s) %s not applied" % ", ".join(missing)) if missing else ""
    if isinstance(written, (list, tuple)) and isinstance(got, (list, tuple)):
        absent = [v for v in written if v not in got]
        return ("%d of %d value(s) not applied" % (len(absent), len(written))) if absent else ""
    return "" if _text_eq(written, got) else "read-back value differs"


def apply_update_semantic(src_props: dict, tgt_props: dict, ops, tgt_obj,
                          ws_map=None, report_sink=None, label: str = "") -> int:
    """Apply the real Merge (UPDATE) write semantic (022 FR-003, issue #22).

    Writes exactly :func:`compute_merge_fillable`'s delta, field by field:
    the SOURCE keys drive (a key the target dict omits is an empty target
    field and is filled); an empty source never blanks the target; for a
    multistring only the non-empty, differing source alternatives are written,
    so a target-only writing-system alternative is never touched.

    Partial applies are auditable (audit blind spot 5). Two failure kinds are
    surfaced on `report_sink.Warning` (and the module log), and neither is
    counted as written:

    - a per-field ``ApplySyncableProperties`` raising AttributeError/TypeError;
    - a write flexicon accepted but silently skipped (its ``_apply_props_loop``
      drops object-reference values, unresolvable writing systems and other
      shapes it does not handle without raising). These are detected by
      reading the target back with ``ops.GetSyncableProperties`` after the
      writes and checking that every requested value is present. When `ops`
      has no getter, or the read-back raises, the writes are reported as
      unverified rather than assumed good.

    Args:
        src_props: dict returned by GetSyncableProperties on the source object.
        tgt_props: dict returned by GetSyncableProperties on the target object.
        ops: the Operations instance (must expose ApplySyncableProperties).
        tgt_obj: the target LCM object to write to.
        ws_map: optional {source_ws_id: target_ws_id} dict forwarded to
            ApplySyncableProperties so multilingual values under a source WS Id
            the target lacks are remapped instead of silently dropped.
        report_sink: optional sink with ``Warning(str)``; when None the
            warnings go to the module log only.
        label: prefix for the warning lines (e.g. ``"[pos] guid=1234abcd"``).

    Returns:
        int: number of fields written AND confirmed on read-back (or written
        and unverifiable). 0 if nothing needed writing.
    """
    def _warn(msg):
        line = ("  %s %s" % (label, msg)) if label else ("  " + msg)
        _log.warning("apply_update_semantic: %s", line.strip())
        if report_sink is not None:
            report_sink.Warning(line)

    attempted = {}
    for key, (value, _tgt_val) in compute_merge_fillable(
        src_props, tgt_props, ws_map=ws_map
    ).items():
        try:
            ops.ApplySyncableProperties(tgt_obj, {key: value}, ws_map=ws_map)
        except (AttributeError, TypeError) as exc:
            _warn("MERGE partial apply: field %r NOT written (%s: %s)"
                  % (key, type(exc).__name__, exc))
            continue
        attempted[key] = value
    if not attempted:
        return 0

    getter = getattr(ops, "GetSyncableProperties", None)
    if getter is None:
        return len(attempted)  # nothing to verify against (test doubles)
    try:
        readback = getter(tgt_obj)
    except Exception as exc:  # noqa: BLE001 -- LCM/COM failures are wide
        _warn("MERGE read-back failed (%s: %s); %d field write(s) unverified"
              % (type(exc).__name__, exc, len(attempted)))
        return len(attempted)
    if not isinstance(readback, dict):
        return len(attempted)

    written = 0
    for key, value in attempted.items():
        problem = _unapplied_parts(key, value, readback, ws_map=ws_map)
        if problem:
            _warn("MERGE partial apply: field %r not applied -- requested "
                  "value not present on read-back after ApplySyncableProperties"
                  " (%s)" % (key, problem))
        else:
            written += 1
    return written


# ============================================================================
# 022 T014: Flexicon version gate for Phoneme/Environment field-diff promotion
# ============================================================================

# First pyflexicon release whose PhonemeOperations / EnvironmentOperations
# GetSyncableProperties no longer call ``.get_String()`` on the scalar
# ITsString fields (``BasicIPASymbol``, ``StringRepresentation``), AND whose
# write half round-trips them: flexicon commit 1f9f747b ("guard mono ITsString
# vs multi-string in Phoneme/Environment GetSyncableProperties"), first tagged
# v4.1.2 (absent from v4.1.1).  That same commit added
# ``PhonemeOperations.__ApplyBasicIPASymbol`` (scalar-tolerant setter); the
# Environment write rides ``BaseOperations``' ITsString ``MakeString``
# fallback for a plain-str value, present at v4.1.2.  Issue #16 / Ruling Y.
#
# The pyproject floor (pyflexicon>=4.8.0) is already above this, so on any
# supported install the gate is open; it stays as a fail-closed guard against
# an out-of-floor or metadata-less install rather than moving the floor.
_FLEXICON_ITSTRING_FIX_VERSION = "4.1.2"


def _phoneme_env_field_diff_enabled() -> bool:
    """Return True if the installed pyflexicon version supports
    GetSyncableProperties on Phoneme and PH_ENVIRONMENT objects without
    the ITsString.get_String defect (022 T014 / Ruling Y, issue #16).

    At or above _FLEXICON_ITSTRING_FIX_VERSION, Phoneme and PH_ENVIRONMENT
    get full field-diff UPDATE (Tier A).  Below it -- or when the installed
    version cannot be read -- they stay SELECTOR-ONLY (Tier C).
    """
    try:
        import importlib.metadata as _meta
        installed = _meta.version("pyflexicon")
        from packaging.version import Version
        return Version(installed) >= Version(_FLEXICON_ITSTRING_FIX_VERSION)
    except Exception:
        return False  # fail-closed: stay SELECTOR-ONLY if version unreadable
