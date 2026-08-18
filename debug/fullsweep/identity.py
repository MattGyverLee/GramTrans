"""Feature 035 -- IDENTITY RULES (T028 of specs/035-fullsweep-fidelity/tasks.md
Phase 4 / US1).

Source: spec.md FR-183..FR-187, contracts/natural-key-identity-roster.json.

Four rules that a naive comparator gets wrong, each in its own section below:

  * FR-183 -- TOOL-OWNED IDENTITY. The target-side object that records the
    transfer tool's OWN act is pinned to a fixed, tool-owned, well-known
    constant. Never derived from a source value; never exempted from
    measurement; exactly one instance expected per target, and a second is a
    NO-EXTRA failure that is never allowlistable.
  * FR-184 -- EVALUATION STATE, NOT AGENT IDENTITY. Human approval is
    compared as a tri-state, never in whole or in part by the identity of the
    object that recorded it. 219 human-approved analyses were once silently
    dropped by a comparator that conflated the two.
  * FR-185/FR-186 -- NATURAL-KEY IDENTITY, admitted only by enumeration on the
    tracked roster, with identity authoritative and the natural key strictly a
    fallback.
  * FR-187 -- IDENTITY-SUBSTITUTION, a first-class accounting outcome with a
    durable per-run remap record, counted per class, never silent and never
    collapsed into "already present".

This module MEASURES. It does not change engine behaviour: feature 035 is a
fidelity sweep, and an instrument that edits the thing it measures cannot
report on it. Where the engine's current construction does not satisfy a rule
here, that is recorded as a finding (see ``ENGINE_CONFORMANCE_FINDINGS``), not
silently corrected.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .moves import HarnessError

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"

NATURAL_KEY_ROSTER_NAME = "natural-key-identity-roster.json"


# ===========================================================================
# FR-183 -- tool-owned identity
# ===========================================================================

#: The URL the well-known constant is derived from. Recorded so the constant
#: is AUDITABLE rather than arbitrary: anyone can recompute it (see
#: ``derive_tool_owned_guid``) and get the same answer forever.
TOOL_OWNED_GUID_NAMESPACE_URL = "https://github.com/MattGyverLee/GramTrans#transfer-agent"

#: FR-183: fixed, tool-owned, well-known. UUIDv5 over the URL above, so it is
#: reproducible from a published recipe and cannot drift.
TOOL_OWNED_AGENT_GUID = "28f8fffb-8d08-54cb-aa9b-2b593163fcc2"

#: The deliberate choice reviews/cycle5-domain-identity.md section 1 asked for
#: ("either is defensible domain-wise, but this should be a deliberate choice,
#: not accidental"), recorded here as the decision plus its reasons.
TOOL_OWNED_GUID_DECISION = {
    "chosen": "a GramTrans-specific well-known constant",
    "rejected": "the FieldWorks template's built-in human-agent GUID",
    "because": [
        "A template GUID is not FIXED in the sense FR-183 requires -- it is a "
        "property of whichever FieldWorks version produced the target, so "
        "pinning to it would make the constant vary with the target's origin.",
        "Reusing the template's built-in agent identity would conflate "
        "GramTrans's own act with FLEx's default human agent, so the "
        "measurement could no longer tell 'the tool recorded this' from 'the "
        "platform shipped this', which is precisely the distinction FR-183 "
        "exists to keep measurable.",
        "A tool-owned constant is derivable from a published recipe "
        "(derive_tool_owned_guid), so it is auditable rather than magic.",
    ],
}

#: FR-183 applies to a class whose target-side object records the transfer
#: tool's own act rather than reproducing any source object.
TOOL_OWNED_IDENTITY_CLASSES: dict[str, dict] = {
    "CmAgent": {
        "records": "the transfer tool's own evaluation act",
        "expected_instances_per_target": 1,
        "pinned_guid": TOOL_OWNED_AGENT_GUID,
        "engine_name": "GramTrans",
    },
}


def derive_tool_owned_guid(namespace_url: str = TOOL_OWNED_GUID_NAMESPACE_URL) -> str:
    """The published recipe for ``TOOL_OWNED_AGENT_GUID``. Kept as code so the
    constant can be re-derived and checked, never merely asserted."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, namespace_url))


