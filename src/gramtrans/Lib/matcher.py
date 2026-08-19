"""Phase 1 match-by-GUID-first / fingerprint-fallback lookup.

Pure-Python module. No LCM / flexicon imports at module level; all LCM
surface is injected by the caller (target project handle, source object,
fingerprint functions) so this module is fully testable without an LCM host.

Public surface
--------------
Match              frozen dataclass returned by lookup_target()
lookup_target()    FR-102 / FR-103 / FR-104 three-step matcher
FINGERPRINT_FNS    per-category registry: GrammarCategory -> callable
fingerprint_for_msa(msa, ws_handle=None) -> Tuple
fingerprint_for_allomorph(allo, ws_handle=None) -> Tuple

Feature 038 (FR-003, research.md R1) natural-key roster surface:

NATURAL_KEY_ROSTER_PATH             default location of 035's roster file
NaturalKeyRosterHarnessError        raised by require_natural_key_roster_entry()
natural_key_roster_entry_for(cls)   THE single roster accessor; None == no basis
require_natural_key_roster_entry(cls)   enforcement gate for the matching step
reset_natural_key_roster_cache()    test hook; also re-points the roster path

Fingerprint definitions per FR-104.

lookup_target() contract
------------------------
The caller passes both the *source* object (so the source fingerprint can be
computed) and the *target* project handle (so target objects can be iterated).
Step 3 computes the source fingerprint once, then iterates target objects in the
same category computing each one's fingerprint; first equality wins.

Target project protocol (duck-typed, no import required)
---------------------------------------------------------
The `target` argument must expose at least one of:

    target.get_object_by_guid(guid: str, category: GrammarCategory) -> obj | None
        O(1) indexed lookup. Preferred when available.

    target.iter_objects(category: GrammarCategory) -> Iterable[obj]
        Linear scan fallback. Each `obj` must have a `.Guid` attribute whose
        str() gives the GUID string.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

_log = logging.getLogger(__name__)

if __package__:
    from .models import GrammarCategory, NaturalKeyRosterEntry
else:
    # loaded via site.addsitedir("Lib")
    from models import GrammarCategory, NaturalKeyRosterEntry


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Match:
    """Result of a lookup_target() call.

    Attributes:
        source_guid:     GUID of the source object being matched.
        target_obj:      The LCM object found in the target, or None when
                         via == "none".
        via:             Which path produced the match:
                           "guid"           - direct GUID lookup
                           "identity_remap" - hit via prior-run remap dict
                           "fingerprint"    - hit via per-category fingerprint
                           "none"           - no match; item is an Add
        fingerprint_key: Computed fingerprint tuple when via=="fingerprint";
                         None otherwise.
    """
    source_guid: str
    target_obj: object  # LCM object or None
    via: str            # "guid" | "identity_remap" | "fingerprint" | "none"
    fingerprint_key: Optional[Tuple] = None

    _VALID_VIA = frozenset({"guid", "identity_remap", "fingerprint", "none"})

    def __post_init__(self) -> None:
        if self.via not in self._VALID_VIA:
            raise ValueError(
                f"Match.via must be one of {self._VALID_VIA!r}, got {self.via!r}"
            )
        if self.via == "none" and self.target_obj is not None:
            raise ValueError("Match.via='none' requires target_obj=None")
        if self.via != "fingerprint" and self.fingerprint_key is not None:
            raise ValueError(
                "fingerprint_key must be None when via != 'fingerprint'"
            )
        if self.via == "fingerprint" and self.fingerprint_key is None:
            raise ValueError(
                "fingerprint_key must be set when via == 'fingerprint'"
            )


# ---------------------------------------------------------------------------
# Fingerprint functions (FR-104)
# ---------------------------------------------------------------------------

def fingerprint_for_msa(msa, ws_handle=None) -> Tuple:
    """Fingerprint for IMoInflAffMsa (FR-104).

    Returns:
        (GrammarCategory.MSA,
         owner_entry_guid: str,
         "MoInflAffMsa",
         pos_guid: str,
         frozenset(slot_guids))

    owner_entry_guid: GUID string of the owning ILexEntry, "" if unavailable.
    pos_guid:         GUID string of PartOfSpeechRA, "" if unset.
    slot_guids:       frozenset of GUID strings from SlotsRC.

    ws_handle is accepted for API symmetry but not used; MSA identity is
    language-independent.
    """
    try:
        if msa.Owner is not None:
            owner_class = type(msa.Owner).__name__
            if owner_class not in ("LexEntry", "ILexEntry"):
                _log.warning(
                    "fingerprint_for_msa: .Owner is %s (expected LexEntry), "
                    "msa GUID=%s; fingerprint owner_guid may be wrong. "
                    "Affix MSA path is unverified -- check ownership.",
                    owner_class,
                    getattr(msa, "Guid", "?"),
                )
                owner_guid = str(getattr(msa.Owner, "Guid", "") or "")
            else:
                owner_guid = str(msa.Owner.Guid)
        else:
            owner_guid = ""
    except AttributeError:
        owner_guid = ""

    try:
        pos_guid = (
            str(msa.PartOfSpeechRA.Guid)
            if msa.PartOfSpeechRA is not None
            else ""
        )
    except AttributeError:
        pos_guid = ""

    try:
        # ILcmReferenceCollection: iterate directly, never use ElementAt()
        slot_guids = frozenset(str(sl.Guid) for sl in msa.SlotsRC)
    except (AttributeError, TypeError):
        slot_guids = frozenset()

    return (GrammarCategory.MSA, owner_guid, "MoInflAffMsa", pos_guid, slot_guids)


def fingerprint_for_allomorph(allo, ws_handle=None) -> Tuple:
    """Fingerprint for IMoAffixAllomorph (FR-104).

    Returns:
        (GrammarCategory.ALLOMORPH,
         owner_entry_guid: str,
         lexeme_form_text: str,
         morph_type_guid: str)

    lexeme_form_text: the string of allo.Form for ws_handle, or "" if
                      ws_handle is None or the Form is unreadable.
    morph_type_guid:  GUID string of MorphTypeRA, "" if unset.

    ws_handle should be the default-vernacular writing-system handle for best
    match quality; passing None degrades fingerprint precision to
    (owner, "", morphtype), which may cause false negatives on entries with
    multiple allomorphs of the same morphtype.
    """
    try:
        if allo.Owner is not None:
            owner_class = type(allo.Owner).__name__
            if owner_class not in ("LexEntry", "ILexEntry"):
                _log.warning(
                    "fingerprint_for_allomorph: .Owner is %s (expected LexEntry), "
                    "allo GUID=%s; fingerprint owner_guid may be wrong. "
                    "Affix allomorph path is unverified -- check ownership.",
                    owner_class,
                    getattr(allo, "Guid", "?"),
                )
                owner_guid = str(getattr(allo.Owner, "Guid", "") or "")
            else:
                owner_guid = str(allo.Owner.Guid)
        else:
            owner_guid = ""
    except AttributeError:
        owner_guid = ""

    lexeme_form_text = ""
    if ws_handle is not None:
        try:
            ts_string = allo.Form.get_String(ws_handle)
            lexeme_form_text = ts_string.Text or ""
        except (AttributeError, TypeError):
            lexeme_form_text = ""

    try:
        morph_type_guid = (
            str(allo.MorphTypeRA.Guid) if allo.MorphTypeRA is not None else ""
        )
    except AttributeError:
        morph_type_guid = ""

    return (GrammarCategory.ALLOMORPH, owner_guid, lexeme_form_text, morph_type_guid)


def fingerprint_with_owner(fn, obj, owner_guid_override, ws_handle=None):
    """Return the fingerprint produced by fn(obj, ws_handle) with tuple
    index 1 (owner_guid) replaced by owner_guid_override.

    Used by the merge-into planner path to evaluate source fingerprints
    against a resolved target entry (different GUID than the source entry),
    so that fingerprint matching correctly identifies already-present
    children under the resolved target.

    NOTE: If .Owner is not an ILexEntry, fingerprint_for_msa / fingerprint_for_allomorph
    will return "" for owner_guid. Callers must supply a valid owner_guid_override in
    that case. Any unexpected ownership will be logged by the caller (S2 residual risk).
    """
    fp = fn(obj, ws_handle)
    return (fp[0], owner_guid_override) + fp[2:]


# ---------------------------------------------------------------------------
# Per-category fingerprint registry (FR-104)
# ---------------------------------------------------------------------------

FINGERPRINT_FNS: Dict[GrammarCategory, Callable] = {
    GrammarCategory.MSA: fingerprint_for_msa,
    GrammarCategory.ALLOMORPH: fingerprint_for_allomorph,
    # POS, SLOTS, AFFIX_TEMPLATES, INFLECTION_FEATURES fingerprints (FR-104 table)
    # will be added here as Phase 1 category planners are implemented.
    # Each entry is (obj, ws_handle=None) -> hashable tuple.
}


# ---------------------------------------------------------------------------
# Natural-key identity roster (feature 038 FR-003 / research.md R1)
# ---------------------------------------------------------------------------
#
# FR-003 admits a class to the NATURAL-KEY match basis "by enumeration on the
# roster only". The roster file is owned by feature 035; this module only READS
# it, through the single accessor below. Nothing here may hard-code a natural
# key or a class name: the file is the one source of truth, so a class is
# admitted exactly when 035's file says so and never because engine code
# happened to know a key for it.
#
# WHY AN ABSENT CLASS IS NOT AN ERROR (R1). 035 has not yet appended 038's six
# proposed entries (that append is 035's own task, not this feature's), and the
# rows in the file today predate the executable `key_fn_id` / `scope_fn_id`
# fields `NaturalKeyRosterEntry` requires. Both conditions therefore hold right
# now for every class: nothing projects, so nothing has a natural-key basis, so
# the engine degrades to the GUID-only behaviour it had before 038 -- which is
# exactly how 038 lands green ahead of 035's append, and how it will start
# matching on the day that append happens with NO code change here.

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(
    os.path.join(_LIB_DIR, os.pardir, os.pardir, os.pardir)
)

#: Default location of 035's roster. Resolved relative to this module so any
#: checkout path works. A FlexTools deployment that ships only ``Lib/`` has no
#: ``specs/`` tree at all; see ``_load_natural_key_roster`` for why that is a
#: degradation rather than a crash.
NATURAL_KEY_ROSTER_PATH = os.path.join(
    _REPO_ROOT,
    "specs", "035-fullsweep-fidelity", "contracts",
    "natural-key-identity-roster.json",
)

# Module-level cache. None == "not loaded yet"; an empty dict is a legitimate
# loaded state (no class has a natural-key basis) and must not trigger a reload.
_ROSTER_CACHE = None          # type: Optional[Dict[str, NaturalKeyRosterEntry]]
_ROSTER_PATH_OVERRIDE = None  # type: Optional[str]


class NaturalKeyRosterHarnessError(RuntimeError):
    """Raised when a class that is NOT on the roster reaches the natural-key
    matching step (035 ``enforcement.firing_for_a_class_not_on_this_roster``,
    038 FR-003).

    This is a harness error, never a run-time fallback: reaching the
    natural-key step means the caller has already decided to match by key, and
    doing that for an unadmitted class is precisely the fabricated
    correspondence FR-185 / FR-186 exist to forbid. The message always names
    the offending class.
    """


def reset_natural_key_roster_cache(roster_path: Optional[str] = None) -> None:
    """Drop the cached roster; optionally re-point where it is read from.

    Parameters:
        roster_path: When given, subsequent loads read this path instead of
                     ``NATURAL_KEY_ROSTER_PATH``. Pass None (the default) to
                     clear both the cache and any previous override, restoring
                     the real file.

    Exists for tests -- a module-level cache that cannot be reset makes the
    missing-file and malformed-file degradations untestable, and those two
    paths are the ones that must never crash a live transfer run.
    """
    global _ROSTER_CACHE, _ROSTER_PATH_OVERRIDE
    _ROSTER_CACHE = None
    _ROSTER_PATH_OVERRIDE = roster_path


def natural_key_roster_entry_for(
    object_class: str,
) -> Optional[NaturalKeyRosterEntry]:
    """THE roster accessor (038 FR-003, research.md R1). Single point of read.

    Parameters:
        object_class: LCM class name as the roster spells it, e.g. "PhPhoneme".

    Returns:
        The projected ``NaturalKeyRosterEntry`` when the class is admitted to
        the natural-key basis, or **None** meaning "no natural-key basis for
        this class".

    ``None`` is a NORMAL, EXPECTED, NON-ERROR return. The caller answers it by
    degrading to GUID-only (identity) matching for that class -- the pre-038
    behaviour -- and must not raise, must not warn per item, and must not
    invent a key. It is the answer to the question "MAY I use a natural key
    for this class?".

    The different question "I am ABOUT to natural-key match this class" is
    answered by ``require_natural_key_roster_entry``, which raises. Do not
    conflate the two: only the second is a contract violation.
    """
    return _natural_key_roster().get(object_class)


def require_natural_key_roster_entry(
    object_class: str,
) -> NaturalKeyRosterEntry:
    """Return the roster entry for a class that has REACHED the natural-key
    matching step, raising if that class is not admitted.

    Raises:
        NaturalKeyRosterHarnessError: naming ``object_class``, when the class
            has no roster entry. An off-roster class arriving here is a harness
            defect in the caller (it should have consulted
            ``natural_key_roster_entry_for`` and degraded to GUID-only), not a
            data condition to be tolerated, so it fails loudly rather than
            matching on an unadmitted key.
    """
    entry = natural_key_roster_entry_for(object_class)
    if entry is None:
        raise NaturalKeyRosterHarnessError(
            "natural-key matching was attempted for object class "
            + repr(object_class) + ", which is NOT admitted to the "
            "natural-key identity roster (" + NATURAL_KEY_ROSTER_PATH + "). "
            "Admission is by enumeration on that roster only (038 FR-003 / "
            "035 FR-185); a class absent from it must degrade to GUID-only "
            "matching, which the caller detects as "
            "natural_key_roster_entry_for(" + repr(object_class) + ") is None."
        )
    return entry


def _natural_key_roster() -> Dict[str, NaturalKeyRosterEntry]:
    """Return the cached class-name -> entry map, loading it on first use."""
    global _ROSTER_CACHE
    if _ROSTER_CACHE is None:
        path = _ROSTER_PATH_OVERRIDE or NATURAL_KEY_ROSTER_PATH
        _ROSTER_CACHE = _load_natural_key_roster(path)
    return _ROSTER_CACHE


def _load_natural_key_roster(path: str) -> Dict[str, NaturalKeyRosterEntry]:
    """Parse the roster file into a class-name -> entry map.

    Every failure mode degrades to an EMPTY roster plus one warning, never an
    exception:

    * missing file -- this module also runs from a FlexTools deployment that
      ships ``Lib/`` without the ``specs/`` tree, and from a checkout made
      before 035 landed the file. Crashing the engine because a planning
      artefact is absent would turn a "no natural-key basis" degradation into
      a total transfer failure, which is strictly worse than the pre-038
      behaviour it would be replacing.
    * malformed JSON -- same reasoning: an unreadable roster admits nobody,
      and "admits nobody" is the safe state (GUID-only matching). A
      half-parsed roster that admitted SOME classes would be the dangerous
      state.

    An individual entry that cannot be projected is skipped and counted in the
    summary line; it does not poison the entries beside it.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (IOError, OSError):
        _log.warning(
            "natural-key roster not found at %s -- no class has a natural-key "
            "basis; matching degrades to GUID-only (038 FR-003 / R1)", path,
        )
        return {}
    except ValueError as exc:  # json.JSONDecodeError subclasses ValueError
        _log.warning(
            "natural-key roster at %s is not valid JSON (%s) -- no class has "
            "a natural-key basis; matching degrades to GUID-only", path, exc,
        )
        return {}

    entries = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        _log.warning(
            "natural-key roster at %s carries no 'entries' list -- no class "
            "has a natural-key basis; matching degrades to GUID-only", path,
        )
        return {}

    roster = {}  # type: Dict[str, NaturalKeyRosterEntry]
    skipped = 0
    for raw_entry in entries:
        entry = _project_roster_entry(raw_entry)
        if entry is None:
            skipped += 1
            continue
        roster[entry.object_class] = entry

    _log.info(
        "natural-key roster %s: %d of %d entries projected; %d not yet "
        "executable (no key_fn_id) and therefore carrying no natural-key "
        "basis", path, len(roster), len(entries), skipped,
    )
    return roster


