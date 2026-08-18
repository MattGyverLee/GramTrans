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

import unicodedata as _unicodedata
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


# ===========================================================================
# ===========================================================================
# PLANE 2 -- THE FIELD/LINK-LEVEL COMPARISON RULES
# (T039-T043 of specs/035-fullsweep-fidelity/tasks.md Phase 5 / US2 wave 2)
#
# FR-093 keeps this plane STRUCTURALLY SEPARATE from the object plane above.
# Nothing below reports object presence/absence, and nothing below writes into
# an ``ObjectAccounting`` block -- ``assert_object_plane_only`` guards that.
#
# Every rule here is a pure function over already-read values. Reading the
# values is ``census.py``'s job (plane 2's census); deciding what a difference
# MEANS is this section's job. Keeping the two apart is what makes the whole
# taxonomy testable without a database.
# ===========================================================================
# ===========================================================================

class FieldPlaneContractError(HarnessError):
    """A field-plane classification could not be made as specified.

    Raised rather than bucketed. S-09 and FR-097's residual rule are the same
    idea applied at two levels: an unresolvable category must never quietly
    become the empty string, because an empty category reads downstream as
    "nothing to see" and is indistinguishable from a clean result.
    """


# ---------------------------------------------------------------------------
# T039 -- WRITING-SYSTEM MAPPED LEGITIMACY (FR-069..FR-072)
# ---------------------------------------------------------------------------

#: The source alternative is carried under a mapped target writing system and
#: its text must be byte-identical there (FR-069).
WS_MAPPED = "mapped"
#: No mapping entry at all, and the run's accounting carries an explicit skip
#: record for that writing system: legitimately out of scope, NEVER loss (FR-070).
WS_OUT_OF_SCOPE = "out-of-scope"
#: The mapping DECLARED this writing system as mapped and the target lookup
#: resolved to nothing. The intent was not honored, so this is loss, not
#: expected divergence (FR-072).
WS_LOST = "lost"
#: An unmapped writing system that carries content and has NO skip record. A
#: process defect in the run's own mapping construction -- reported as its own
#: distinct finding, folded into neither LOST nor EXPECTED_DIVERGENT (FR-070).
WS_PROCESS_DEFECT = "unmapped-writing-system-with-no-skip-record"

WS_VERDICTS = (WS_MAPPED, WS_OUT_OF_SCOPE, WS_LOST, WS_PROCESS_DEFECT)


@dataclass(frozen=True)
class WritingSystemMapping:
    """FR-071: the run's writing-system mapping, covering EVERY distinct source
    writing system, vernacular and analysis alike.

    ``to_create`` is not a lesser form of ``mapped``: it records that the run
    declared an intent to carry that writing system by creating it in the
    target. Both are "declared", and FR-072 therefore applies to both -- a
    declared writing system that resolves to nothing in the target is loss.
    """

    mapped: dict            # source language tag -> target language tag
    to_create: frozenset    # source tags the run declared it will create
    skip_records: frozenset  # source tags with an explicit recorded skip

    def declares(self, source_tag: str) -> bool:
        return source_tag in self.mapped or source_tag in self.to_create

    def target_tag_for(self, source_tag: str):
        if source_tag in self.mapped:
            return self.mapped[source_tag]
        if source_tag in self.to_create:
            return source_tag
        return None

    def as_dict(self) -> dict:
        return {
            "mapped": dict(sorted(self.mapped.items())),
            "to_create": sorted(self.to_create),
            "skip_records": sorted(self.skip_records),
        }


def build_writing_system_mapping(
    source_tags,
    target_tags,
    *,
    skip_records=(),
) -> WritingSystemMapping:
    """FR-071: enumerate every distinct source writing system BEFORE any
    comparison is computed, and for each one either map it by language-tag
    identity to an existing target writing system of the same tag, or record
    that a new target writing system will be created for it.

    The narrower default this exists to refuse is the single-default-vernacular
    map: a mapping that covers one writing system and silently drops the rest
    would make every other writing system's content invisible rather than
    compared. An empty source enumeration is therefore a measurement defect --
    a project always has at least one writing system -- not an empty mapping.
    """
    src = [t for t in dict.fromkeys(source_tags or ())]
    if not src:
        raise FieldPlaneContractError(
            "[FR-071] no source writing systems were enumerated; refusing to "
            "build a mapping that would classify every alternative as "
            "out-of-scope"
        )
    tgt = frozenset(target_tags or ())
    mapped = {t: t for t in src if t in tgt}
    to_create = frozenset(t for t in src if t not in tgt)
    return WritingSystemMapping(
        mapped=mapped, to_create=to_create,
        skip_records=frozenset(skip_records or ()),
    )