def verify_tool_owned_guid_derivation() -> None:
    """Fail loudly if the recorded constant and its recipe ever disagree."""
    derived = derive_tool_owned_guid()
    if derived != TOOL_OWNED_AGENT_GUID:
        raise HarnessError(
            "[FR-183] TOOL_OWNED_AGENT_GUID (%s) does not match its published "
            "derivation from %s (%s) -- one of the two was edited without the "
            "other" % (TOOL_OWNED_AGENT_GUID, TOOL_OWNED_GUID_NAMESPACE_URL, derived)
        )


def is_tool_owned_class(class_name: str) -> bool:
    return class_name in TOOL_OWNED_IDENTITY_CLASSES


def assert_identity_not_derived_from_source(
    class_name: str, target_guid: str, source_guids,
) -> None:
    """FR-183: the identity MUST NOT be derived from any source value under
    any circumstance. Propagating a source object's identity onto such an
    object is a fidelity VIOLATION, not fidelity -- it asserts that another
    project's own evaluator approved data now present in this target."""
    if not is_tool_owned_class(class_name):
        return
    if target_guid in set(source_guids or ()):
        raise HarnessError(
            "[FR-183] the tool-owned-identity object for class %r carries "
            "identity %s, which is one of the SOURCE project's own identifiers "
            "-- a tool-owned identity must never be derived from a source value"
            % (class_name, target_guid)
        )


@dataclass(frozen=True)
class ToolOwnedIdentityOutcome:
    """The measured state of a tool-owned-identity class in one target."""
    class_name: str
    observed_guids: tuple[str, ...]
    expected_guid: str
    outcome: str          # "pinned" | "absent" | "unpinned" | "duplicated"
    no_extra_failure: bool
    allowlistable: bool
    message: str

    def as_dict(self) -> dict:
        return {
            "class": self.class_name, "observed_guids": list(self.observed_guids),
            "expected_guid": self.expected_guid, "outcome": self.outcome,
            "no_extra_failure": self.no_extra_failure,
            "allowlistable": self.allowlistable, "message": self.message,
        }


def classify_tool_owned_instances(class_name: str, observed_guids) -> ToolOwnedIdentityOutcome:
    """FR-183 + FR-102: measure a tool-owned-identity class against its pinned
    constant.

    Exactly one instance is expected per target. A second instance, UNDER ANY
    IDENTITY, is a NO-EXTRA failure and is NEVER allowlistable on the grounds
    that the object records the tool's own act -- more than one such object is
    never expected however an allowlist entry is written.

    The zero and one-but-unpinned cases are reported distinctly rather than
    folded together, because they mean different things: nothing recorded the
    act at all, versus something recorded it under an identity the tool does
    not own.
    """
    if not is_tool_owned_class(class_name):
        raise HarnessError(
            "[FR-183] classify_tool_owned_instances called for class %r, which "
            "is not a tool-owned-identity class (%r)"
            % (class_name, sorted(TOOL_OWNED_IDENTITY_CLASSES))
        )
    expected = TOOL_OWNED_IDENTITY_CLASSES[class_name]["pinned_guid"]
    guids = tuple(observed_guids or ())

    if len(guids) > 1:
        return ToolOwnedIdentityOutcome(
            class_name=class_name, observed_guids=guids, expected_guid=expected,
            outcome="duplicated", no_extra_failure=True, allowlistable=False,
            message=(
                "[FR-102/FR-183] %d instances of tool-owned-identity class %r "
                "found; exactly one is expected per target. This is an "
                "unexplained-loss failure under NO-EXTRA and MUST NEVER be "
                "allowlisted as an expected target-native addition -- provenance "
                "is now split across instances that should have been one."
                % (len(guids), class_name)
            ),
        )
    if not guids:
        return ToolOwnedIdentityOutcome(
            class_name=class_name, observed_guids=(), expected_guid=expected,
            outcome="absent", no_extra_failure=False, allowlistable=False,
            message=(
                "[FR-183] no instance of tool-owned-identity class %r in the "
                "target: nothing recorded the tool's own act. Distinct from an "
                "instance under the wrong identity -- reported separately, never "
                "folded into it." % (class_name,)
            ),
        )
    only = guids[0]
    if only == expected:
        return ToolOwnedIdentityOutcome(
            class_name=class_name, observed_guids=guids, expected_guid=expected,
            outcome="pinned", no_extra_failure=False, allowlistable=False,
            message="[FR-183] exactly one instance, carrying the pinned tool-owned identity.",
        )
    return ToolOwnedIdentityOutcome(
        class_name=class_name, observed_guids=guids, expected_guid=expected,
        outcome="unpinned", no_extra_failure=False, allowlistable=False,
        message=(
            "[FR-183] exactly one instance of %r, but under identity %s rather "
            "than the pinned tool-owned constant %s. FR-183 requires the "
            "identity be MEASURED against that constant rather than exempted "
            "from measurement, so this is reported, not passed over."
            % (class_name, only, expected)
        ),
    )


