"""Feature 035 -- exact-reason loss-allowlist matching with cap enforcement
(T032 of specs/035-fullsweep-fidelity/tasks.md Phase 4).

Source: spec.md FR-115..FR-117, contracts/rosters.md section 2
(``contracts/loss-allowlist.json``), contracts/artifact-schema.md
(``allowlist_hits``).

SCOPE. This module covers exactly what the dropped-and-allowlisted bucket of
FR-097 needs: an entry's structure (FR-115), EXACT reason matching with
patterns refused (FR-116), and the per-entry cap (FR-117). The rest of the
validity regime -- expiry (FR-118), tracking-issue openness (FR-119),
staleness (FR-120), engine-bug refusal (FR-121), the corpus hard caps
(FR-122) and the capability-presence inversion (FR-182) -- lands in User
Story 5 and is deliberately NOT implemented here.

NAMING. Do not confuse this with the ``allowlist`` parameter threaded through
``safety.py`` / ``baseline.py`` / ``run_one_project``. That one is a write
DESTINATION PROJECT-NAME allowlist, matched by anchored ``re.fullmatch``
against names like ``Target1`` (``safety.assert_name_allowlisted``). This one
is a LOSS-REASON allowlist, matched by exact string equality and never by
pattern. They are unrelated concepts that happen to share an English word;
every public name here says ``loss_allowlist`` so no call site can blur them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_CONTRACTS_DIR = (
    Path(__file__).resolve().parents[2] / "specs" / "035-fullsweep-fidelity" / "contracts"
)
LOSS_ALLOWLIST_NAME = "loss-allowlist.json"

#: contracts/rosters.md section 2, verbatim key order. FR-115: ALL fields
#: present on EVERY entry -- a partially-filled entry is invalid, never a
#: best-effort match.
LOSS_ALLOWLIST_ENTRY_FIELDS: tuple[str, ...] = (
    "id",
    "owner",
    "issue",
    "projects",
    "class",
    "field",
    "reason",
    "max_count",
    "first_observed",
    "expires",
    "justification",
    "capability_id",
)

#: ``capability_id`` is the one field allowed to be null (rosters.md: "null
#: unless FR-182 applies"). Every other field must be present AND non-null.
LOSS_ALLOWLIST_NULLABLE_FIELDS: frozenset = frozenset({"capability_id"})

#: FR-116 forbids wildcard and pattern matching so that "one entry cannot be
#: stretched to cover two different failure modes". Refusing these at LOAD
#: time is the point of T032: a pattern accepted at match time has already
#: widened the entry before any later validity check can object.
#:
#: A bare ``.`` is NOT listed -- ordinary reason strings end in a period and
#: refusing it would reject legitimate literals. The regex sequences that
#: turn a period into a wildcard are refused below instead.
PATTERN_METACHARACTERS: tuple[str, ...] = (
    "*", "?", "[", "]", "{", "}", "(", ")", "|", "\\", "^", "$", "+", "%",
)
PATTERN_SEQUENCES: tuple[str, ...] = (".*", ".+", ".?")


class LossAllowlistInvalid(ValueError):
    """FR-115/FR-116: the entry cannot stand as written.

    Maps to the ``ALLOWLIST_INVALID`` verdict (exit 8) -- distinct from a cap
    OVERFLOW, which is ordinary ``UNEXPLAINED_LOSS`` (exit 1). An invalid
    entry is a defect in the allowlist; an overflowing entry is a valid entry
    describing more loss than it was permitted to excuse.
    """


def pattern_offenders(reason: str) -> tuple[str, ...]:
    """Every wildcard/pattern construct present in ``reason`` (FR-116)."""
    found = [m for m in PATTERN_METACHARACTERS if m in reason]
    found += [s for s in PATTERN_SEQUENCES if s in reason]
    return tuple(sorted(set(found)))


@dataclass(frozen=True)
class LossAllowlistEntry:
    """One accepted loss pattern. ``class_name`` carries the JSON key ``class``
    (a Python keyword, so it cannot be an attribute name)."""

    id: str
    owner: str
    issue: str
    projects: tuple[str, ...]
    class_name: str
    field_name: str
    reason: str
    max_count: int
    first_observed: str
    expires: str
    justification: str
    capability_id: Optional[str] = None

    @classmethod
    def from_json(cls, raw: dict) -> "LossAllowlistEntry":
        """FR-115: every field present. FR-116: the reason is a literal.
        FR-117: a declared, usable maximum count."""
        if not isinstance(raw, dict):
            raise LossAllowlistInvalid(
                "[FR-115] an allowlist entry must be an object, got %r" % type(raw).__name__
            )
        missing = [f for f in LOSS_ALLOWLIST_ENTRY_FIELDS if f not in raw]
        if missing:
            raise LossAllowlistInvalid(
                "[FR-115] entry %r is missing required field(s) %r -- every field "
                "must be present on every entry"
                % (raw.get("id", "<no id>"), missing)
            )
        null = [
            f
            for f in LOSS_ALLOWLIST_ENTRY_FIELDS
            if raw[f] is None and f not in LOSS_ALLOWLIST_NULLABLE_FIELDS
        ]
        if null:
            raise LossAllowlistInvalid(
                "[FR-115] entry %r has null field(s) %r -- only capability_id may "
                "be null" % (raw["id"], null)
            )

        reason = raw["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise LossAllowlistInvalid(
                "[FR-116] entry %r has no literal reason to match" % (raw["id"],)
            )
        offenders = pattern_offenders(reason)
        if offenders:
            raise LossAllowlistInvalid(
                "[FR-116] entry %r reason contains pattern construct(s) %r -- the "
                "reason is matched EXACTLY; wildcards are refused here so one "
                "entry cannot be stretched to cover two failure modes"
                % (raw["id"], list(offenders))
            )

        max_count = raw["max_count"]
        if isinstance(max_count, bool) or not isinstance(max_count, int):
            raise LossAllowlistInvalid(
                "[FR-117] entry %r max_count must be an integer, got %r"
                % (raw["id"], type(max_count).__name__)
            )
        if max_count < 1:
            raise LossAllowlistInvalid(
                "[FR-117] entry %r declares max_count=%r -- an entry that permits "
                "nothing is not a declared maximum, it is a missing one"
                % (raw["id"], max_count)
            )

        projects = raw["projects"]
        if isinstance(projects, str) or not isinstance(projects, Sequence):
            raise LossAllowlistInvalid(
                "[FR-115] entry %r projects must be a list of exact project names"
                % (raw["id"],)
            )
        if not projects:
            raise LossAllowlistInvalid(
                "[FR-115] entry %r names no project -- an entry that applies "
                "nowhere cannot excuse a loss anywhere" % (raw["id"],)
            )

        return cls(
            id=str(raw["id"]),
            owner=str(raw["owner"]),
            issue=str(raw["issue"]),
            projects=tuple(str(p) for p in projects),
            class_name=str(raw["class"]),
            field_name=str(raw["field"]),
            reason=reason,
            max_count=max_count,
            first_observed=str(raw["first_observed"]),
            expires=str(raw["expires"]),
            justification=str(raw["justification"]),
            capability_id=(
                None if raw["capability_id"] is None else str(raw["capability_id"])
            ),
        )

    def covers(self, *, project: str, class_name: str, field_name: str, reason: str) -> bool:
        """FR-116: EXACT match on the reason, and on the class and field the
        entry was written for, in the project it was written for.

        No normalisation, no case folding, no stripping -- an entry that does
        not match the observed reason byte-for-byte does not cover it.
        """
        return (
            project in self.projects
            and class_name == self.class_name
            and field_name == self.field_name
            and reason == self.reason
        )


def load_loss_allowlist(
    path: Optional[Path] = None, *, contracts_dir: Optional[Path] = None,
) -> tuple[LossAllowlistEntry, ...]:
    """Read and validate ``loss-allowlist.json``.

    An empty ``entries`` list is legitimate and means "nothing is excused" --
    the honest default. A malformed entry raises rather than being skipped,
    because a skipped entry would silently narrow the allowlist and change
    which losses count as explained.
    """
    if path is None:
        base = DEFAULT_CONTRACTS_DIR if contracts_dir is None else Path(contracts_dir)
        path = base / LOSS_ALLOWLIST_NAME
    path = Path(path)
    if not path.exists():
        raise LossAllowlistInvalid(
            "[FR-115] the loss allowlist must be a git-tracked file reviewed as "
            "source; %s does not exist" % path
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "entries" not in payload:
        raise LossAllowlistInvalid(
            "[FR-115] %s must be an object carrying an 'entries' list" % path
        )
    entries = tuple(LossAllowlistEntry.from_json(e) for e in payload["entries"])

    seen: dict = {}
    for e in entries:
        if e.id in seen:
            raise LossAllowlistInvalid(
                "[FR-115] allowlist id %r is used twice -- ids are stable and "
                "never reused" % (e.id,)
            )
        seen[e.id] = e
    return entries


@dataclass
class LossAllowlistMatch:
    """The outcome of testing one observed loss against the allowlist."""

    entry: Optional[LossAllowlistEntry] = None
    within_cap: bool = False
    count_after: int = 0

    @property
    def covered(self) -> bool:
        """FR-117: covered only if an entry matched AND the cap still admits it.
        A match over cap is unexplained loss, never a widened allowance."""
        return self.entry is not None and self.within_cap


@dataclass
class LossAllowlistMatcher:
    """Matches observed losses against the allowlist, counting per entry.

    One matcher per project run. FR-117's cap is per entry, so the counts live
    here rather than on the frozen entries.
    """

    entries: tuple[LossAllowlistEntry, ...] = ()
    counts: dict = field(default_factory=dict)
    overflowed: dict = field(default_factory=dict)

    def match(
        self, *, project: str, class_name: str, field_name: str, reason: str,
    ) -> LossAllowlistMatch:
        """Test one observed loss. Increments the matched entry's count.

        FR-117: at exactly ``max_count`` the entry still covers; strictly over
        it the loss is unexplained and the overflow is recorded so the run can
        report it rather than absorb it.
        """
        for entry in self.entries:
            if not entry.covers(
                project=project, class_name=class_name,
                field_name=field_name, reason=reason,
            ):
                continue
            count = self.counts.get(entry.id, 0) + 1
            self.counts[entry.id] = count
            if count > entry.max_count:
                self.overflowed[entry.id] = count
                return LossAllowlistMatch(entry=entry, within_cap=False, count_after=count)
            return LossAllowlistMatch(entry=entry, within_cap=True, count_after=count)
        return LossAllowlistMatch()

    def overflows(self) -> tuple[dict, ...]:
        """Entries whose observed count exceeded their declared maximum. Each
        is unexplained loss (``UNEXPLAINED_LOSS``), not an invalid entry."""
        out = []
        for entry in self.entries:
            if entry.id in self.overflowed:
                out.append({
                    "id": entry.id,
                    "cap": entry.max_count,
                    "observed": self.overflowed[entry.id],
                    "over_by": self.overflowed[entry.id] - entry.max_count,
                })
        return tuple(out)

    def hits(self) -> tuple[dict, ...]:
        """FR-123 / artifact-schema ``allowlist_hits``: every entry actually
        consumed, with its matched count, cap, and remaining headroom.

        Entries that matched nothing are omitted -- they were not consumed.
        Headroom floors at zero so an overflow does not report negative slack.
        """
        out = []
        for entry in self.entries:
            count = self.counts.get(entry.id, 0)
            if not count:
                continue
            out.append({
                "id": entry.id,
                "matched_count": count,
                "cap": entry.max_count,
                "headroom": max(0, entry.max_count - count),
            })
        return tuple(out)