def classify_writing_system(
    source_tag: str,
    *,
    mapping: WritingSystemMapping,
    target_resolves: bool,
    has_content: bool,
) -> str:
    """FR-069/FR-070/FR-072. One source writing-system alternative's verdict.

    ``target_resolves`` is whether looking the mapped target writing system up
    in the target actually yielded one -- measured, never assumed from the
    mapping, because the mapping records intent and this records outcome.
    """
    if not source_tag:
        raise FieldPlaneContractError(
            "[FR-070] a writing-system alternative with no language tag cannot "
            "be classified; the tag is the only stable identifier permitted "
            "for comparison (FR-068)"
        )
    if mapping.declares(source_tag):
        # FR-072: the mapping declared an intent to carry this content across.
        # A target lookup resolving to nothing means the intent was not
        # honored, which is loss -- explicitly NOT expected divergence.
        return WS_MAPPED if target_resolves else WS_LOST
    # Undeclared from here down.
    if source_tag in mapping.skip_records:
        return WS_OUT_OF_SCOPE
    if has_content:
        # FR-070: content under a writing system the mapping never enumerated
        # and never skipped. The defect is in the run's own mapping
        # construction, so it must not be folded into either ordinary loss or
        # expected divergence -- both would blame the data for a harness bug.
        return WS_PROCESS_DEFECT
    return WS_OUT_OF_SCOPE


# ---------------------------------------------------------------------------
# T040 -- STRING-CONTENT DISTORTION (FR-067, FR-073..FR-078)
# ---------------------------------------------------------------------------

EQUAL = "EQUAL"
DISTORTED = "DISTORTED"

#: FR-073..FR-078 subtypes. Each is reported distinctly so a reviewer can triage
#: a large, probably-benign cluster separately from genuine content bugs -- which
#: is the entire reason FR-076 insists normalization be its own subtype.
SUB_WHITESPACE = "leading-or-trailing-whitespace"
SUB_CASING = "letter-casing"
SUB_RUN_STRUCTURE = "multi-run-structure-collapsed"
SUB_NORMALIZATION = "unicode-normalization-form"
SUB_DATE_PRECISION = "approximate-date-precision"
SUB_ENUM_DECODED = "decoded-enumerated-value"
SUB_CONTENT = "content-mismatch"

DISTORTION_SUBTYPES = (
    SUB_WHITESPACE, SUB_CASING, SUB_RUN_STRUCTURE, SUB_NORMALIZATION,
    SUB_DATE_PRECISION, SUB_ENUM_DECODED, SUB_CONTENT,
)

#: The comparison kinds this dispatcher knows. An unknown kind RAISES (S-09).
KIND_TEXT = "text"
KIND_RUNS = "runs"
KIND_DATE = "date"
KIND_ENUM = "enum"
COMPARISON_KINDS = (KIND_TEXT, KIND_RUNS, KIND_DATE, KIND_ENUM)


@dataclass(frozen=True)
class DistortionResult:
    verdict: str          # EQUAL | DISTORTED
    subtype: str          # "" only when verdict is EQUAL
    source_value: object = None
    target_value: object = None

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "subtype": self.subtype,
                "source_value": self.source_value,
                "target_value": self.target_value}


def _nfc(s: str) -> str:
    return _unicodedata.normalize("NFC", s)