#: Where the engine as currently written does not satisfy a rule in this
#: module. Recorded rather than corrected: 035 measures, it does not edit the
#: engine. Each finding is what the sweep should EXPECT to observe, so a
#: surprising absence is as interesting as a hit.
ENGINE_CONFORMANCE_FINDINGS: tuple[dict, ...] = (
    {
        "id": "T028-F1",
        "rule": "FR-183",
        "site": "src/gramtrans/Lib/wordforms.py:plan_agent / apply_agent",
        "observed": (
            "plan_agent prefers whatever human agent the target already has "
            "(existing = agents[0]) and otherwise creates one BY NAME "
            "(_AGENT_NAME = 'GramTrans'). No fixed, tool-owned identity "
            "constant is used anywhere."
        ),
        "why_it_matters": (
            "FR-183 names this exact hazard: 'a name-based lookup used to avoid "
            "that collision can itself miss an existing instance and silently "
            "create a duplicate, splitting provenance across two instances that "
            "should have been one.' Taking agents[0] also means the identity "
            "recorded for the tool's act varies with whatever the target "
            "happened to contain first."
        ),
        "sweep_expectation": (
            "classify_tool_owned_instances will report 'unpinned' on a target "
            "whose agent came from the template, and 'duplicated' -- a NO-EXTRA "
            "failure -- on any target where the name-based path minted a second "
            "agent. Both are measurements of the engine as it stands, not "
            "defects in this module."
        ),
    },
)


# ===========================================================================
# FR-184 -- evaluation state, not agent identity
# ===========================================================================

#: The tri-state FR-184 requires. "parser-only" means no human evaluation is
#: recorded -- distinct from an evaluation recording disapproval.
EVAL_STATE_APPROVED = "approved"
EVAL_STATE_DISAPPROVED = "disapproved"
EVAL_STATE_PARSER_ONLY = "parser-only"

EVALUATION_STATES: tuple[str, ...] = (
    EVAL_STATE_APPROVED, EVAL_STATE_DISAPPROVED, EVAL_STATE_PARSER_ONLY,
)


class EvaluationIdentityConflation(HarnessError):
    """Raised when a caller tries to compare human-approval state using the
    identity of the object that recorded it. A distinct exception type so the
    regression that once dropped 219 human-approved analyses is caught by
    CODE at the call site, not by reading a message (FR-176)."""


def evaluation_state(approves: Optional[bool], has_human_evaluation: bool) -> str:
    """Derive FR-184's tri-state.

    ``has_human_evaluation`` False -> parser-only, REGARDLESS of ``approves``:
    the absence of a human opinion is its own state, never a disapproval.
    """
    if not has_human_evaluation:
        return EVAL_STATE_PARSER_ONLY
    return EVAL_STATE_APPROVED if approves else EVAL_STATE_DISAPPROVED