def _project_roster_entry(raw_entry) -> Optional[NaturalKeyRosterEntry]:
    """Project one roster ``entries[]`` object to a ``NaturalKeyRosterEntry``.

    Returns None -- "this class has no natural-key basis" -- for any row that
    cannot be projected, which today is EVERY row: the file spells the class
    name ``class`` (accepted here alongside ``object_class``) and carries none
    of 038's executable ``key_fn_id`` / ``scope_fn_id`` fields, so
    ``NaturalKeyRosterEntry``'s non-empty ``key_fn_id`` invariant rejects it.
    That is deliberate and is R1's whole point: a declarative row nobody can
    execute must not be treated as an admission. NEVER fill ``key_fn_id`` in
    with a guess here -- inventing one would fabricate an admission the roster
    never granted.
    """
    if not isinstance(raw_entry, dict):
        return None
    object_class = raw_entry.get("object_class") or raw_entry.get("class")
    try:
        return NaturalKeyRosterEntry(
            object_class=object_class,
            natural_key=raw_entry.get("natural_key"),
            key_unique_by_construction=bool(
                raw_entry.get("key_unique_by_construction")
            ),
            on_ambiguous_key=raw_entry.get("on_ambiguous_key"),
            reason=raw_entry.get("reason"),
            key_fn_id=raw_entry.get("key_fn_id"),
            key_scoping_note=_as_optional_text(
                raw_entry.get("key_scoping_note")
            ),
            uniqueness_caveat=_as_optional_text(
                raw_entry.get("uniqueness_caveat")
            ),
            live_confirmation=(
                raw_entry.get("live_confirmation")
                if isinstance(raw_entry.get("live_confirmation"), dict)
                else None
            ),
            scope_fn_id=raw_entry.get("scope_fn_id"),
        )
    except (ValueError, TypeError) as exc:
        _log.debug(
            "natural-key roster entry for %r is not projectable (%s) -- no "
            "natural-key basis for that class", object_class, exc,
        )
        return None