def _classify_text(src: str, tgt: str) -> DistortionResult:
    """FR-073/FR-074/FR-076. Order matters and is deliberate.

    Normalization is tested FIRST because it is the one difference that is
    plausibly benign at scale: two forms of the same grapheme. Testing it first
    means a normalization cluster is reported as a normalization cluster rather
    than as generic content mismatch, which is what FR-076 asks for. It cannot
    mask whitespace or casing, because neither of those becomes equal under NFC.
    """
    if src == tgt:
        return DistortionResult(EQUAL, "", src, tgt)
    ns, nt = _nfc(src), _nfc(tgt)
    if ns == nt:
        # Byte-different, canonically equal. FR-076 forbids treating these as
        # equal AND requires the distinct subtype.
        return DistortionResult(DISTORTED, SUB_NORMALIZATION, src, tgt)
    if ns.strip() == nt.strip():
        # FR-073: never benign -- this whitespace can be linguistically
        # significant in the orthographies this tool's users work in.
        return DistortionResult(DISTORTED, SUB_WHITESPACE, src, tgt)
    if ns.casefold() == nt.casefold():
        # FR-074: always DISTORTED, with no exception.
        return DistortionResult(DISTORTED, SUB_CASING, src, tgt)
    if ns.strip().casefold() == nt.strip().casefold():
        # Whitespace AND casing together. Reported as casing: it is the more
        # consequential of the two for lexical identity, and reporting one
        # subtype per finding keeps the triage buckets disjoint.
        return DistortionResult(DISTORTED, SUB_CASING, src, tgt)
    return DistortionResult(DISTORTED, SUB_CONTENT, src, tgt)


def _classify_runs(src, tgt) -> DistortionResult:
    """FR-075: a formatted multi-run field that collapses to matching plain text
    but loses its run boundaries, per-run writing system, or per-run styling is
    DISTORTED.

    Each run is ``(text, writing_system, style)``. Comparing only the
    concatenated plain text is precisely the failure this rule names, so plain
    text equality is checked only to distinguish "structure lost" from ordinary
    content mismatch -- never to pass the field.
    """
    src_runs = tuple(tuple(r) for r in (src or ()))
    tgt_runs = tuple(tuple(r) for r in (tgt or ()))
    if src_runs == tgt_runs:
        return DistortionResult(EQUAL, "", src_runs, tgt_runs)
    src_plain = "".join(str(r[0]) for r in src_runs)
    tgt_plain = "".join(str(r[0]) for r in tgt_runs)
    if src_plain == tgt_plain:
        # Same visible text, different structure: run boundaries, per-run
        # writing system, or per-run styling was lost.
        return DistortionResult(DISTORTED, SUB_RUN_STRUCTURE, src_runs, tgt_runs)
    # The text itself differs too -- fall through to the text rules so a
    # normalization or casing difference inside a formatted field is still
    # reported as that, not as generic content.
    inner = _classify_text(src_plain, tgt_plain)
    return DistortionResult(inner.verdict, inner.subtype, src_runs, tgt_runs)


def _classify_date(src, tgt) -> DistortionResult:
    """FR-077: a precision difference in an approximate date field is DISTORTED,
    because precision is itself asserted data, not formatting.

    Each side is ``(value, precision)``. A forward guard: no currently
    transferred category exposes such a field, so this rule exists to be correct
    the day one does rather than to fire today.
    """
    s_val, s_prec = (src if isinstance(src, (tuple, list)) and len(src) == 2
                     else (src, None))
    t_val, t_prec = (tgt if isinstance(tgt, (tuple, list)) and len(tgt) == 2
                     else (tgt, None))
    if s_val == t_val and s_prec == t_prec:
        return DistortionResult(EQUAL, "", src, tgt)
    if s_prec != t_prec:
        return DistortionResult(DISTORTED, SUB_DATE_PRECISION, src, tgt)
    return DistortionResult(DISTORTED, SUB_CONTENT, src, tgt)