def compare_evaluation_state(source_state: str, target_state: str) -> bool:
    """FR-184: compare BY STATE. Load-bearing history -- 219 human-approved
    analyses were once silently dropped by a comparator that treated a
    locally-created evaluator in the target as a mismatch against the source's
    own locally-created evaluator even though the recorded state agreed."""
    for name, value in (("source_state", source_state), ("target_state", target_state)):
        if value not in EVALUATION_STATES:
            raise HarnessError(
                "[FR-184] %s=%r is not one of the three evaluation states %r"
                % (name, value, EVALUATION_STATES)
            )
    return source_state == target_state


def assert_no_agent_identity_in_evaluation_comparison(keys) -> None:
    """FR-184: the comparison must never be made, in whole or in part, by the
    identity of the tool-owned object that recorded the evaluation. Called with
    whatever field names a comparison is about to use; refuses agent-identity
    fields outright rather than trusting each caller to remember."""
    banned_substrings = ("agent", "evaluator", "approvedby", "approved_by")
    offending = []
    for key in keys or ():
        flat = str(key).replace("-", "").replace("_", "").lower()
        if any(b.replace("_", "") in flat for b in banned_substrings):
            if "guid" in flat or "hvo" in flat or "id" in flat or "ra" in flat:
                offending.append(str(key))
    if offending:
        raise EvaluationIdentityConflation(
            "[FR-184] refusing to compare human-approval state using "
            "agent-identity field(s) %r -- evaluation STATE is the basis; who "
            "performed the act is not. This is the conflation that silently "
            "dropped 219 human-approved analyses." % (sorted(offending),)
        )


# ===========================================================================
# FR-185 / FR-186 -- the natural-key basis and identity-first ordering
# ===========================================================================

class NaturalKeyBasisError(HarnessError):
    """FR-185: firing the natural-key basis for a class NOT enumerated on the
    Natural-Key Identity Roster is a harness error naming the class -- on the
    same terms FR-090 sets for RESOLVED-BY-EQUIVALENCE."""


class AmbiguousNaturalKey(HarnessError):
    """A natural-key fallback that resolved to more than one candidate. For a
    roster class whose key is not unique by construction (see the roster's
    ``key_unique_by_construction``), an ambiguous key MUST be a harness error
    naming the class, never a silent pick -- FR-187's remap record cannot
    honestly be written for an object whose correspondence is ambiguous."""


#: FR-186: the two possible orderings, recorded so the artifact can state
#: which one a run actually used.
ORDERING_IDENTITY_FIRST = "identity-first"
ORDERING_NATURAL_KEY_FIRST = "natural-key-first"


@dataclass(frozen=True)
class RosterEntry:
    class_name: str
    natural_key: str
    key_unique_by_construction: bool
    on_ambiguous_key: str
    reason: str


