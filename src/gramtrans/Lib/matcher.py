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
    from .models import (
        GrammarCategory,
        MatchBasis,
        MatchBasisRecord,
        NaturalKeyRosterEntry,
    )
else:
    # loaded via site.addsitedir("Lib")
    from models import (
        GrammarCategory,
        MatchBasis,
        MatchBasisRecord,
        NaturalKeyRosterEntry,
    )


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
        "natural-key roster %s: %d of %d entries projected; %d carry no "
        "natural-key basis (the file admits the class but neither the file nor "
        "NATURAL_KEY_BINDINGS makes it executable)",
        path, len(roster), len(entries), skipped,
    )
    return roster


def _project_roster_entry(raw_entry) -> Optional[NaturalKeyRosterEntry]:
    """Project one roster ``entries[]`` object to a ``NaturalKeyRosterEntry``.

    Returns None -- "this class has no natural-key basis" -- for any row that
    cannot be projected. THE TWO HALVES MEET HERE (T029): the file supplies the
    declarative half (the class name, which it spells ``class`` and which is
    accepted alongside ``object_class``; the ``natural_key`` text; the
    ambiguity rule), and ``NATURAL_KEY_BINDINGS`` supplies the executable half
    (``key_fn_id`` / ``scope_fn_id``), which ``data-model.md`` marks as "038
    adds" and which the file will never carry, because T028 appends 038's six
    proposed entries to it VERBATIM and those entries have no such fields.

    Filling them from the binding is NOT the guess this docstring used to
    forbid. A guess would invent a key for a class nobody declared one for;
    this joins two independently-authored halves on the only key they share,
    the class name, and it can only ever ADD an admission the roster ALREADY
    granted -- a class absent from the file still projects nothing, however
    many bindings exist, and a class with no binding (``WfiWordform``) still
    projects nothing, however completely the file describes it.

    A file that DOES spell ``key_fn_id`` wins over the binding, so an entry can
    always override engine code rather than the other way round.
    """
    if not isinstance(raw_entry, dict):
        return None
    object_class = raw_entry.get("object_class") or raw_entry.get("class")
    binding = NATURAL_KEY_BINDINGS.get(object_class)
    try:
        return NaturalKeyRosterEntry(
            object_class=object_class,
            natural_key=raw_entry.get("natural_key"),
            key_unique_by_construction=bool(
                raw_entry.get("key_unique_by_construction")
            ),
            on_ambiguous_key=raw_entry.get("on_ambiguous_key"),
            reason=raw_entry.get("reason"),
            key_fn_id=(
                raw_entry.get("key_fn_id")
                or (binding.key_fn_id if binding else None)
            ),
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
            scope_fn_id=(
                raw_entry.get("scope_fn_id")
                or (binding.scope_fn_id if binding else None)
            ),
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
# Feature 038 T029 / T030 -- the EXECUTABLE half of the natural-key basis
# ---------------------------------------------------------------------------
#
# TWO HALVES, BOTH REQUIRED. A class has a natural-key basis only when
#
#   (a) 035's roster file admits it -- the DECLARATIVE half, owned by 035 and
#       merely read here (see the roster section above), and
#   (b) a `NaturalKeyBinding` exists to execute it -- the EXECUTABLE half,
#       owned by 038 and declared below.
#
# Either half alone yields no basis. That is not belt-and-braces, it is the
# safety property:
#
#   * a binding without a roster row would let engine code fabricate an
#     admission 035 never granted (035 FR-185 / 038 FR-003), and
#   * a roster row without a binding would let an admitted-but-unexecutable
#     row match on a guessed key. `WfiWordform` is exactly that case: 035
#     admits it and `census.NATURAL_KEY_DEFINITIONS` can even compute its key,
#     but 038 binds no key function for it, so it has no basis HERE.
#
# WHY `key_fn_id` / `scope_fn_id` LIVE IN CODE AND NOT IN THE FILE.
# `data-model.md` marks both as "038 adds". T028 appends 038's six proposed
# entries to 035's file VERBATIM, and those entries carry neither field -- so
# the file will never supply them. `_project_roster_entry` therefore fills them
# from `NATURAL_KEY_BINDINGS` when the file does not, keyed by class name. That
# is not a guess: it is the executable half being joined to the declarative
# half by the only key the two share. A file that DOES spell `key_fn_id` still
# wins, so an entry can always override the binding.
#
# WRITING SYSTEMS RUN IN OPPOSITE DIRECTIONS, AND THAT IS MEASURED.
# `PhPhoneme` keys on the default VERNACULAR (97 of 97 phonemes carry a name
# there; only 44 of 97 do in the default analysis WS, and `Mbugwe LizzieHC
# practice` has 42 phonemes and not one with an `en` name). Every other
# admitted class keys on the default ANALYSIS WS (natural-class names: 121 of
# 121 in analysis, 0 of 121 in vernacular; categories: 50 of 51 in analysis, 0
# in vernacular). The scope is therefore stored PER CLASS, and it is taken from
# `census.NATURAL_KEY_DEFINITIONS` rather than restated, so the matcher and the
# census can never hold two different keys for one class.
#
# `PhCode` is explicitly NOT the phoneme key. The key is `PhPhoneme.Name`.

if __package__:
    from . import census as _census
else:  # loaded via site.addsitedir("Lib")
    import census as _census  # type: ignore[no-redef]


#: The class is not enumerated on 035's roster, or 038 binds no key function
#: for it. Either way it has no natural-key basis and matching degrades to
#: GUID-only -- the pre-038 behaviour, which is a degradation and not an error.
KEY_INELIGIBLE_NOT_ADMITTED = "not_admitted_by_roster"

#: The object is not of EXACTLY the keyed class. `PhNCSegments` must never
#: match `PhNCFeatures` and `LexEntryInflType` must never match `LexEntryType`,
#: however identical their names: they are different linguistic objects that
#: happen to share a list.
KEY_INELIGIBLE_SUBCLASS_MISMATCH = "subclass_mismatch"

#: The name is a FLEx auto-generated rule label. It names the RULE, not the
#: class, so two objects carrying one are not the same object. Measured: 66 of
#: 113 feature-based natural classes in `Mbugwe LizzieHC practice` collide on
#: such a label, and 47 of the 113 carry one that is unique WITHIN the project
#: -- which is why this is an eligibility rule decided BEFORE candidate
#: counting rather than something the ambiguity rule could catch. Those 47
#: would otherwise sail through as clean single-candidate matches.
KEY_INELIGIBLE_AUTO_GENERATED = "auto_generated_rule_label"

#: The object has no name in ITS OWN scoped writing system, or that writing
#: system is not available at all (the pre-run WS mapping did not produce a
#: source -> target default vernacular, so a phoneme key is not computable).
#: Never fall back to another writing system: matching a secondary vernacular
#: would have fabricated 16 matches on `Yi Sichuan` alone.
KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS = "no_name_in_scoped_ws"

#: Closed set, so a report can enumerate the outcomes rather than print free
#: text. An ineligible object is REPORTED under its reason -- never silently
#: dropped (FR-013) and never created by key (FR-007 governs creation, and it
#: is not reached through a key that could not be computed).
KEY_INELIGIBLE_REASONS = frozenset({
    KEY_INELIGIBLE_NOT_ADMITTED,
    KEY_INELIGIBLE_SUBCLASS_MISMATCH,
    KEY_INELIGIBLE_AUTO_GENERATED,
    KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS,
})

#: FLEx labels every natural class it creates for a phonological rule context
#: after that rule. Matched with `startswith` on the invariant prefix rather
#: than a full-string regex: the rule name is arbitrary user text and may
#: contain anything, including an unbalanced quote.
_AUTO_GENERATED_NAME_PREFIX = 'Created automatically for rule'

#: Only `PhNCFeatures` carries the auto-label exclusion, because that is the
#: only class the roster excludes them for. `PhNCSegments` is left alone: its
#: entry states no such clause, and inventing one here would narrow the basis
#: beyond what the roster admits.
_AUTO_GENERATED_LABEL_CLASSES = frozenset({"PhNCFeatures"})


class NaturalKeyAmbiguityError(RuntimeError):
    """An eligible key resolved to MORE THAN ONE destination candidate.

    RAISED, never returned, and never resolved by picking one. Every one of
    038's six admitted entries sets ``on_ambiguous_key: harness_error`` and
    ``key_unique_by_construction: false``, so ambiguity is a measured, expected
    condition -- 66 collisions in 113 natural classes -- and the only safe
    answer is to stop rather than fabricate a correspondence. An ambiguous key
    therefore produces NO decision, and so no IDENTITY-SUBSTITUTION record to
    inflate the count with a guess.

    The message always names the class, the destination scope and the key, so
    the operator can find the colliding objects without re-running anything.
    """


@dataclass(frozen=True)
class NaturalKeyBinding:
    """The executable half of one roster row (T029).

    Fields:
        object_class:    LCM class name, as the roster spells it.
        key_fn_id:       names the pure key-extraction function in
                         ``NATURAL_KEY_FNS``. One id PER CLASS even though the
                         extraction shape is shared, so a report can say which
                         key ran rather than "a name".
        scope_fn_id:     names the destination candidate scope in
                         ``NATURAL_KEY_SCOPE_FNS``. A key unique only within
                         one owning list must never be matched project-wide.
        ws_scope:        which default writing system the key is read from.
                         Taken from ``census.NATURAL_KEY_DEFINITIONS``, never
                         restated, so matcher and census cannot drift.
        creates_on_miss: whether FR-007 lets a MISSED key create the object.
                         True for every class but ``MoMorphType``.
    """

    object_class: str
    key_fn_id: str
    scope_fn_id: str
    ws_scope: str
    creates_on_miss: bool

    def __post_init__(self) -> None:
        definition = _census.NATURAL_KEY_DEFINITIONS.get(self.object_class)
        if definition is None:
            raise ValueError(
                "NaturalKeyBinding for " + repr(self.object_class) + " has no "
                "census NATURAL_KEY_DEFINITIONS counterpart -- the matcher may "
                "not key a class the census cannot measure, or the two would "
                "hold different keys for one class"
            )
        if self.ws_scope != definition.ws_scope:
            raise ValueError(
                "NaturalKeyBinding for " + repr(self.object_class)
                + " reads the " + repr(self.ws_scope) + " writing system but "
                "the census definition reads " + repr(definition.ws_scope)
            )


@dataclass(frozen=True)
class MatchDecision:
    """The whole answer to "what is this source object's destination?" (T031).

    Computed ONCE, in the plan builder, so Preview and Move agree by
    construction rather than by both happening to run the same steps.

    Fields:
        record:            the `MatchBasisRecord` for the run report. Always
                           present, including for a miss (basis NONE).
        target_obj:        the matched destination object, or None.
        enrich:            True whenever a destination was matched. A matched
                           GUID is a LINK, not a SKIP (defect G3,
                           data-model.md:209-213): field-identity comparison
                           still has to happen, and this says so explicitly
                           rather than leaving "matched" to be read as "done".
        ineligible_reason: "" or a member of `KEY_INELIGIBLE_REASONS`.
        may_create:        whether the caller may create the object because the
                           KEY MISSED. False whenever a key could not be
                           computed at all -- an object that could not be keyed
                           was never compared, so a create here would be a
                           create-anyway, which is the duplicating half of the
                           defect this feature removes. It is also False when
                           the class has no basis: the natural-key step did not
                           run, and the caller's own GUID-only path (FR-007 /
                           FR-013) decides, exactly as the roster's
                           "if 035 rejects an entry" clause requires.
        parent_divergence: "" when the two objects' owners agree or cannot be
                           compared; otherwise a message naming both owner
                           GUIDs. A matched category is NOT evidence that the
                           two hierarchies agree, and the matcher never
                           re-parents the destination.
    """

    record: "MatchBasisRecord"
    target_obj: object = None
    enrich: bool = False
    ineligible_reason: str = ""
    may_create: bool = False
    parent_divergence: str = ""


def _natural_key_fn(object_class: str) -> Callable:
    """The key function for one class: `(obj, ws_handle) -> Optional[str]`.

    Delegates to `census.natural_key_of`, which returns the named property's
    alt in the scoped writing system UNCHANGED -- no `.strip()`, no
    `.casefold()`, no `unicodedata.normalize`. `Nasals`, `nasals` and
    `Nasal Consonants` were measured as three distinct classes, and a
    vernacular phoneme inventory is exactly where NFC and NFD spellings of one
    grapheme coexist, so any normalisation here would silently merge distinct
    objects.

    None means "this object HAS no key" -- and an object with no key never
    matches anything, including another object with no key.
    """
    definition = _census.NATURAL_KEY_DEFINITIONS[object_class]

    def _key_of(obj, ws_handle):
        return _census.natural_key_of(obj, definition, ws_handle)

    _key_of.__name__ = "natural_key_of_" + object_class
    _key_of.__doc__ = (
        object_class + ": " + definition.description
    )
    return _key_of


def _natural_key_scope_fn(object_class: str) -> Callable:
    """The destination candidate scope for one class: `(target) -> Iterable`.

    Delegates to `census.objects_in_class`, which enumerates instances of
    EXACTLY this class -- `AllInstances()` yields the whole inheritance
    subtree, so an unfiltered enumeration would offer a `CmSemanticDomain` as a
    candidate for a `PartOfSpeech`. Exactness is also what makes the three
    subclass-restricted classes safe by construction here: a `PhNCFeatures`
    never appears in the `PhNCSegments` scope, and a `LexEntryType` never
    appears in the `LexEntryInflType` scope.

    `resolve_match` re-checks each candidate anyway, because a caller may pass
    candidates it assembled itself.
    """

    def _scope(target):
        return _census.objects_in_class(target, object_class)

    _scope.__name__ = "objects_in_class_" + object_class
    return _scope


#: `key_fn_id -> (obj, ws_handle) -> Optional[str]`.
NATURAL_KEY_FNS: Dict[str, Callable] = {}

#: `scope_fn_id -> (target) -> Iterable[obj]`.
NATURAL_KEY_SCOPE_FNS: Dict[str, Callable] = {}


def _bind(object_class: str, key_fn_id: str, scope_fn_id: str,
          creates_on_miss: bool) -> "NaturalKeyBinding":
    """Register one class's key and scope functions and return its binding."""
    NATURAL_KEY_FNS[key_fn_id] = _natural_key_fn(object_class)
    NATURAL_KEY_SCOPE_FNS[scope_fn_id] = _natural_key_scope_fn(object_class)
    return NaturalKeyBinding(
        object_class=object_class,
        key_fn_id=key_fn_id,
        scope_fn_id=scope_fn_id,
        ws_scope=_census.NATURAL_KEY_DEFINITIONS[object_class].ws_scope,
        creates_on_miss=creates_on_miss,
    )


#: The six classes FR-005 admits, and nothing else. `WfiWordform` is
#: deliberately absent: 035 admits it and the census can key it, but matching a
#: wordform is 035's own business, and binding it here would silently extend
#: 038's matcher over a class 038 never measured.
#:
#: `MoMorphType` is the ONE class that may not create on a miss. FLEx treats the
#: morph-types list as project-independent fixed content -- all 19 GUIDs are
#: byte-identical across all three projects measured -- so identity already
#: matches the canonical list and a key match there is a rare SIGNAL rather than
#: the normal path. Minting a morph type would add an object the canonical list
#: does not contain, so an unmatched key is reported and skipped, never created,
#: and any nonzero IDENTITY-SUBSTITUTION count for it is a review signal.
#: `LexEntryInflType` is the explicit opposite: a project-local inflection type
#: (`Class 10`, `Perfective`, `Habitual`) is ordinary linguistic content and
#: creating it IS correct (FR-007, GUID-preserving).
NATURAL_KEY_BINDINGS: Dict[str, NaturalKeyBinding] = {
    binding.object_class: binding for binding in (
        _bind("PhPhoneme",
              "phoneme_name_default_vernacular",
              "project_phonemes",
              True),
        _bind("PhNCSegments",
              "nc_segments_name_default_analysis",
              "phondata_natural_classes_segment_based",
              True),
        _bind("PhNCFeatures",
              "nc_features_name_default_analysis",
              "phondata_natural_classes_feature_based",
              True),
        _bind("PartOfSpeech",
              "part_of_speech_name_default_analysis",
              "project_wide_category_hierarchy",
              True),
        _bind("MoMorphType",
              "morph_type_name_default_analysis",
              "lexicon_morph_types",
              False),
        _bind("LexEntryInflType",
              "lex_entry_infl_type_name_default_analysis",
              "variant_entry_types_inflectional_only",
              True),
    )
}


def natural_key_binding_for(
    object_class: str,
) -> Optional[NaturalKeyBinding]:
    """The binding for a class, or None when 038 binds no key function for it.

    None is the executable half of "no natural-key basis" and is a normal,
    non-error answer, exactly as `natural_key_roster_entry_for` returning None
    is the declarative half.
    """
    return NATURAL_KEY_BINDINGS.get(object_class)


def _guid_text(obj) -> str:
    """An object's GUID as a string, or "" when it has none."""
    if obj is None:
        return ""
    guid = getattr(obj, "Guid", None)
    if guid is None:
        return ""
    text = str(guid)
    return text if text else ""


def _class_name(obj) -> str:
    """An object's exact LCM class name, or "" when it does not declare one."""
    name = getattr(obj, "ClassName", None)
    return str(name) if name else ""


def natural_key_eligibility(object_class, obj, ws_handle=None) -> str:
    """Whether `obj` MAY be keyed at all: "" when it may, else a reason token.

    Decided BEFORE candidate counting, which is the whole point: an ineligible
    object is reported under its own named, counted outcome and is not even an
    ambiguity. 47 of the 113 measured feature-based natural classes carry an
    auto-generated label that is unique within its project, so the ambiguity
    rule alone would let every one of them through as a clean single-candidate
    match.

    Never raises. `ws_handle` is optional so the two handle-independent rules
    (admission and subclass) can be asked without a live project; when it is
    given, the two name-dependent rules are checked as well.
    """
    binding = NATURAL_KEY_BINDINGS.get(object_class)
    if binding is None or natural_key_roster_entry_for(object_class) is None:
        return KEY_INELIGIBLE_NOT_ADMITTED

    declared = _class_name(obj)
    if declared and declared != object_class:
        return KEY_INELIGIBLE_SUBCLASS_MISMATCH

    text = NATURAL_KEY_FNS[binding.key_fn_id](obj, ws_handle)
    if object_class in _AUTO_GENERATED_LABEL_CLASSES and text is not None:
        if text.startswith(_AUTO_GENERATED_NAME_PREFIX):
            return KEY_INELIGIBLE_AUTO_GENERATED
    if ws_handle is not None and not text:
        return KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS
    return ""


def natural_key_for(object_class, obj, ws_handle) -> Optional[str]:
    """The exact key string for one object, or None when it HAS no key.

    Read ONLY from the class's own scoped writing system. A name in the other
    default writing system is not a key and must never be silently substituted.
    """
    binding = NATURAL_KEY_BINDINGS.get(object_class)
    if binding is None:
        return None
    return NATURAL_KEY_FNS[binding.key_fn_id](obj, ws_handle)


def _parent_divergence(object_class: str, source_obj, target_obj) -> str:
    """A message naming both owner GUIDs when they differ, else "".

    The owning parent is NOT part of any key -- catalog category
    `093264d7-06c3-42e1-bc4d-5a965ce63887` ("Demonstrative") is depth-1 in
    `Ejagham Mini` and depth-2 in `Mbugwe LizzieHC practice`, so a
    parent-scoped key would fail to match precisely the category a linguist has
    re-parented, and failing to match is 038's whole defect.

    But a match is NOT evidence that the two hierarchies agree, so the
    divergence is recorded and reported. For `LexEntryInflType` it is anomalous
    rather than routine: 14 of the 15 measured inflection types sit under
    `Irregularly Inflected Form`. The matcher only DECIDES; it never re-parents
    the destination.
    """
    source_parent = _guid_text(getattr(source_obj, "Owner", None))
    target_parent = _guid_text(getattr(target_obj, "Owner", None))
    if not source_parent or not target_parent:
        return ""
    if source_parent == target_parent:
        return ""
    return (
        object_class + " matched across a parent divergence: the source object "
        "is owned by " + source_parent + " and the matched destination object "
        "by " + target_parent + ". The owning parent is not part of the key, "
        "and the destination keeps its own parent -- this is reported, not "
        "corrected."
    )


def resolve_match(
    object_class: str,
    source_obj,
    candidates,
    *,
    ws_handles,
    identity_remap=None,
    key_fn=None,
) -> MatchDecision:
    """Identity first, then a roster-admitted natural key. THE ordering (T031).

    Parameters:
        object_class:   LCM class name as the roster spells it.
        source_obj:     the source object being placed.
        candidates:     the destination scope for this class. Production
                        resolves it through `NATURAL_KEY_SCOPE_FNS`; callers
                        may pass an already-assembled iterable.
        ws_handles:     `{ws_scope: handle}`. A missing scope means the key is
                        NOT COMPUTABLE, which is reported -- never answered by
                        falling back to another writing system.
        identity_remap: `{source_guid: target_guid}` from a previous run.
        key_fn:         injection hook, mirroring `lookup_target`'s existing
                        `fingerprint_fn=`.

    Returns a `MatchDecision` in every case except ambiguity.

    Raises:
        NaturalKeyAmbiguityError: when an eligible key hits more than one
            candidate. Never a pick, and never a record.

    The order is a contract, not a preference. Identity is authoritative and
    the key is consulted ONLY when identity finds nothing; inverting them would
    let a name collision overwrite an object a GUID had already correctly
    identified. On an identity hit the key is not merely unused -- it is NEVER
    COMPUTED, so a collision has no opportunity to participate.
    """
    source_guid = _guid_text(source_obj)
    candidates = list(candidates or ())

    # --- Step 1: identity. Authoritative, and it short-circuits. ------------
    wanted = {source_guid} if source_guid else set()
    if identity_remap and source_guid:
        remapped = identity_remap.get(source_guid)
        if remapped:
            wanted.add(str(remapped))
    for candidate in candidates:
        candidate_guid = _guid_text(candidate)
        if candidate_guid and candidate_guid in wanted:
            return MatchDecision(
                record=MatchBasisRecord(
                    basis=MatchBasis.IDENTITY,
                    object_class=object_class,
                    source_guid=source_guid,
                    target_guid=candidate_guid,
                    candidate_count=1,
                ),
                target_obj=candidate,
                enrich=True,
                may_create=False,
                parent_divergence=_parent_divergence(
                    object_class, source_obj, candidate,
                ),
            )

    def _miss(reason: str, may_create: bool) -> MatchDecision:
        return MatchDecision(
            record=MatchBasisRecord(
                basis=MatchBasis.NONE,
                object_class=object_class,
                source_guid=source_guid,
                candidate_count=0,
            ),
            target_obj=None,
            enrich=False,
            ineligible_reason=reason,
            may_create=may_create,
        )

    # --- Step 2: the natural key, if and only if BOTH halves admit it. ------
    binding = NATURAL_KEY_BINDINGS.get(object_class)
    entry = natural_key_roster_entry_for(object_class)
    if binding is None or entry is None:
        return _miss(KEY_INELIGIBLE_NOT_ADMITTED, False)

    ws_handle = (ws_handles or {}).get(binding.ws_scope)
    reason = natural_key_eligibility(object_class, source_obj, ws_handle)
    if reason:
        return _miss(reason, False)

    compute = key_fn or NATURAL_KEY_FNS[binding.key_fn_id]
    key = compute(source_obj, ws_handle)
    if not key:
        return _miss(KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS, False)

    matched = []
    for candidate in candidates:
        if natural_key_eligibility(object_class, candidate, ws_handle):
            continue
        if compute(candidate, ws_handle) == key:
            matched.append(candidate)

    if len(matched) > 1:
        raise NaturalKeyAmbiguityError(
            "natural-key match for object class " + repr(object_class)
            + " is AMBIGUOUS: key " + repr(key) + " resolves to "
            + str(len(matched)) + " destination objects in scope "
            + repr(binding.scope_fn_id) + " ("
            + ", ".join(_guid_text(m) for m in matched) + "). The roster sets "
            "on_ambiguous_key=harness_error for this class and does not claim "
            "the key is unique by construction, so this is a measured, "
            "expected condition and the only safe answer is to stop. Picking "
            "one would fabricate a correspondence and record it as an "
            "identity substitution."
        )

    if not matched:
        return _miss("", binding.creates_on_miss)

    target = matched[0]
    return MatchDecision(
        record=MatchBasisRecord(
            basis=MatchBasis.NATURAL_KEY,
            object_class=object_class,
            source_guid=source_guid,
            key_expression=entry.natural_key,
            key_value=key,
            target_guid=_guid_text(target),
            candidate_count=1,
        ),
        target_obj=target,
        enrich=True,
        may_create=False,
        parent_divergence=_parent_divergence(object_class, source_obj, target),
    )


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