def _classify_enum(src, tgt, decode) -> DistortionResult:
    """FR-078 (and FR-067 for a phonological rule's direction-of-application):
    DISTORTED only when the DECODED semantic value differs -- never merely
    because the raw stored integer differs.

    Both sides are decoded, defensively against cross-version ordinal drift:
    decoding only one side would silently compare an integer against a name.
    """
    if decode is None:
        raise FieldPlaneContractError(
            "[FR-078] an enumerated value cannot be classified without a "
            "decoder; comparing raw stored integers is exactly what this rule "
            "forbids, because the ordinals may drift across host versions"
        )
    ds, dt = decode(src), decode(tgt)
    if ds is None or dt is None:
        raise FieldPlaneContractError(
            "[FR-078] the enumerated value decoder returned no semantic value "
            "for %r / %r; an undecodable ordinal must be reported, not compared "
            "as a raw integer" % (src, tgt)
        )
    if ds == dt:
        # Raw ints may well differ here. That is the point: FR-078 says a raw
        # difference with an equal decoded value is NOT a distortion.
        return DistortionResult(EQUAL, "", ds, dt)
    return DistortionResult(DISTORTED, SUB_ENUM_DECODED, ds, dt)


def classify_distortion(src, tgt, *, kind: str = KIND_TEXT, decode=None
                        ) -> DistortionResult:
    """The FR-073..FR-078 dispatcher.

    An unrecognized ``kind`` RAISES rather than bucketing to ``""`` (S-09): a
    category that quietly becomes the empty string is indistinguishable
    downstream from a clean result, which is the silence this feature replaces.
    """
    if kind == KIND_TEXT:
        if not isinstance(src, str) or not isinstance(tgt, str):
            raise FieldPlaneContractError(
                "[S-09] text comparison received non-text values (%r / %r); "
                "refusing to coerce -- the caller must name the right kind"
                % (type(src).__name__, type(tgt).__name__)
            )
        return _classify_text(src, tgt)
    if kind == KIND_RUNS:
        return _classify_runs(src, tgt)
    if kind == KIND_DATE:
        return _classify_date(src, tgt)
    if kind == KIND_ENUM:
        return _classify_enum(src, tgt, decode)
    raise FieldPlaneContractError(
        "[S-09] unresolvable comparison kind %r; the legal kinds are %s. An "
        "unresolvable category MUST raise rather than bucket to an empty "
        "category" % (kind, ", ".join(COMPARISON_KINDS))
    )


def compare_ws_alternatives(source_alts, target_alts, *, mapping,
                            target_resolves=None) -> list:
    """FR-069: for every source writing-system alternative that has a mapping
    entry, that alternative's text must appear BYTE-IDENTICAL under the
    mapping's target writing system.

    ``source_alts`` / ``target_alts`` are ``{language_tag: text}``. Returns one
    finding dict per source alternative -- including the legitimately
    out-of-scope ones, because an alternative that produced no finding at all is
    indistinguishable from one that was never looked at.
    """
    resolves = (target_resolves if target_resolves is not None
                else (lambda tag: tag in (target_alts or {})))
    findings = []
    for tag in sorted(source_alts or {}):
        text = (source_alts or {})[tag]
        ws_verdict = classify_writing_system(
            tag, mapping=mapping, target_resolves=bool(resolves(tag)),
            has_content=bool(text),
        )
        row = {"writing_system": tag, "ws_verdict": ws_verdict}
        if ws_verdict == WS_MAPPED:
            tgt_tag = mapping.target_tag_for(tag)
            # FR-069 says byte-identical, so this is an exact comparison and
            # the distortion subtypes below describe HOW it failed.
            d = classify_distortion(text, (target_alts or {}).get(tgt_tag, ""),
                                    kind=KIND_TEXT)
            row.update({"target_writing_system": tgt_tag,
                        "verdict": d.verdict, "subtype": d.subtype})
        findings.append(row)
    return findings


# ---------------------------------------------------------------------------
# T041 -- ORDER SEMANTICS (FR-079..FR-084)
# ---------------------------------------------------------------------------

ORDER_ASSERTED = "ordered"
ORDER_NOT_ASSERTED = "unordered"
ORDER_EXCLUDED = "not-asserted-by-design"

#: FR-082 -- order-critical OWNED sequences. Scrambling any of these fails.
ORDER_CRITICAL_OWNED = (
    ("LexEntry", "SensesOS"),
    ("WfiAnalysis", "MorphBundlesOS"),
    ("StTxtPara", "SegmentsOS"),
    ("LexEntry", "AlternateFormsOS"),
)

