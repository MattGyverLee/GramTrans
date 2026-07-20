"""Writing-system mapping validation (T036, spec.md FR-011 / Clarification Q3).

Pure-Python validation: given a set of source WS IDs (with kind) that the
current Selection requires, and a user-supplied `WSMapping`, decide whether
the mapping is complete and 1:1.

Mapping materialization into the target (creating WSs flagged
`create_in_target=True`) is implemented at runtime in `Lib/transfer.py`'s
pre-step; this module is the read-only validator and stays import-safe
without flexicon / pythonnet.
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

if __package__:
    from .models import WSKind, WSMapping
else:
    from models import WSKind, WSMapping


# ============================================================================
# Exceptions
# ============================================================================

class WSMappingError(Exception):
    """Base class for WS-mapping errors surfaced by `validate`."""


class WSMappingIncomplete(WSMappingError):
    """Raised when the user-provided WSMapping doesn't cover every required
    source writing system. The missing set is exposed via the `.missing`
    attribute as a frozenset of (source_ws_id, WSKind) pairs."""

    def __init__(self, missing: FrozenSet[Tuple[str, WSKind]]) -> None:
        self.missing = missing
        formatted = ", ".join(
            f"{ws_id!r} ({kind.value})" for ws_id, kind in sorted(missing, key=lambda x: x[0])
        )
        super().__init__(f"WS mapping incomplete: missing {formatted}")


class WSMappingOverspecified(WSMappingError):
    """Raised when the user-provided WSMapping carries entries for WSs that
    the current Selection doesn't reference. Not a hard error in production
    (the extras are simply ignored), but tests use it to verify the WSs the
    user is asked to map are exactly the ones actually needed."""

    def __init__(self, extras: FrozenSet[Tuple[str, WSKind]]) -> None:
        self.extras = extras
        super().__init__(f"WS mapping overspecified: extras {sorted(extras)}")


# ============================================================================
# Public API
# ============================================================================

def required_ws_set(pairs: Iterable[Tuple[str, WSKind]]) -> FrozenSet[Tuple[str, WSKind]]:
    """Build a frozenset of (source_ws_id, kind) pairs from an arbitrary
    iterable. Caller is the closure walker — it asks each selected piece for
    its `required_writing_systems()` and feeds the union here.
    """
    return frozenset(pairs)


def to_ws_map_dict(ws_mapping) -> dict:
    """Flatten a `WSMapping` into the ``{source_ws_id: target_ws_id}`` dict that
    flexicon's ``BaseOperations.ApplySyncableProperties(item, props, ws_map=...)``
    expects.

    ApplySyncableProperties applies each multilingual value under the target WS
    whose Id equals the *mapped* source Id (identity when no mapping), and
    SILENTLY SKIPS any value whose mapped target WS Id is absent from the target
    project. So a source vernacular Id (e.g. ``mgz``) that has no counterpart in
    the target is dropped and the field lands empty — unless a mapping entry
    routes it to a target WS that exists (e.g. ``mgz`` -> ``etu``). This helper
    produces that dict once so the execute layer can pass it to every
    ApplySyncableProperties call.

    Returns ``{}`` for a None / empty mapping (identity behavior downstream).
    """
    if ws_mapping is None:
        return {}
    entries = getattr(ws_mapping, "entries", None) or ()
    return {e.source_ws_id: e.target_ws_id for e in entries if e.target_ws_id}


def validate(ws_mapping: WSMapping,
             required: FrozenSet[Tuple[str, WSKind]],
             *, strict_overspec: bool = False) -> None:
    """Verify that `ws_mapping` covers every (source_ws_id, kind) pair in
    `required`. Raises `WSMappingIncomplete` listing the missing entries
    otherwise.

    If `strict_overspec=True`, also raise `WSMappingOverspecified` when the
    mapping carries entries the Selection doesn't reference. Default is
    permissive — production runs ignore extras (the user may have mapped
    extra WSs in anticipation of future selections).
    """
    provided = frozenset(
        (e.source_ws_id, e.source_ws_kind) for e in ws_mapping.entries
    )
    missing = required - provided
    if missing:
        raise WSMappingIncomplete(missing)
    if strict_overspec:
        extras = provided - required
        if extras:
            raise WSMappingOverspecified(extras)


def is_complete(ws_mapping: WSMapping,
                required: FrozenSet[Tuple[str, WSKind]]) -> bool:
    """Predicate form of `validate` — True iff `ws_mapping` covers every
    required pair. Use this in UI gating (Move button stays disabled until
    the WS mapping is complete)."""
    try:
        validate(ws_mapping, required, strict_overspec=False)
        return True
    except WSMappingIncomplete:
        return False


# ============================================================================
# Phase 2 (US2 / FR-209..212) -- writing-system mismatch wizard support
# ============================================================================

from typing import Protocol

if __package__:
    from .models import WSMismatch
else:
    from models import WSMismatch


class WSResolver(Protocol):
    """Phase 2 -- the interactive WS wizard's contract.

    Production: PyQt `Lib/ui/ws_wizard.py.WSWizard` (deferred).
    Tests: FakeWSResolver in tests/unit/conftest.py.
    """

    def resolve(self, mismatches):
        """Block until the user has resolved every mismatch.

        Args:
            mismatches: tuple[WSMismatch, ...].

        Returns:
            tuple[WSMappingChoice, ...] of the same length and order.

        Raises:
            UserCancelled: if the user dismisses the wizard.
        """
        ...


def _enumerate_ws(project):
    """Return tuple of WS descriptor dicts {id, kind, handle} for a
    flexicon project.  Tolerates several accessor shapes; uses
    WritingSystems.GetAll() per the flexicon API."""
    if project is None:
        return ()
    out = []
    ws_ops = getattr(project, "WritingSystems", None)
    if ws_ops is None:
        return ()
    try:
        ws_defs = list(ws_ops.GetAll())
    except (AttributeError, TypeError):
        return ()
    # WS kind classification. The live WS descriptor
    # (CoreWritingSystemDefinition) exposes NO ``IsVernacular`` attribute, so the
    # legacy per-descriptor probe silently defaulted EVERY WS to VERNACULAR
    # (live-confirmed: analysis WS like ``en``/``es`` were mis-tagged vernacular,
    # corrupting primary-vernacular detection and the related-language defaults).
    # Prefer the project's own vernacular membership
    # (``WritingSystems.GetVernacular()``); a WS in that set is VERNACULAR,
    # everything else ANALYSIS (dual-role WSs resolve to VERNACULAR, the correct
    # precedence for primary-vernacular logic). Fall back to the legacy
    # ``IsVernacular`` probe only when GetVernacular is unavailable/empty -- the
    # host-free unit-test fakes expose IsVernacular but not GetVernacular.
    vern_ids = None
    getv = getattr(ws_ops, "GetVernacular", None)
    if callable(getv):
        try:
            vern_ids = {
                str(getattr(w, "Id", None) or getattr(w, "id", ""))
                for w in getv()
            }
            vern_ids.discard("")
        except (AttributeError, TypeError):
            vern_ids = None
    for wd in ws_defs:
        try:
            ws_id = wd.Id
        except AttributeError:
            ws_id = getattr(wd, "id", None) or ""
        try:
            handle = wd.Handle
        except AttributeError:
            handle = getattr(wd, "handle", None)
        if vern_ids:  # authoritative membership from the project
            kind = WSKind.VERNACULAR if str(ws_id) in vern_ids else WSKind.ANALYSIS
        else:
            # Legacy fallback (test fakes / no GetVernacular): probe IsVernacular,
            # default VERNACULAR when even that attribute is absent.
            kind = WSKind.VERNACULAR
            try:
                if not wd.IsVernacular:
                    kind = WSKind.ANALYSIS
            except AttributeError:
                pass
        if ws_id:
            out.append({"id": str(ws_id), "kind": kind, "handle": handle})
    return tuple(out)


def _similarity_rank(source_id: str, candidate_id: str) -> int:
    """Lower rank = better match. Used to sort target_ws_candidates so
    the most likely "did you mean" appears first in the wizard.

    Ranks:
        0: exact (won't show in mismatches but kept for symmetry)
        1: same primary language tag prefix (ko-* vs ko-*)
        2: same first-3 chars (koh-x-Latn ~ koh-Hang)
        3: any other target WS
    """
    if source_id == candidate_id:
        return 0
    s_lang = source_id.split("-", 1)[0]
    c_lang = candidate_id.split("-", 1)[0]
    if s_lang == c_lang:
        return 1
    # Same first 2 chars (ko vs koh, etc.) -- close-enough match.
    if len(s_lang) >= 2 and len(c_lang) >= 2 and s_lang[:2] == c_lang[:2]:
        return 2
    return 3


def detect_ws_mismatches(source, target):
    """T031 / FR-209 -- enumerate every source WS whose Id is NOT in the
    target project's WS list, returning similarity-sorted candidates.

    Args:
        source: flexicon FLExProject (read-only).
        target: flexicon FLExProject (read-only here).

    Returns:
        tuple[WSMismatch, ...] sorted by source_ws_id.  Empty when
        every source WS is already in the target.
    """
    src_ws = _enumerate_ws(source)
    tgt_ws = _enumerate_ws(target)
    tgt_ids = {w["id"] for w in tgt_ws}
    tgt_id_list = [w["id"] for w in tgt_ws]
    out = []
    for sw in src_ws:
        if sw["id"] in tgt_ids:
            continue
        candidates = sorted(
            tgt_id_list, key=lambda c: (_similarity_rank(sw["id"], c), c)
        )
        out.append(WSMismatch(
            source_ws_id=sw["id"],
            source_ws_kind=sw["kind"],
            target_ws_candidates=tuple(candidates),
        ))
    out.sort(key=lambda m: m.source_ws_id)
    return tuple(out)


# ============================================================================
# Feature 032 US4 (FR-012..FR-015) -- related-languages default correspondence
# ============================================================================

def _primary_vernacular(ws_descriptors):
    """Return the descriptor of the primary vernacular WS, or None.

    The primary vernacular is the map anchor (contracts/ws-mapping-default.md):
    the vernacular WS whose Id is the bare base language subtag (no extension,
    e.g. ``eja`` rather than ``eja-fonipa``).  When no vernacular WS is bare,
    fall back to the shortest-Id vernacular (deterministic tie-break by Id).
    Returns None when the side has no vernacular WS at all (FR-015: target
    with no primary vernacular leaves the primary row unresolved).
    """
    vern = [w for w in ws_descriptors if w["kind"] == WSKind.VERNACULAR]
    if not vern:
        return None
    for w in vern:
        if "-" not in w["id"]:
            return w
    return min(vern, key=lambda w: (len(w["id"]), w["id"]))


def _subtag_suffix(ws_id: str, primary_base: str) -> str:
    """Subtag suffix of ``ws_id`` relative to ``primary_base`` (FR-013).

    ``eja-fonipa`` relative to primary base ``eja`` -> ``-fonipa``;
    ``eja`` relative to ``eja`` -> ```` (the primary itself).  When ``ws_id``
    does not extend ``primary_base`` (a differing base language on the same
    side), the suffix is everything after this Id's own base subtag, so that
    ``def-fonipa`` still yields ``-fonipa`` -- which is what lets an ambiguous
    (>1 target sub sharing a suffix) case be detected and left unresolved.
    """
    if ws_id == primary_base:
        return ""
    if ws_id.startswith(primary_base + "-"):
        return ws_id[len(primary_base):]
    parts = ws_id.split("-", 1)
    return "-" + parts[1] if len(parts) > 1 else ""


def default_ws_choices(source, target):
    """FR-012..FR-015 -- pre-fill related-languages WS correspondence.

    Returns a tuple of ``WSMappingChoice`` rows (all ``WSChoice.MAP``, never
    CREATE/SKIP -- FR-014) for the source vernacular WSs that are *not* already
    present in the target by identity and for which a confident target
    correspondence exists:

    * **Primary -> primary** (FR-012): the source primary vernacular defaults to
      the target primary vernacular, even across differing base subtags
      (``eja`` -> ``abc``).
    * **Sub -> sub by suffix** (FR-013): each source sub WS defaults to the
      *unique* target sub WS sharing its subtag suffix relative to each side's
      primary base (``eja-fonipa`` -> ``abc-fonipa`` via shared ``-fonipa``).

    Rows with no confident correspondence -- target has no primary vernacular,
    zero target subs share the suffix, or >1 target sub shares it -- get NO
    choice and are simply omitted (FR-015).  Omitted rows keep
    ``is_complete`` / ``validate`` failing until the user resolves them, so
    confirmation stays gated; the caller seeds these defaults into the mapping
    and the WS wizard collects the remainder.
    """
    if __package__:
        from .models import WSMappingChoice, WSChoice
    else:
        from models import WSMappingChoice, WSChoice
    src_ws = _enumerate_ws(source)
    tgt_ws = _enumerate_ws(target)
    tgt_ids = {w["id"] for w in tgt_ws}

    src_primary = _primary_vernacular(src_ws)
    tgt_primary = _primary_vernacular(tgt_ws)
    src_base = src_primary["id"].split("-", 1)[0] if src_primary else None
    tgt_base = tgt_primary["id"].split("-", 1)[0] if tgt_primary else None

    # Index target vernacular sub WSs by their suffix relative to target base.
    tgt_sub_by_suffix: dict = {}
    if tgt_primary and tgt_base:
        for w in tgt_ws:
            if w["kind"] != WSKind.VERNACULAR or w["id"] == tgt_primary["id"]:
                continue
            tgt_sub_by_suffix.setdefault(
                _subtag_suffix(w["id"], tgt_base), []
            ).append(w["id"])

    choices = []
    for sw in src_ws:
        if sw["id"] in tgt_ids:
            continue  # already present by identity -- not a mismatch
        if sw["kind"] != WSKind.VERNACULAR:
            continue  # analysis defaults are identity-only; no correspondence guess
        if src_primary is None or tgt_primary is None:
            continue  # missing primary vernacular on either side -> unresolved (FR-015)
        if sw["id"] == src_primary["id"]:
            choices.append(WSMappingChoice(
                source_ws_id=sw["id"],
                source_ws_kind=sw["kind"],
                choice=WSChoice.MAP,
                target_ws_id=tgt_primary["id"],
            ))
            continue
        matches = tgt_sub_by_suffix.get(_subtag_suffix(sw["id"], src_base), [])
        if len(matches) == 1:  # unique correspondence only (FR-013); 0 or >1 -> unresolved
            choices.append(WSMappingChoice(
                source_ws_id=sw["id"],
                source_ws_kind=sw["kind"],
                choice=WSChoice.MAP,
                target_ws_id=matches[0],
            ))
    return tuple(choices)


def _primary_of(ws_list):
    """Primary WS of a same-kind list: the bare (no ``-``) tag, else the
    shortest-Id (deterministic tie-break). ``None`` for an empty list.

    Unlike ``_primary_vernacular`` this does NOT filter by kind -- the caller
    passes an already-kind-filtered list, so it works for vernacular OR analysis.
    """
    if not ws_list:
        return None
    for w in ws_list:
        if "-" not in w["id"]:
            return w
    return min(ws_list, key=lambda w: (len(w["id"]), w["id"]))


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _closest_sub(src_suffix: str, tgt_subs):
    """Pick the closest target sub Id for ``src_suffix`` from ``tgt_subs`` (a
    list of ``(target_id, target_suffix)``). Exact-suffix match wins; otherwise
    the longest shared suffix prefix; deterministic tie-break by target Id.
    Returns ``None`` only when ``tgt_subs`` is empty."""
    best = None
    best_key = None
    for tid, tsuf in sorted(tgt_subs, key=lambda t: t[0]):
        key = (tsuf == src_suffix, _common_prefix_len(src_suffix, tsuf))
        if best_key is None or key > best_key:
            best_key, best = key, tid
    return best


def closest_ws_defaults(source, target) -> dict:
    """Best-effort WS correspondence for the selection wizard (user policy).

    Per WS kind (vernacular, then analysis):
      * source **primary** -> target **primary** of the same kind (always, even
        across differing base language subtags, e.g. ``eja`` -> ``abc``);
      * source **variants** are matched **one-to-one** to target variants,
        closest first (exact subtag suffix, then nearest shared suffix), top-down
        -- each target variant is consumed at most once;
      * when the source has **more variants than the target** (or the target has
        none), the leftover source variants are proposed as **new** target WSs
        created **under the target primary's base language subtag** -- the source
        suffix is rebased onto the target base (``eja-x-emic`` -> create
        ``abc-x-emic``), never onto the source base, so a language is not split
        across two base subtags.

    Returns ``{source_ws_id: (choice, target_ws_id)}`` where ``choice`` is
    ``"map"`` (an existing target WS) or ``"create"`` (a new WS to add under the
    target primary base). Identity rows (source Id already present in the target)
    are omitted -- the wizard maps those to themselves directly.
    """
    src_ws = _enumerate_ws(source)
    tgt_ws = _enumerate_ws(target)
    tgt_ids = {w["id"] for w in tgt_ws}
    out: dict = {}
    for kind in (WSKind.VERNACULAR, WSKind.ANALYSIS):
        src_k = [w for w in src_ws if w["kind"] == kind]
        tgt_k = [w for w in tgt_ws if w["kind"] == kind]
        src_primary = _primary_of(src_k)
        tgt_primary = _primary_of(tgt_k)
        if src_primary is None or tgt_primary is None:
            continue
        src_base = src_primary["id"].split("-", 1)[0]
        tgt_base = tgt_primary["id"].split("-", 1)[0]

        # primary -> primary (skip identity; wizard maps it to itself)
        if src_primary["id"] not in tgt_ids:
            out[src_primary["id"]] = ("map", tgt_primary["id"])

        # source variants (top-down order), excluding the primary and any that
        # already exist identically in the target.
        src_vars = [
            (w["id"], _subtag_suffix(w["id"], src_base))
            for w in src_k
            if w["id"] != src_primary["id"] and w["id"] not in tgt_ids
        ]
        # available target variants (consumed one-to-one below).
        avail = [
            (w["id"], _subtag_suffix(w["id"], tgt_base))
            for w in tgt_k
            if w["id"] != tgt_primary["id"]
        ]
        used: set = set()

        # Pass 1: exact-suffix matches, one-to-one.
        for sid, suf in src_vars:
            if sid in out:
                continue
            for tid, tsuf in avail:
                if tid not in used and tsuf == suf:
                    out[sid] = ("map", tid)
                    used.add(tid)
                    break

        # Pass 2: closest remaining target variant, one-to-one, top-down.
        for sid, suf in src_vars:
            if sid in out:
                continue
            remaining = [(tid, tsuf) for tid, tsuf in avail if tid not in used]
            if not remaining:
                break
            best = _closest_sub(suf, remaining)
            out[sid] = ("map", best)
            used.add(best)

        # Pass 3: leftovers -> CREATE under the target primary base (rebase the
        # source suffix onto tgt_base; never split the language onto src_base).
        for sid, suf in src_vars:
            if sid in out:
                continue
            proposed = (tgt_base + suf) if suf else tgt_base
            # If the rebased tag already exists in the target, map to it rather
            # than propose a duplicate create.
            out[sid] = ("map", proposed) if proposed in tgt_ids else ("create", proposed)
    return out


def fold_choices_into_ws_mapping(choices, base_mapping):
    """T036 / FR-210 -- convert WSMappingChoice tuple into WSMappingEntry
    rows and merge into `base_mapping`.

    Per FR-211, SKIP choices are NOT folded into the WSMapping (they have
    no target_ws_id).  Callers must thread the original choice tuple
    through Selection.ws_mapping_choices so the planner can detect SKIP
    and emit Skip(UNMAPPED_WS_USER_CHOSE_SKIP).

    Per FR-212, CREATE choices assume the new WS has ALREADY been created
    in the target before this function is called.  An identity mapping
    (source_id -> source_id) is registered with create_in_target=True
    for audit.
    """
    if __package__:
        from .models import WSMappingEntry, WSChoice
    else:
        from models import WSMappingEntry, WSChoice
    existing = list(base_mapping.entries) if base_mapping is not None else []
    seen = {(e.source_ws_id, e.source_ws_kind) for e in existing}
    for c in choices:
        key = (c.source_ws_id, c.source_ws_kind)
        if key in seen:
            continue
        if c.choice == WSChoice.MAP:
            existing.append(WSMappingEntry(
                source_ws_id=c.source_ws_id,
                source_ws_kind=c.source_ws_kind,
                target_ws_id=c.target_ws_id,
                create_in_target=False,
            ))
            seen.add(key)
        elif c.choice == WSChoice.CREATE:
            existing.append(WSMappingEntry(
                source_ws_id=c.source_ws_id,
                source_ws_kind=c.source_ws_kind,
                target_ws_id=c.source_ws_id,
                create_in_target=True,
            ))
            seen.add(key)
        # WSChoice.SKIP intentionally not folded.
    return WSMapping(entries=tuple(existing))