def _as_optional_text(value) -> Optional[str]:
    """Coerce a roster field the model types as ``Optional[str]`` but the file
    may spell as a nested object (035 writes ``uniqueness_caveat`` as a dict).

    A stable JSON rendering keeps the evidence readable in a report without
    letting a shape difference alone reject an otherwise-valid entry.
    """
    if value is None or isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Main lookup entry point
# ---------------------------------------------------------------------------

def lookup_target(
    source_guid: str,
    category: GrammarCategory,
    target,
    *,
    source_obj=None,
    identity_remap: Optional[Dict[str, str]] = None,
    fingerprint_fn: Optional[Callable] = None,
) -> Match:
    """Look up the target object that matches source_guid (FR-102/103/104).

    Three-step fallback:

    1. Direct GUID match (FR-102):
       Queries the target for an object whose GUID == source_guid.
       Most LCM classes preserve source GUIDs via factory.Create(Guid, owner),
       so this is the dominant path for POS / Template / Slot / LexEntry /
       LexSense / PhEnvironment.

    2. identity_remap lookup (FR-103):
       Looks up source_guid in identity_remap (dict[str, str] from a prior
       Phase 0 RunReport: source_guid -> target_guid). Used for IMoInflAffMsa
       and IMoAffixAllomorph, whose LCM factories do not accept a GUID override
       so Phase 0 recorded the remapping explicitly.

    3. Fingerprint match (FR-104):
       Computes source_obj's fingerprint via fingerprint_fn (or the registry
       entry for category), then iterates all target objects in that category
       comparing fingerprints. First equality wins.
       Requires source_obj to be passed; skipped if source_obj is None and no
       fingerprint_fn is resolvable.

    Parameters:
        source_guid:    GUID string of the source LCM object.
        category:       GrammarCategory enum member.
        target:         Target project handle (duck-typed; see module docstring).
        source_obj:     The source LCM object. Required for step 3. Optional for
                        steps 1 and 2.
        identity_remap: Optional dict[str, str] (source GUID -> target GUID)
                        from a prior RunReport. Pass None when unavailable.
        fingerprint_fn: Optional (obj, ws_handle=None) -> tuple callable.
                        If None and source_obj is not None, FINGERPRINT_FNS is
                        consulted. If the category has no registered fingerprint
                        function, step 3 is skipped.

    Returns:
        Match(.via in {"guid", "identity_remap", "fingerprint", "none"}).
    """
    # ------------------------------------------------------------------
    # Step 1: Direct GUID match (FR-102)
    # ------------------------------------------------------------------
    obj = _find_by_guid(target, source_guid, category)
    if obj is not None:
        return Match(source_guid=source_guid, target_obj=obj, via="guid")

    # ------------------------------------------------------------------
    # Step 2: identity_remap (FR-103)
    # ------------------------------------------------------------------
    if identity_remap:
        remapped_guid = identity_remap.get(source_guid)
        if remapped_guid:
            obj = _find_by_guid(target, remapped_guid, category)
            if obj is not None:
                return Match(
                    source_guid=source_guid,
                    target_obj=obj,
                    via="identity_remap",
                )

    # ------------------------------------------------------------------
    # Step 3: Fingerprint (FR-104)
    # ------------------------------------------------------------------
    fn = fingerprint_fn or FINGERPRINT_FNS.get(category)
    if fn is not None and source_obj is not None:
        try:
            source_fp = fn(source_obj)
        except Exception:  # noqa: BLE001
            source_fp = None

        if source_fp is not None:
            result = _find_by_fingerprint(target, category, fn, source_fp)
            if result is not None:
                target_obj, fp_key = result
                return Match(
                    source_guid=source_guid,
                    target_obj=target_obj,
                    via="fingerprint",
                    fingerprint_key=fp_key,
                )

    # ------------------------------------------------------------------
    # No match — treat as Add
    # ------------------------------------------------------------------
    return Match(source_guid=source_guid, target_obj=None, via="none")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_by_guid(target, guid: str, category: GrammarCategory):
    """Return the target object whose str(Guid) == guid, or None.

    Tries target.get_object_by_guid(guid, category) first (O(1) if the
    target implements an index), then falls back to target.iter_objects(
    category) with a linear scan.
    """
    getter = getattr(target, "get_object_by_guid", None)
    if callable(getter):
        return getter(guid, category)

    iterator = getattr(target, "iter_objects", None)
    if callable(iterator):
        for obj in iterator(category):
            try:
                if str(obj.Guid) == guid:
                    return obj
            except AttributeError:
                continue

    return None


def _find_by_fingerprint(
    target,
    category: GrammarCategory,
    fp_fn: Callable,
    source_fp: Tuple,
) -> Optional[Tuple[object, Tuple]]:
    """Iterate target objects in category and return (obj, fp_key) for the
    first object whose fingerprint equals source_fp, or None.

    Gracefully skips any object for which fp_fn raises (FR-018 no-silent-drop
    principle: skip the individual comparison, not the whole search).
    """
    iterator = getattr(target, "iter_objects", None)
    if not callable(iterator):
        return None

    for obj in iterator(category):
        try:
            fp_key = fp_fn(obj)
        except Exception:  # noqa: BLE001
            continue
        if fp_key == source_fp:
            return (obj, fp_key)

    return None