#: FR-083 -- order-critical REFERENCE sequences. Scrambling any of these fails.
ORDER_CRITICAL_REFERENCE = (
    ("MoInflAffixTemplate", "PrefixSlotsRS"),
    ("MoInflAffixTemplate", "SuffixSlotsRS"),
    ("LexEntryRef", "ComponentLexemesRS"),
    ("LexEntryRef", "PrimaryLexemesRS"),
)

#: FR-081 -- a wordform's competing analyses are unordered BY DESIGN, so
#: re-ordering them across a transfer is expected and benign.
UNORDERED_BY_DESIGN = (
    ("WfiWordform", "AnalysesOC"),
)

#: FR-084 -- cross-entry iteration order across unrelated top-level entries is
#: not asserted at all: the host exposes entries through a surface with no
#: author-assigned cross-entry order. Distinct from "unordered" because there is
#: no membership claim to make either.
ORDER_NOT_ASSERTED_FIELDS = (
    ("LexDb", "Entries"),
    ("LangProject", "LexDbOA.Entries"),
)


def order_significance(class_name: str, field_name: str) -> str:
    """FR-079/FR-080: derive order-significance from the tool's OWN existing
    ordered-versus-unordered field classification, never re-derived per class.

    That classification is the accessor-suffix convention the whole codebase
    already relies on: ``OS``/``RS`` are sequences (ordered), ``OC``/``RC`` are
    collections (unordered). Re-deriving per class is what FR-079 forbids, so
    the explicit rosters above exist only to name the FR-081/FR-082/FR-083/
    FR-084 cases the suffix cannot express -- never to override it.
    """
    key = (class_name, field_name)
    if key in ORDER_NOT_ASSERTED_FIELDS:
        return ORDER_EXCLUDED
    if key in UNORDERED_BY_DESIGN:
        return ORDER_NOT_ASSERTED
    if key in ORDER_CRITICAL_OWNED or key in ORDER_CRITICAL_REFERENCE:
        return ORDER_ASSERTED
    if field_name.endswith("OS") or field_name.endswith("RS"):
        return ORDER_ASSERTED
    if field_name.endswith("OC") or field_name.endswith("RC"):
        return ORDER_NOT_ASSERTED
    raise FieldPlaneContractError(
        "[FR-079] cannot determine order significance for %s.%s from the "
        "tool's own ordered/unordered classification; refusing to guess, "
        "because guessing 'unordered' would silently stop asserting order"
        % (class_name, field_name)
    )


@dataclass(frozen=True)
class OrderResult:
    class_name: str
    field_name: str
    significance: str
    passed: bool
    reason: str = ""
    missing: tuple = ()
    extra: tuple = ()

    def as_dict(self) -> dict:
        return {"class": self.class_name, "field": self.field_name,
                "significance": self.significance, "passed": self.passed,
                "reason": self.reason, "missing": list(self.missing),
                "extra": list(self.extra)}


def compare_order(class_name: str, field_name: str, source_seq, target_seq,
                  *, significance: Optional[str] = None) -> OrderResult:
    """FR-079..FR-084.

    * ordered      -- the sequence itself is compared; a scramble FAILS even
                      when membership is identical (FR-082/FR-083).
    * unordered    -- ONLY set membership is compared; a positional difference
                      is benign (FR-080/FR-081).
    * not-asserted -- neither order nor membership is asserted (FR-084).
    """
    sig = significance or order_significance(class_name, field_name)
    src = tuple(source_seq or ())
    tgt = tuple(target_seq or ())
    if sig == ORDER_EXCLUDED:
        return OrderResult(class_name, field_name, sig, True,
                           reason="cross-entry order is not asserted (FR-084)")
    missing = tuple(x for x in src if x not in set(tgt))
    extra = tuple(x for x in tgt if x not in set(src))
    if missing or extra:
        return OrderResult(class_name, field_name, sig, False,
                           reason="set membership differs", missing=missing,
                           extra=extra)
    if sig == ORDER_NOT_ASSERTED:
        # Membership matches and order is not part of faithfulness here.
        return OrderResult(class_name, field_name, sig, True,
                           reason="unordered collection; positional difference "
                                  "is benign by design")
    if src != tgt:
        return OrderResult(class_name, field_name, sig, False,
                           reason="ordered sequence scrambled: membership is "
                                  "identical but position is not")
    return OrderResult(class_name, field_name, sig, True)


