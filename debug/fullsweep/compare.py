"""Feature 035 -- the object-level TOTAL-ACCOUNTING plane (T031 of
specs/035-fullsweep-fidelity/tasks.md Phase 4).

Source: spec.md FR-091, FR-092, FR-093, FR-097; contracts/guards.md
"TOTAL-ACCOUNTING"; contracts/artifact-schema.md.

The rule this module exists to enforce: every in-scope source identifier lands
in EXACTLY ONE bucket, and the residual is zero. Anything that is neither
transferred, independently verified as already present, legitimately
substituted, allowlisted within cap, nor explicitly out of scope is
unexplained loss -- and "it was reported" is never, by itself, an explanation
(FR-097).

Two inversions of the obvious design, both required:

* FR-091 -- **drop records corroborate, they never detect.** The primary
  channel is this module's own reconciliation of every source object against
  the target's actual state. Drop records are consulted only to explain an
  absence reconciliation has ALREADY found. Reading them first would inherit
  the engine's blind spot: its dedup key is
  ``(owner_guid, field_name, item_guid)`` and deliberately excludes the
  reason, so a second distinct failure on the same owner/field/item is
  discarded and the survivor carries a stale reason.
* FR-092 -- the dedup identity used HERE is widened to include the reason
  (``moves.DropRecord.identity``), so those collapsed failures reappear.

FR-093 -- the object-level plane in this module and the link/field-level
five-verdict plane are STRUCTURALLY SEPARATE and must not be merged in the
artifact or in the verdict logic. ``ObjectAccounting.as_dict`` therefore emits
object-plane keys only; ``assert_object_plane_only`` is the guard against a
caller folding field findings back in.

Bucket key names are this module's own: FR-097 and the artifact schema name
the five buckets in prose but pin no JSON keys. The superseded key list in
reviews/cycle1-qc.md is deliberately NOT followed -- it still carries a
standalone ``dropped_reported`` bucket, which is precisely what FR-097
abolished, and predates the IDENTITY-SUBSTITUTION bucket.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from . import identity as identity_mod
from .moves import DropRecord, HarnessError, dedup_drop_records

# ---------------------------------------------------------------------------
# The five FR-097 buckets, plus the residual that must stay empty
# ---------------------------------------------------------------------------

BUCKET_TRANSFERRED = "transferred_equal_payload"
BUCKET_ALREADY_PRESENT = "already_present_equal_payload_verified"
BUCKET_IDENTITY_SUBSTITUTION = "identity_substitution"
BUCKET_DROPPED_ALLOWLISTED = "dropped_allowlisted_within_cap"
BUCKET_OUT_OF_SCOPE = "out_of_scope"

#: FR-093: "zero unaccounted objects". Named as a bucket so the residual is
#: reported rather than being an absence nobody prints.
BUCKET_UNACCOUNTED = "unaccounted"

ACCOUNTING_BUCKETS: tuple[str, ...] = (
    BUCKET_TRANSFERRED,
    BUCKET_ALREADY_PRESENT,
    BUCKET_IDENTITY_SUBSTITUTION,
    BUCKET_DROPPED_ALLOWLISTED,
    BUCKET_OUT_OF_SCOPE,
    BUCKET_UNACCOUNTED,
)

#: Why an identifier was ruled unaccounted. FR-097 names the first two
#: explicitly as failures that must not be absorbed.
UNACCOUNTED_DROPPED_NOT_ALLOWLISTED = "dropped-and-reported-with-no-allowlist-entry"
UNACCOUNTED_NO_PAYLOAD_COMPARISON = "present-under-matching-identity-but-never-compared"
UNACCOUNTED_ABSENT_NO_EXPLANATION = "absent-from-target-with-no-explanation"
UNACCOUNTED_OVER_ALLOWLIST_CAP = "dropped-and-allowlisted-but-over-cap"
UNACCOUNTED_PAYLOAD_DIVERGED = "present-but-payload-compared-unequal"


@dataclass
class AccountedObject:
    """One source identifier's disposition. ``detail`` carries the reason for
    the unaccounted buckets, so a failure names itself in the artifact."""

    class_name: str
    source_id: str
    bucket: str
    detail: str = ""
    target_id: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "source_id": self.source_id,
            "bucket": self.bucket,
            "detail": self.detail,
            "target_id": self.target_id,
        }


@dataclass
class ObjectAccounting:
    """The object-level plane for one project."""

    project: str = ""
    assignments: list = field(default_factory=list)
    allowlist_overflows: tuple = ()
    corroborating_drops: tuple = ()
    uncorroborated_absences: list = field(default_factory=list)

    def assign(
        self, class_name: str, source_id: str, bucket: str, *,
        detail: str = "", target_id: Optional[str] = None,
    ) -> None:
        if bucket not in ACCOUNTING_BUCKETS:
            raise HarnessError(
                "[FR-097] %r is not one of the accounting buckets %r"
                % (bucket, list(ACCOUNTING_BUCKETS))
            )
        self.assignments.append(
            AccountedObject(
                class_name=class_name, source_id=source_id, bucket=bucket,
                detail=detail, target_id=target_id,
            )
        )

    def in_bucket(self, bucket: str) -> tuple:
        return tuple(a for a in self.assignments if a.bucket == bucket)

    def counts(self) -> dict:
        out = {b: 0 for b in ACCOUNTING_BUCKETS}
        for a in self.assignments:
            out[a.bucket] += 1
        return out

    @property
    def total(self) -> int:
        return len(self.assignments)

    @property
    def unaccounted(self) -> tuple:
        return self.in_bucket(BUCKET_UNACCOUNTED)

    @property
    def passed(self) -> bool:
        """FR-093: zero unaccounted objects. An allowlist cap overflow also
        fails -- FR-117 makes it unexplained loss, not a widened allowance."""
        return not self.unaccounted and not self.allowlist_overflows

    def assert_exactly_one_bucket_each(self) -> None:
        """FR-097's "exactly one" is a property of the reconciliation, so it is
        asserted rather than assumed: a duplicate assignment means the same
        object was explained twice and one explanation is wrong."""
        seen: dict = {}
        for a in self.assignments:
            key = (a.class_name, a.source_id)
            if key in seen:
                raise HarnessError(
                    "[FR-097] %s/%s was assigned to both %r and %r -- every "
                    "in-scope source identifier lands in EXACTLY one bucket"
                    % (a.class_name, a.source_id, seen[key], a.bucket)
                )
            seen[key] = a.bucket

    def as_dict(self) -> dict:
        """FR-093: object-plane keys ONLY. Field/link findings belong to the
        other plane and must not be folded in here."""
        return {
            "project": self.project,
            "counts": self.counts(),
            "total": self.total,
            "passed": self.passed,
            "unaccounted": [a.as_dict() for a in self.unaccounted],
            "allowlist_overflows": list(self.allowlist_overflows),
            "corroborating_drop_count": len(self.corroborating_drops),
            "uncorroborated_absence_count": len(self.uncorroborated_absences),
        }


#: The keys the link/field-level plane owns. FR-093 forbids merging them into
#: the object plane's block.
FIELD_PLANE_KEYS: frozenset = frozenset(
    {"link_findings", "findings", "field_verdicts", "verdict_plane"}
)


def assert_object_plane_only(block: dict) -> None:
    """FR-093: the two accounting planes stay structurally separate."""
    intruders = sorted(FIELD_PLANE_KEYS & set(block))
    if intruders:
        raise HarnessError(
            "[FR-093] the object-level accounting plane must stay structurally "
            "separate from the link/field-level verdict plane; found %r in the "
            "object-plane block" % (intruders,)
        )


def index_drops_by_target(
    drops: Sequence[DropRecord],
) -> dict:
    """Group drop records by the ``(owner, field_name, item)`` triple, keeping
    EVERY distinct reason (FR-092).

    The engine collapses these; this does not. A triple therefore maps to a
    tuple of records, not a single survivor.
    """
    out: dict = {}
    for rec in dedup_drop_records(drops):
        out.setdefault((rec.owner, rec.field_name, rec.item), []).append(rec)
    return {k: tuple(v) for k, v in out.items()}


def reconcile_objects(
    source_census: dict,
    target_before: dict,
    target_after: dict,
    *,
    project: str,
    payload_equal: Callable[[str, str, str], Optional[bool]],
    roster: Optional[object] = None,
    remap: Optional[object] = None,
    matcher: Optional[object] = None,
    drops: Sequence[DropRecord] = (),
    out_of_scope: Optional[Callable[[str, str], bool]] = None,
    natural_key_lookup: Optional[Callable[[str, str], Optional[list]]] = None,
) -> ObjectAccounting:
    """FR-097: walk EVERY in-scope source identifier and put it in exactly one
    bucket. This walk is the primary detection channel (FR-091).

    ``payload_equal(class_name, source_id, target_id)`` returns True/False for
    a comparison that was actually performed, and **None** when no comparison
    happened. None is not "probably fine": FR-097 makes an object present under
    a matching identity with no payload comparison an explicit failure, so it
    lands in ``unaccounted``.

    ``matcher`` is a ``allowlist.LossAllowlistMatcher`` (or None for "nothing
    is excused"). ``roster``/``remap`` are T028's ``NaturalKeyRoster`` and
    ``IdentityRemapRecord`` -- identity resolution is delegated to
    ``identity.resolve_match`` so the comparator never re-guesses identity and
    never compares raw identifiers itself.
    """
    acc = ObjectAccounting(project=project)
    drops_index = index_drops_by_target(drops)
    acc.corroborating_drops = dedup_drop_records(drops)
    consumed_drops: set = set()

    for class_name in sorted(source_census):
        target_ids = set(target_after.get(class_name, set()))
        before_ids = set(target_before.get(class_name, set()))

        def _identity_lookup(source_id: str, _t=target_ids) -> Optional[str]:
            return source_id if source_id in _t else None

        def _nk_lookup(source_id: str, _c=class_name):
            if natural_key_lookup is None:
                return None
            return natural_key_lookup(_c, source_id)

        for source_id in sorted(source_census[class_name]):
            if out_of_scope is not None and out_of_scope(class_name, source_id):
                acc.assign(class_name, source_id, BUCKET_OUT_OF_SCOPE,
                           detail="explicitly out of scope")
                continue

            match = identity_mod.resolve_match(
                class_name,
                source_id,
                _identity_lookup,
                (lambda _s=source_id: _nk_lookup(_s)) if natural_key_lookup else None,
                remap=remap,
                key_value=None,
            )

            # -- matched by natural key: the IDENTITY-SUBSTITUTION bucket -----
            if match.basis == "natural-key":
                if roster is not None:
                    # Harness error for a class not on the roster (FR-187).
                    identity_mod.assert_substitution_admissible(class_name, roster)
                acc.assign(class_name, source_id, BUCKET_IDENTITY_SUBSTITUTION,
                           detail="matched by natural key",
                           target_id=match.target_guid)
                continue

            # -- matched by identity: transferred, or already present ---------
            if match.basis == "identity" and match.target_guid is not None:
                equal = payload_equal(class_name, source_id, match.target_guid)
                if equal is None:
                    acc.assign(class_name, source_id, BUCKET_UNACCOUNTED,
                               detail=UNACCOUNTED_NO_PAYLOAD_COMPARISON,
                               target_id=match.target_guid)
                elif not equal:
                    acc.assign(class_name, source_id, BUCKET_UNACCOUNTED,
                               detail=UNACCOUNTED_PAYLOAD_DIVERGED,
                               target_id=match.target_guid)
                elif source_id in before_ids:
                    # FR-097: "already present" needs the payload verified
                    # independently -- identity alone is not enough, and the
                    # comparison above is what supplies that verification.
                    acc.assign(class_name, source_id, BUCKET_ALREADY_PRESENT,
                               detail="payload independently verified equal",
                               target_id=match.target_guid)
                else:
                    acc.assign(class_name, source_id, BUCKET_TRANSFERRED,
                               detail="payload equal",
                               target_id=match.target_guid)
                continue

            # -- absent from the target: reconciliation DETECTED the loss -----
            # Only now are drop records consulted, and only to explain it.
            explained = False
            for (owner, field_name, item), recs in drops_index.items():
                if item != source_id:
                    continue
                for rec in recs:
                    if matcher is None:
                        continue
                    result = matcher.match(
                        project=project, class_name=class_name,
                        field_name=rec.field_name, reason=rec.reason,
                    )
                    consumed_drops.add(rec.identity())
                    if result.covered:
                        acc.assign(class_name, source_id,
                                   BUCKET_DROPPED_ALLOWLISTED,
                                   detail="allowlisted by %s: %s"
                                          % (result.entry.id, rec.reason))
                        explained = True
                        break
                    if result.entry is not None:
                        acc.assign(class_name, source_id, BUCKET_UNACCOUNTED,
                                   detail="%s (%s, observed %d > cap %d)"
                                          % (UNACCOUNTED_OVER_ALLOWLIST_CAP,
                                             result.entry.id, result.count_after,
                                             result.entry.max_count))
                        explained = True
                        break
                    acc.assign(class_name, source_id, BUCKET_UNACCOUNTED,
                               detail="%s: %s"
                                      % (UNACCOUNTED_DROPPED_NOT_ALLOWLISTED,
                                         rec.reason))
                    explained = True
                    break
                if explained:
                    break

            if not explained:
                # No drop record at all: the engine did not even report it.
                # FR-091's whole point -- this is invisible to a drop-led audit.
                acc.uncorroborated_absences.append((class_name, source_id))
                acc.assign(class_name, source_id, BUCKET_UNACCOUNTED,
                           detail=UNACCOUNTED_ABSENT_NO_EXPLANATION)

    if matcher is not None:
        acc.allowlist_overflows = matcher.overflows()
    acc.assert_exactly_one_bucket_each()
    return acc