class NaturalKeyRoster:
    """The tracked roster (contracts/natural-key-identity-roster.json) loaded
    as the ONLY admission mechanism for FR-185's basis."""

    def __init__(self, entries: dict[str, RosterEntry], excluded: tuple[str, ...] = ()):
        self._entries = entries
        self._excluded = tuple(excluded)

    @classmethod
    def load(cls, contracts_dir: Optional[Path] = None) -> "NaturalKeyRoster":
        path = Path(contracts_dir or DEFAULT_CONTRACTS_DIR) / NATURAL_KEY_ROSTER_NAME
        if not path.is_file():
            raise HarnessError(
                "[FR-185] the Natural-Key Identity Roster is missing at %s. The "
                "basis is admitted ONLY by enumeration on this roster, so a "
                "missing roster cannot be treated as an empty one -- that would "
                "silently convert every legitimate natural-key match into a "
                "harness error." % (path,)
            )
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries: dict[str, RosterEntry] = {}
        for raw in doc.get("entries", ()):
            missing = [k for k in ("class", "natural_key", "reason") if not raw.get(k)]
            if missing:
                raise HarnessError(
                    "[FR-185] roster entry %r is missing required field(s) %r"
                    % (raw.get("class"), missing)
                )
            name = raw["class"]
            entries[name] = RosterEntry(
                class_name=name,
                natural_key=raw["natural_key"],
                key_unique_by_construction=bool(raw.get("key_unique_by_construction", False)),
                on_ambiguous_key=raw.get("on_ambiguous_key", "harness_error"),
                reason=raw["reason"],
            )
        if not entries:
            raise HarnessError(
                "[FR-185] the Natural-Key Identity Roster at %s enumerates NO "
                "classes. An empty roster is not a valid state: FR-185 requires "
                "the wordform class be enumerated on its (writing system, form) "
                "key precisely because 'omitting it from the roster would make "
                "this basis's own harness error fire on correct behaviour'. "
                "Loading an empty roster would therefore convert every "
                "legitimate wordform reuse into a harness error -- silently, and "
                "at scale. The likeliest cause is reading the schema_version-1 "
                "scaffold instead of the populated roster: spec artifacts are "
                "committed to main, so a feature worktree can hold a stale copy. "
                "Pass --contracts-dir at a tree carrying the populated roster."
                % (path,)
            )
        excluded = tuple(e.get("class", "") for e in doc.get("deliberately_excluded", ()))
        return cls(entries, excluded)

    def admits(self, class_name: str) -> bool:
        return class_name in self._entries

    def entry(self, class_name: str) -> RosterEntry:
        if class_name not in self._entries:
            raise NaturalKeyBasisError(
                "[FR-185] the natural-key identity basis fired for class %r, "
                "which is NOT enumerated on the Natural-Key Identity Roster "
                "(admitted: %r; deliberately excluded: %r). This is a harness "
                "error naming the class, never a fallback."
                % (class_name, sorted(self._entries), list(self._excluded))
            )
        return self._entries[class_name]

    @property
    def classes(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    @property
    def deliberately_excluded(self) -> tuple[str, ...]:
        return self._excluded


@dataclass
class IdentityRemapRecord:
    """FR-187: the durable, per-run record naming, for every object matched by
    natural key rather than by identity, the target object it was matched to --
    'sufficient for the link-classification' to proceed through it instead of
    re-guessing the correspondence.

    The comparator MUST read correspondences from here and MUST NOT infer or
    re-guess them (FR-185's roster note, FR-186).
    """
    roster: NaturalKeyRoster
    ordering: str = ORDERING_IDENTITY_FIRST
    #: class -> [ {source_guid, target_guid, natural_key, key_value} ]
    substitutions: dict = field(default_factory=dict)
    #: FR-186's aggregated warning: counted, reported ONCE per run.
    ordering_disagreements: list = field(default_factory=list)

    def record_substitution(
        self, class_name: str, source_guid: str, target_guid: str, key_value,
    ) -> None:
        entry = self.roster.entry(class_name)  # raises for a non-roster class
        self.substitutions.setdefault(class_name, []).append({
            "source_guid": source_guid, "target_guid": target_guid,
            "natural_key": entry.natural_key, "key_value": key_value,
        })

    def target_for(self, class_name: str, source_guid: str) -> Optional[str]:
        """The lookup the comparator uses instead of re-guessing (FR-185)."""
        for rec in self.substitutions.get(class_name, ()):
            if rec["source_guid"] == source_guid:
                return rec["target_guid"]
        return None

    def counts_by_class(self) -> dict[str, int]:
        """FR-187: per class, how many objects were matched this way, with a
        per-run total available from the caller by summing."""
        return {cls: len(recs) for cls, recs in sorted(self.substitutions.items())}

    def total(self) -> int:
        return sum(len(r) for r in self.substitutions.values())

    def note_ordering_disagreement(self, class_name: str, identity_reading, natural_key_reading) -> None:
        """FR-186: where a target predates identity preservation for a roster
        class and its recorded state would be READ DIFFERENTLY depending on
        which rule is applied, the run reports an aggregated warning."""
        self.ordering_disagreements.append({
            "class": class_name,
            "identity_reading": identity_reading,
            "natural_key_reading": natural_key_reading,
        })

    def ordering_warning(self) -> Optional[str]:
        """FR-186: silent at zero occurrences; EXACTLY ONE warning per run,
        naming BOTH readings, when at least one occurrence exists."""
        if not self.ordering_disagreements:
            return None
        classes = sorted({d["class"] for d in self.ordering_disagreements})
        first = self.ordering_disagreements[0]
        return (
            "[FR-186] %d object(s) across class(es) %r would be read differently "
            "depending on whether identity or the natural key is applied first. "
            "Both readings, for the first occurrence: identity=%r, "
            "natural_key=%r. This run used ordering %r."
            % (len(self.ordering_disagreements), classes,
               first["identity_reading"], first["natural_key_reading"], self.ordering)
        )

    def as_dict(self) -> dict:
        """The artifact's shape. FR-186 requires the ordering basis actually
        used be a recorded field, because it changes what a clean measurement
        means for the affected classes."""
        return {
            "ordering_basis_used": self.ordering,
            "identity_substitution_counts_by_class": self.counts_by_class(),
            "identity_substitution_total": self.total(),
            "substitutions": {k: list(v) for k, v in sorted(self.substitutions.items())},
            "ordering_disagreement_count": len(self.ordering_disagreements),
            "ordering_warning": self.ordering_warning(),
        }


@dataclass(frozen=True)
class MatchResult:
    """How one source object was matched, and on which basis."""
    source_guid: str
    target_guid: Optional[str]
    basis: str            # "identity" | "natural-key" | "unmatched"
    class_name: str = ""

    @property
    def is_substitution(self) -> bool:
        return self.basis == "natural-key"


def resolve_match(
    class_name: str,
    source_guid: str,
    identity_lookup: Callable[[str], Optional[str]],
    natural_key_lookup: Optional[Callable[[], list]] = None,
    *,
    remap: Optional[IdentityRemapRecord] = None,
    key_value=None,
) -> MatchResult:
    """FR-186: identity-first ordering, for real.

    ``identity_lookup(source_guid)`` returns the target identifier if identity
    resolves, else None. ``natural_key_lookup()`` returns the list of candidate
    target identifiers the natural key matches -- a LIST, not a single value,
    so ambiguity is representable and therefore checkable.

    Identity is authoritative. The natural key is consulted ONLY when identity
    does not resolve -- never the reverse. When the natural key is consulted
    for a class whose key is not unique by construction and it returns more
    than one candidate, that is a harness error, not a pick.
    """
    roster = remap.roster if remap is not None else None

    resolved = identity_lookup(source_guid)
    if resolved is not None:
        return MatchResult(source_guid=source_guid, target_guid=resolved,
                           basis="identity", class_name=class_name)

    if natural_key_lookup is None:
        return MatchResult(source_guid=source_guid, target_guid=None,
                           basis="unmatched", class_name=class_name)

    # Consulting the natural key at all is what FR-185 gates on the roster.
    if roster is None:
        raise NaturalKeyBasisError(
            "[FR-185] the natural-key basis was consulted for class %r without a "
            "roster to admit it. Admission is BY ENUMERATION only, so there is "
            "no roster-free path to this basis." % (class_name,)
        )
    entry = roster.entry(class_name)  # raises NaturalKeyBasisError off-roster

    candidates = list(natural_key_lookup() or ())
    if not candidates:
        return MatchResult(source_guid=source_guid, target_guid=None,
                           basis="unmatched", class_name=class_name)
    if len(candidates) > 1:
        raise AmbiguousNaturalKey(
            "[FR-185/FR-187] the natural key %s for class %r resolved to %d "
            "candidate targets (%r) for source %s. key_unique_by_construction=%s "
            "for this class, and an ambiguous key must be a harness error naming "
            "the class -- never a pick, because a remap record cannot honestly "
            "be written for an ambiguous correspondence."
            % (entry.natural_key, class_name, len(candidates), candidates,
               source_guid, entry.key_unique_by_construction)
        )

    target = candidates[0]
    if remap is not None:
        remap.record_substitution(class_name, source_guid, target, key_value)
    return MatchResult(source_guid=source_guid, target_guid=target,
                       basis="natural-key", class_name=class_name)


def assert_substitution_admissible(class_name: str, roster: NaturalKeyRoster) -> None:
    """FR-187: IDENTITY-SUBSTITUTION is admissible ONLY for a class enumerated
    on the roster; firing for anything else is a harness error, never a quiet
    reclassification."""
    roster.entry(class_name)