# ---------------------------------------------------------------------------
# T042 -- LINK CLASSIFICATION, EXACTLY FIVE VERDICTS (FR-085..FR-090)
# ---------------------------------------------------------------------------

LINK_RESOLVED = "RESOLVED"
LINK_DANGLING = "DANGLING"
LINK_SILENTLY_UNSET = "SILENTLY_UNSET"
LINK_LOST_BUT_ACCOUNTED = "LOST-BUT-ACCOUNTED"
LINK_RESOLVED_BY_EQUIVALENCE = "RESOLVED-BY-EQUIVALENCE"

LINK_VERDICTS = (LINK_RESOLVED, LINK_DANGLING, LINK_SILENTLY_UNSET,
                 LINK_LOST_BUT_ACCOUNTED, LINK_RESOLVED_BY_EQUIVALENCE)

#: FR-090: the ONLY basis for RESOLVED-BY-EQUIVALENCE is a class carrying no
#: stable per-instance identifier at all. This is deliberately NOT the
#: natural-key basis of FR-185, and must never be used to widen it.
NO_STABLE_IDENTIFIER_CLASSES = frozenset({"FieldDescription"})


@dataclass(frozen=True)
class LinkResult:
    verdict: str
    basis: str
    class_name: str = ""
    field_name: str = ""
    source_referent: Optional[str] = None
    target_referent: Optional[str] = None

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "basis": self.basis,
                "class": self.class_name, "field": self.field_name,
                "source_referent": self.source_referent,
                "target_referent": self.target_referent}


def classify_link(
    *,
    class_name: str,
    field_name: str,
    source_referent,
    target_referent,
    has_accounting_record: bool = False,
    natural_key_roster=None,
    remap_record=None,
    equivalence_match=None,
) -> LinkResult:
    """FR-085..FR-090. Exactly five verdicts, and no sixth.

    Null-or-empty target, in order:
      * source also had nothing        -> RESOLVED, vacuously; there was no
                                          referent to carry.
      * source had one, record exists  -> LOST-BUT-ACCOUNTED (FR-088), the
                                          milder verdict, never conflated with
                                          SILENTLY_UNSET or with a clean pass.
      * source had one, no record      -> SILENTLY_UNSET (FR-087), higher
                                          severity than an accounted-for gap.

    Non-null target:
      * class on the natural-key roster -> resolution proceeds THROUGH the run's
        recorded identity-remap record and NEVER by direct identifier comparison
        (FR-085/FR-086 as amended). The comparator must not re-guess the
        correspondence itself.
      * identifiers equal -> RESOLVED (FR-085), regardless of whether the target
        object was created by this run or shipped with a freshly created target
        from the host's project-creation template (FR-089). Never inferred from
        "the run must have created it".
      * class carries no stable per-instance identifier and owner+name
        equivalence matches -> RESOLVED-BY-EQUIVALENCE (FR-090).
      * otherwise -> DANGLING (FR-086), always a hard failure, never benign.
    """
    if not class_name:
        raise FieldPlaneContractError(
            "[FR-090] a link cannot be classified without its owning class; "
            "the roster checks below are per class"
        )

    if not target_referent:
        if not source_referent:
            return LinkResult(LINK_RESOLVED, "no referent on either side",
                              class_name, field_name, source_referent,
                              target_referent)
        if has_accounting_record:
            return LinkResult(LINK_LOST_BUT_ACCOUNTED,
                              "null target with a matching drop/skip record "
                              "for this owner/field/item (FR-088)",
                              class_name, field_name, source_referent,
                              target_referent)
        return LinkResult(LINK_SILENTLY_UNSET,
                          "null target, source had a referent, and NO record "
                          "exists for this owner/field/item (FR-087)",
                          class_name, field_name, source_referent,
                          target_referent)

    on_natural_key_roster = bool(
        natural_key_roster is not None
        and getattr(natural_key_roster, "admits", None) is not None
        and natural_key_roster.admits(class_name)
    )

    if on_natural_key_roster:
        # FR-085/FR-086 as amended: for such a class, identifier comparison is
        # FORBIDDEN as the basis. The remap record is the only admissible one.
        if remap_record is None:
            raise FieldPlaneContractError(
                "[FR-085] class %r is on the natural-key identity roster, so "
                "its links MUST resolve through the run's recorded "
                "identity-remap record -- and no record was supplied. Falling "
                "back to identifier comparison is explicitly forbidden here"
                % (class_name,)
            )
        expected = None
        lookup = getattr(remap_record, "target_for", None)
        if callable(lookup):
            expected = lookup(class_name, source_referent)
        if expected is not None and expected == target_referent:
            return LinkResult(LINK_RESOLVED,
                              "matched through the recorded identity-remap "
                              "record (FR-185/FR-187 natural-key basis)",
                              class_name, field_name, source_referent,
                              target_referent)
        if source_referent == target_referent:
            # Identity is authoritative and the natural key is the fallback,
            # never the reverse (FR-186) -- so an identifier match still
            # resolves even for a roster class.
            return LinkResult(LINK_RESOLVED,
                              "identifiers equal (FR-186: identity remains "
                              "authoritative for a roster class)",
                              class_name, field_name, source_referent,
                              target_referent)
        return LinkResult(LINK_DANGLING,
                          "matched neither the recorded identity-remap record "
                          "nor the source identifier (FR-086 as amended)",
                          class_name, field_name, source_referent,
                          target_referent)

    if source_referent == target_referent:
        return LinkResult(LINK_RESOLVED,
                          "referent identifiers equal (FR-085; FR-089 makes "
                          "this hold for a catalog/seed entry the target "
                          "shipped with)",
                          class_name, field_name, source_referent,
                          target_referent)

    if equivalence_match:
        # FR-090: admissible ONLY for a class with no stable per-instance
        # identifier. Firing it for a class that normally carries one is a
        # harness error that must name the class.
        if class_name not in NO_STABLE_IDENTIFIER_CLASSES:
            raise FieldPlaneContractError(
                "[FR-090] RESOLVED-BY-EQUIVALENCE fired for class %r, which "
                "normally carries a stable per-instance identifier. This basis "
                "is admissible only for a class that carries none, and MUST "
                "NOT be used as a fallback -- nor conflated with the FR-185 "
                "natural-key basis" % (class_name,)
            )
        return LinkResult(LINK_RESOLVED_BY_EQUIVALENCE,
                          "owner-and-name equivalence, the same basis the "
                          "engine's own de-duplication uses for this class "
                          "(FR-090)",
                          class_name, field_name, source_referent,
                          target_referent)

    return LinkResult(LINK_DANGLING,
                      "non-null target whose identifier does not match the "
                      "source referent under RESOLVED or "
                      "RESOLVED-BY-EQUIVALENCE (FR-086)",
                      class_name, field_name, source_referent, target_referent)


# ---------------------------------------------------------------------------
# T043 -- STRUCTURAL DEPTH AND PER-PARENT DEGREE (FR-189, SC-017)
# ---------------------------------------------------------------------------

DEPTH_NOT_EVALUATED = "NOT-EVALUATED"

#: FR-189: classes whose objects may own further objects of the SAME class.
SAME_CLASS_NESTING_CLASSES = (
    "LexSense",          # sub-senses
    "ReversalIndexEntry",  # reversal sub-entries
    "CmPossibility",     # possibility sub-items
    "CmSemanticDomain",  # semantic-domain sub-items
    "PartOfSpeech",      # category sub-items
)


def measure_max_depth(children_of, root_ids, *, _seen=None) -> int:
    """FR-189: enumerate children RECURSIVELY at every node until no further
    children exist there -- never to a fixed or assumed depth.

    ``children_of`` maps a parent id to its direct children ids. Depth counts
    nodes, so a flat set of roots is depth 1 and a root with one child is 2.
    An empty root set is depth 0.

    A cycle would make "until no further children exist" non-terminating, so it
    raises: a cyclic ownership graph is a defect in the measurement's input, and
    silently truncating the walk is the exact self-hiding failure FR-189 exists
    to catch.
    """
    seen = set() if _seen is None else _seen
    best = 0
    for rid in root_ids or ():
        if rid in seen:
            raise FieldPlaneContractError(
                "[FR-189] ownership cycle reached at %r; the recursive walk "
                "cannot terminate, and truncating it would report a shallower "
                "depth than the data actually has" % (rid,)
            )
        kids = (children_of or {}).get(rid) or ()
        best = max(best, 1 + measure_max_depth(children_of, kids,
                                               _seen=seen | {rid}))
    return best


@dataclass(frozen=True)
class StructuralDepthResult:
    class_name: str
    source_max_depth: int
    target_max_depth: int
    degree_mismatches: tuple      # ((parent_id, src_count, tgt_count), ...)
    parents_compared: int
    evaluated: bool
    verdict: str
    reason: str = ""

    @property
    def clean(self) -> bool:
        return self.evaluated and self.verdict == EQUAL

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "source_max_depth": self.source_max_depth,
            "target_max_depth": self.target_max_depth,
            "parents_compared": self.parents_compared,
            "degree_mismatches": [
                {"parent": p, "source_children": s, "target_children": t}
                for p, s, t in self.degree_mismatches
            ],
            "evaluated": self.evaluated,
            "verdict": self.verdict,
            "reason": self.reason,
        }


def compare_structural_depth(
    class_name: str,
    *,
    source_children,
    target_children,
    source_roots,
    target_roots,
    matched_parents=None,
    nesting_available_in_corpus: bool = True,
) -> StructuralDepthResult:
    """FR-189 / SC-017. Two INDEPENDENT signals, recorded per class and per side.

    1. Per-side maximum nesting depth actually reached. A target-side maximum
       lower than the source-side maximum is VACUOUS for that class -- not a
       milder failure, because it means the comparator's own recursion may have
       stopped early and every object it did visit compared perfectly.
    2. Per-matched-parent direct-child COUNT. A disagreement FAILS the run even
       when every child actually visited compared clean.

    FR-189 also forbids treating this as satisfied by the ordered-sequence
    comparisons of FR-059/FR-079/FR-082/FR-083: those establish degree for
    ordered fields but cannot observe a level the walk never reached.

    Where the corpus has no project exhibiting nesting deeper than one level for
    this class, the result is NOT-EVALUATED -- never clean.
    """
    src_depth = measure_max_depth(source_children, source_roots)
    tgt_depth = measure_max_depth(target_children, target_roots)

    parents = (list(matched_parents) if matched_parents is not None
               else sorted(set(source_children or {}) & set(target_children or {})))
    mismatches = []
    for p in parents:
        s = len((source_children or {}).get(p) or ())
        t = len((target_children or {}).get(p) or ())
        if s != t:
            mismatches.append((p, s, t))
    mismatches = tuple(mismatches)

    if not nesting_available_in_corpus or src_depth <= 1:
        # FR-189's closing clause: no project exhibits same-class nesting deeper
        # than one level for this class, so its depth behavior is unmeasured.
        # Reporting clean here would claim evidence the corpus cannot supply.
        return StructuralDepthResult(
            class_name, src_depth, tgt_depth, mismatches, len(parents),
            evaluated=False, verdict=DEPTH_NOT_EVALUATED,
            reason=("no project in the corpus exhibits same-class nesting "
                    "deeper than one level for this class; depth behavior is "
                    "NOT-EVALUATED and MUST NOT be reported clean"),
        )

    if tgt_depth < src_depth:
        return StructuralDepthResult(
            class_name, src_depth, tgt_depth, mismatches, len(parents),
            evaluated=True, verdict="VACUOUS",
            reason=("target-side maximum depth %d is lower than source-side %d; "
                    "the comparator's own recursion may have stopped early, so "
                    "every per-object comparison above is not evidence"
                    % (tgt_depth, src_depth)),
        )

    if mismatches:
        return StructuralDepthResult(
            class_name, src_depth, tgt_depth, mismatches, len(parents),
            evaluated=True, verdict=DISTORTED,
            reason=("%d matched parent(s) disagree on direct-child count; this "
                    "fails the run even though every child actually visited "
                    "compared clean" % (len(mismatches),)),
        )

    return StructuralDepthResult(
        class_name, src_depth, tgt_depth, mismatches, len(parents),
        evaluated=True, verdict=EQUAL,
    )
