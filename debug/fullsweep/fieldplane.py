"""Feature 035 -- T045a(c): THE FIELD PLANE, WIRED.

T045d built the live ``field_source(cls, guid)`` reader. T045e built the
class -> category join. T045f gave plane 2 a home on the artifact. Nothing
CALLED any of them: ``run_one_project`` still handed ``reconcile_objects``
the honest no-op comparator ``payload_never_compared``, so every matched
object landed in ``unaccounted`` as
"present-under-matching-identity-but-never-compared", and
``RunContext.comparisons`` / ``measured_categories`` stayed ``None`` --
``COMPARISONS-PERFORMED`` and ``CATEGORY-COVERAGE`` therefore reported
``not-evaluated`` and FR-109 sank the run to ``VACUOUS``.

This module is the missing middle: it reads both projects' field censuses,
compares a matched pair of objects field by field through the T039-T043
rules, and accumulates exactly the four things the artifact and the guards
need -- the per-class comparison counters, the value findings, the link
findings, and the per-class nesting measurements.

WHAT DECIDES WHICH RULE APPLIES (and why it is measured, not assumed)
----------------------------------------------------------------------
``GetSyncableProperties`` returns a plain dict whose VALUES carry no type
tag. The rule is therefore chosen from the value's SHAPE, against a closed
vocabulary (``VALUE_KINDS``), with two measured discriminators rather than
two guesses:

1. A ``dict`` is a MULTISTRING only when every one of its keys names a
   writing system OF THE PROJECT IT CAME FROM. Measured live 2026-09-19:
   ``MoStemMsa.MsFeatures`` is ``{'TypeGuid': ..., 'specs': [...]}`` -- a
   dict that is not a multistring at all. Classifying it as one would
   compare a feature structure as if ``specs`` were a language tag.

2. A multistring's keys are NOT always language tags. Measured live on
   ``Ejagham Mini``: ``PartOfSpeech.Name`` is ``{'en': ...}`` (tag-keyed)
   while ``CmPossibility.Name``, ``LexEntryType.Name``,
   ``LexEntryInflType.Name``, ``LexRefType.Name`` and ``MoMorphType.Name``
   are ``{'999000001': ..., '999000003': ...}`` (HANDLE-keyed, via
   ``PossibilityItemOperations``). A writing-system handle is per-project
   and NOT portable -- ``tests/integration/harness/full_run.py`` records the
   measurement that ``999000002`` is ``en`` in ``Ngoreme FLEx`` and ``ngq``
   in ``Ngoreme Target``. Comparing two projects' handle-keyed dicts
   directly would compare unrelated writing systems and call the result
   fidelity. So every multistring is normalized to LANGUAGE TAGS, through
   the handle map OF ITS OWN PROJECT, before any comparison happens
   (FR-068: the tag is the only stable identifier permitted for comparison).

WHAT IS REFUSED RATHER THAN GUESSED
-------------------------------------
* A raw ``int`` whose field is not on ``NUMERIC_INT_FIELDS`` is NOT
  compared. FR-078 forbids comparing a stored enumerated ordinal, and no
  decoder exists for these fields; comparing them as numbers is exactly the
  cross-version ordinal drift that rule names. The field is recorded as
  not-compared WITH ITS REASON and is visible on the artifact, instead of
  being compared wrongly or dropped silently.
* A value shape outside ``VALUE_KINDS`` produces a finding, not a pass. An
  unknown shape means the comparator did not establish equality, and
  "we could not tell" must never read as "they matched".
* A class whose ``GetSyncableProperties`` raises live (ten of them do -- see
  ``field_dispatch``'s "OTHER LIVE DEFECTS") is recorded per class as
  unreadable and lands in the coverage report's unmeasured bucket. It never
  aborts the sweep and never reports clean.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field as _dc_field
from typing import Callable, Mapping, Optional

from .moves import HarnessError
from .compare import (
    DISTORTED, EQUAL, KIND_TEXT, LINK_RESOLVED, LINK_RESOLVED_BY_EQUIVALENCE,
    ORDER_NOT_ASSERTED, SUB_CONTENT, WS_MAPPED, WS_OUT_OF_SCOPE,
    FieldPlaneContractError, classify_distortion, classify_link, compare_order,
    compare_ws_alternatives,
)

__all__ = [
    "GUID_RE",
    "RULE_WS", "RULE_TEXT", "RULE_LINK", "RULE_ORDER", "RULE_SCALAR",
    "RULE_STRUCTURE", "RULE_SHAPE", "RULE_UNCLASSIFIED", "RULES",
    "KIND_NULL", "KIND_SCALAR", "KIND_TEXT_VALUE", "KIND_REFERENCE",
    "KIND_MULTISTRING", "KIND_REFERENCE_SEQUENCE", "KIND_SCALAR_SET",
    "KIND_STRUCTURE", "KIND_STRUCTURE_SEQUENCE", "KIND_UNKNOWN", "VALUE_KINDS",
    "NUMERIC_INT_FIELDS", "VERDICT_TARGET_ONLY", "VERDICT_SHAPE_MISMATCH",
    "VERDICT_UNCLASSIFIED",
    "NOT_COMPARED_UNDECLARED_INT", "NOT_COMPARED_NO_REMAP_RECORD",
    "NOT_COMPARED_UNRESOLVED_HANDLE", "NOT_COMPARED_RULE_REFUSED",
    "FieldComparison", "jsonable", "looks_like_guid", "normalize_multistring",
    "classify_value_kind", "compare_field", "FieldPlaneComparator",
    "SUB_ABSENT", "WS_MODE_FULL", "WS_MODE_DEFAULT_VERNACULAR", "WS_MODES",
    "FieldPlaneSide", "open_project_readonly", "gather_field_plane_side",
    "build_ws_mapping_for_mode", "depth_results",
]


#: A canonical LCM GUID as every census in this feature spells it (lowercased
#: by ``census_project`` / ``audit_guid_preservation.inventory_all``).
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# ---------------------------------------------------------------------------
# THE CLOSED RULE VOCABULARY
# ---------------------------------------------------------------------------
# One token per comparison rule, recorded on every comparison. The artifact's
# ``comparisons`` block counts PERFORMED comparisons per class per rule --
# contracts/artifact-schema.md's { "rule": ..., "performed": n, "findings": n }
# -- because "zero findings" and "never looked" are the same number of
# findings and FR-137 forbids reporting them alike.

RULE_WS = "ws-alternatives"          # T039/FR-069..FR-072
RULE_TEXT = "text"                   # T040/FR-073..FR-078
RULE_LINK = "link"                   # T042/FR-085..FR-090
RULE_ORDER = "order"                 # T041/FR-079..FR-084
RULE_SCALAR = "scalar"               # a bool or a declared-numeric int
RULE_STRUCTURE = "structure"         # a nested owned record (e.g. TranslationsOC)
RULE_SHAPE = "shape"                 # the two sides are not the same kind of thing
RULE_UNCLASSIFIED = "unclassified-shape"

RULES: tuple = (
    RULE_WS, RULE_TEXT, RULE_LINK, RULE_ORDER, RULE_SCALAR, RULE_STRUCTURE,
    RULE_SHAPE, RULE_UNCLASSIFIED,
)

# ---------------------------------------------------------------------------
# THE CLOSED VALUE-SHAPE VOCABULARY
# ---------------------------------------------------------------------------

KIND_NULL = "null"
KIND_SCALAR = "scalar"
KIND_TEXT_VALUE = "text"
KIND_REFERENCE = "reference"
KIND_MULTISTRING = "multistring"
KIND_REFERENCE_SEQUENCE = "reference-sequence"
KIND_SCALAR_SET = "scalar-set"
KIND_STRUCTURE = "structure"
KIND_STRUCTURE_SEQUENCE = "structure-sequence"
KIND_UNKNOWN = "unknown"

VALUE_KINDS: tuple = (
    KIND_NULL, KIND_SCALAR, KIND_TEXT_VALUE, KIND_REFERENCE, KIND_MULTISTRING,
    KIND_REFERENCE_SEQUENCE, KIND_SCALAR_SET, KIND_STRUCTURE,
    KIND_STRUCTURE_SEQUENCE, KIND_UNKNOWN,
)

#: The source had nothing and the target has something. NOT loss, and
#: therefore not a finding at the field plane -- FR-089 makes a value the
#: target shipped with legitimate. It is counted and published so that a
#: reader can see it, because an addition nobody prints is indistinguishable
#: from no addition; deciding whether any of them are tool-owned duplicates
#: is FR-102/FR-183's reverse walk, which is T045b's object-plane work.
VERDICT_TARGET_ONLY = "TARGET-ONLY"

#: The two sides are not the same kind of thing at all (e.g. the source
#: carries a multistring and the target carries a bare GUID). Always a
#: finding: whatever happened, the field did not arrive as itself.
VERDICT_SHAPE_MISMATCH = "SHAPE-MISMATCH"

#: The value's shape is outside ``VALUE_KINDS``. A finding, never a pass --
#: the comparator did not establish equality, and an unmeasurable field
#: reported as clean is the exact defect this feature exists to remove.
VERDICT_UNCLASSIFIED = "UNCLASSIFIED-SHAPE"

#: ``class.field`` entries whose stored integer is a COUNT or an ORDINAL
#: POSITION -- a number whose arithmetic meaning is the same in every host
#: version -- and therefore may be compared directly.
#:
#: Everything else that arrives as a bare ``int`` is treated as a stored
#: ENUMERATED value and is NOT compared (FR-078). This roster is deliberately
#: tiny and explicit: adding a field here is a claim that its integer is not
#: an enum ordinal, and that claim should be made deliberately, in a diff,
#: rather than inferred by a heuristic at runtime.
NUMERIC_INT_FIELDS: frozenset = frozenset({
    "LexEntry.HomographNumber",
})

NOT_COMPARED_UNDECLARED_INT = (
    "[FR-078] the value is a stored integer and the field is not declared "
    "numeric; no decoder exists, and comparing the raw ordinal is what FR-078 "
    "forbids (host versions may renumber it). Add it to NUMERIC_INT_FIELDS "
    "deliberately, or supply a decoder"
)
NOT_COMPARED_NO_REMAP_RECORD = (
    "[FR-085] the owning class is on the natural-key identity roster, so its "
    "links may resolve ONLY through the run's recorded identity-remap record "
    "-- and this run produced none. Identifier comparison is explicitly "
    "forbidden here, so the link is left unclassified rather than guessed"
)
NOT_COMPARED_UNRESOLVED_HANDLE = (
    "[FR-068] a writing-system HANDLE in this multistring could not be "
    "resolved to a language tag in its own project. A handle is per-project "
    "and not portable, so comparing it across projects would compare "
    "unrelated writing systems"
)


def jsonable(value):
    """Coerce a census value into something ``json.dumps`` accepts, WITHOUT
    letting ``flush_artifact``'s ``default=str`` turn an object into a repr
    string that reads like evidence (T045f ruling 2).

    Sets and tuples become sorted/plain lists because that is what they mean.
    Anything genuinely outside JSON becomes an explicit
    ``{"unserializable": ..., "repr": ...}`` marker -- visibly not a value.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return {"unserializable": type(value).__name__, "repr": repr(value)[:200]}


def looks_like_guid(value) -> bool:
    """True for a canonical GUID string. Used as the FIRST discriminator for a
    reference, ahead of the field NAME: measured live, ``PhonemeGuids`` (a
    list of GUIDs), ``MorphTypeRA`` and ``InflFeatsGuid`` (bare GUIDs) and
    ``TranslationsOC`` (a list of nested RECORDS, despite the owning-sequence
    suffix) all disagree with what their names suggest."""
    return isinstance(value, str) and bool(GUID_RE.match(value))


def normalize_multistring(value, handle_to_tag) -> tuple:
    """Return ``(tag_keyed_dict, unresolved_handles)``.

    A key that is already a language tag passes through. A key that is a
    writing-system HANDLE is translated through ITS OWN PROJECT's handle map.
    An unresolvable handle is NOT dropped and NOT passed through: it is
    returned in ``unresolved_handles`` so the caller records the field as
    not-compared with a reason (FR-068), because a handle compared across
    projects is a comparison of two different writing systems.
    """
    out: dict = {}
    unresolved: list = []
    for key, text in (value or {}).items():
        skey = str(key)
        if skey.isdigit():
            tag = (handle_to_tag or {}).get(skey)
            if not tag:
                unresolved.append(skey)
                continue
            out[tag] = text
        else:
            out[skey] = text
    return out, sorted(unresolved)


def classify_value_kind(value, *, ws_keys) -> str:
    """Name a census value's shape, from the closed ``VALUE_KINDS`` vocabulary.

    ``ws_keys`` is the set of writing-system keys (language tags AND handle
    strings) of the project this value came from -- the measured discriminator
    that separates a multistring from a structured dict.
    """
    keys = frozenset(str(k) for k in (ws_keys or ()))
    if value is None:
        return KIND_NULL
    if isinstance(value, bool) or isinstance(value, int):
        return KIND_SCALAR
    if isinstance(value, str):
        return KIND_REFERENCE if looks_like_guid(value) else KIND_TEXT_VALUE
    if isinstance(value, Mapping):
        if not value:
            # Ambiguous on its own (an empty multistring and an empty
            # structure look identical); resolved by the counterpart in
            # ``compare_field``, and equal to another empty dict either way.
            return KIND_MULTISTRING
        # A digit key is a writing-system HANDLE by construction -- no
        # structured syncable property uses one. Accepting it here even when
        # the project's own enumeration did not carry it is what makes the
        # FR-068 refusal reachable: the alternative is to call it a structure,
        # compare it as one, and report a handle difference as a content
        # difference.
        if all(str(k) in keys or str(k).isdigit() for k in value):
            return KIND_MULTISTRING
        return KIND_STRUCTURE
    if isinstance(value, (set, frozenset)):
        return KIND_SCALAR_SET
    if isinstance(value, (list, tuple)):
        if not value:
            return KIND_REFERENCE_SEQUENCE
        if all(looks_like_guid(v) for v in value):
            return KIND_REFERENCE_SEQUENCE
        if all(isinstance(v, Mapping) for v in value):
            return KIND_STRUCTURE_SEQUENCE
        if all(isinstance(v, (str, int, float, bool)) for v in value):
            return KIND_SCALAR_SET
        return KIND_UNKNOWN
    return KIND_UNKNOWN


@dataclass(frozen=True)
class FieldComparison:
    """One field of one matched object pair, judged by exactly one rule.

    ``performed`` is the load-bearing flag: a comparison that was REFUSED
    (an undeclared integer, an unresolvable writing-system handle, a roster
    class with no remap record) is recorded with ``performed=False`` and a
    ``reason``, and is counted separately from both a pass and a finding.
    That is the distinction FR-137 exists to keep.
    """
    class_name: str
    field_name: str
    rule: str
    verdict: str
    performed: bool = True
    subtype: str = ""
    reason: str = ""
    source_value: object = None
    target_value: object = None
    detail: dict = _dc_field(default_factory=dict)

    @property
    def is_finding(self) -> bool:
        """A performed comparison whose verdict is not one of the passing
        ones. ``VERDICT_TARGET_ONLY`` passes: a value the target carries and
        the source never had is not loss (FR-089)."""
        return self.performed and self.verdict not in (
            EQUAL, LINK_RESOLVED, LINK_RESOLVED_BY_EQUIVALENCE,
            VERDICT_TARGET_ONLY,
        )

    def as_dict(self) -> dict:
        return {
            "class": self.class_name,
            "field": self.field_name,
            "rule": self.rule,
            "verdict": self.verdict,
            "performed": self.performed,
            "subtype": self.subtype,
            "reason": self.reason,
            "source_value": jsonable(self.source_value),
            "target_value": jsonable(self.target_value),
            "detail": jsonable(self.detail),
        }


#: A value the source carries and the target does not. Its own subtype so a
#: reader can separate "arrived wrong" from "did not arrive".
SUB_ABSENT = "absent-from-target"


def _reconcile_kinds(src_kind: str, tgt_kind: str, src, tgt) -> str:
    """Decide the ONE kind a pair is compared under, or return ``RULE_SHAPE``
    when the two sides are not the same kind of thing.

    The empty-container cases are resolved in favour of the non-empty side:
    an empty ``dict`` cannot tell a multistring from a structure, and an
    empty ``list`` cannot tell a reference sequence from a record sequence.
    Calling either one a shape mismatch would report a difference that the
    data does not contain.
    """
    if src_kind == tgt_kind:
        return src_kind
    pair = {src_kind, tgt_kind}
    empty_src = isinstance(src, (Mapping, list, tuple, set, frozenset)) and not src
    empty_tgt = isinstance(tgt, (Mapping, list, tuple, set, frozenset)) and not tgt
    if empty_src or empty_tgt:
        if pair <= {KIND_MULTISTRING, KIND_STRUCTURE}:
            return KIND_STRUCTURE if KIND_STRUCTURE in pair else KIND_MULTISTRING
        if pair <= {KIND_REFERENCE_SEQUENCE, KIND_STRUCTURE_SEQUENCE, KIND_SCALAR_SET}:
            for candidate in (KIND_STRUCTURE_SEQUENCE, KIND_SCALAR_SET,
                              KIND_REFERENCE_SEQUENCE):
                if candidate in pair:
                    return candidate
    return RULE_SHAPE


def _structure_key(record) -> Optional[str]:
    """A nested record's own identity, when it carries one. Measured live:
    ``FsClosedFeature.Values`` rows carry ``Guid``; ``LexExampleSentence``'s
    ``TranslationsOC`` rows do not."""
    if not isinstance(record, Mapping):
        return None
    for key in ("Guid", "guid"):
        if key in record and looks_like_guid(record[key]):
            return str(record[key]).lower()
    return None


def _canonical(value, handle_to_tag) -> object:
    """A comparable, order-stable projection of a nested structure, with every
    multistring inside it normalized to language tags (the same FR-068
    discipline the top-level multistring rule applies -- a handle nested two
    levels down is no more portable than one at the top)."""
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            sk = str(k)
            if sk.isdigit():
                sk = (handle_to_tag or {}).get(sk) or ("handle:" + sk)
            out[sk] = _canonical(v, handle_to_tag)
        return {k: out[k] for k in sorted(out)}
    if isinstance(value, (set, frozenset)):
        return sorted(str(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_canonical(v, handle_to_tag) for v in value]
    return value


NOT_COMPARED_RULE_REFUSED = (
    "a comparison rule refused to classify this field rather than guess "
    "(compare.FieldPlaneContractError). The refusal is recorded here, at the "
    "field, so the object's other fields are still measured and the gap is "
    "attributable -- raising would cost the whole run one class's worth of "
    "evidence for one unclassifiable field"
)


def compare_field(class_name: str, field_name: str, source_value, target_value,
                  **kw) -> FieldComparison:
    """``_compare_field`` with FR-079/FR-090's "refuse rather than guess"
    exceptions turned into a RECORDED refusal.

    ``compare.FieldPlaneContractError`` is raised by the rules themselves when
    a classification cannot be made as specified -- an order significance the
    tool's own convention does not determine (measured: flexicon renames
    ``SegmentsRC`` to ``PhonemeGuids``, which no suffix rule can read), a
    writing-system alternative with no language tag, an enumerated value with
    no decoder. Every one of those is a real gap and belongs on the artifact.
    None of them is a reason to lose the other twenty fields of the object.
    """
    try:
        return _compare_field(class_name, field_name, source_value,
                              target_value, **kw)
    except FieldPlaneContractError as exc:
        return FieldComparison(
            class_name=class_name, field_name=field_name,
            rule=RULE_UNCLASSIFIED, verdict="", performed=False,
            reason="%s -- %s" % (NOT_COMPARED_RULE_REFUSED, exc),
            source_value=source_value, target_value=target_value)


def _compare_field(
    class_name: str,
    field_name: str,
    source_value,
    target_value,
    *,
    ws_mapping,
    source_ws_keys=(),
    target_ws_keys=(),
    source_handle_to_tag=None,
    target_handle_to_tag=None,
    target_ws_tags=(),
    natural_key_roster=None,
    remap_record=None,
    has_accounting_record: bool = False,
) -> FieldComparison:
    """Judge ONE field of one matched object pair, by exactly one rule.

    The unit of "a comparison performed" is a FIELD of an object, not an
    alternative or a list element: the sub-rows live in ``detail`` so nothing
    is lost, but the count that ``COMPARISONS-PERFORMED`` reads stays a count
    of things a reader can point at.
    """
    src_kind = classify_value_kind(source_value, ws_keys=source_ws_keys)
    tgt_kind = classify_value_kind(target_value, ws_keys=target_ws_keys)
    kind = _reconcile_kinds(src_kind, tgt_kind, source_value, target_value)

    def _mk(rule, verdict, **kw):
        return FieldComparison(
            class_name=class_name, field_name=field_name, rule=rule,
            verdict=verdict, source_value=source_value,
            target_value=target_value, **kw)

    # ---- the two asymmetric cases, before any rule is chosen -------------
    if src_kind == KIND_NULL and tgt_kind != KIND_NULL:
        return _mk(RULE_SHAPE, VERDICT_TARGET_ONLY)
    if tgt_kind == KIND_NULL and src_kind != KIND_NULL:
        if src_kind == KIND_REFERENCE:
            # FR-087/FR-088: a null target referent is the link rule's own
            # business, and the accounting record is what separates the
            # milder verdict from the silent one.
            result = classify_link(
                class_name=class_name, field_name=field_name,
                source_referent=source_value, target_referent=None,
                has_accounting_record=has_accounting_record,
                natural_key_roster=natural_key_roster,
                remap_record=remap_record,
            )
            return _mk(RULE_LINK, result.verdict, detail=result.as_dict())
        return _mk(RULE_SHAPE, DISTORTED, subtype=SUB_ABSENT)

    if kind == RULE_SHAPE:
        return _mk(RULE_SHAPE, VERDICT_SHAPE_MISMATCH,
                   detail={"source_kind": src_kind, "target_kind": tgt_kind})

    if kind == KIND_NULL:
        return _mk(RULE_SCALAR, EQUAL)

    if kind == KIND_UNKNOWN:
        return _mk(RULE_UNCLASSIFIED, VERDICT_UNCLASSIFIED,
                   detail={"source_kind": src_kind, "target_kind": tgt_kind,
                           "source_type": type(source_value).__name__,
                           "target_type": type(target_value).__name__})

    # ---- KIND_SCALAR: a bool, or an int this feature has declared numeric
    if kind == KIND_SCALAR:
        equal = source_value == target_value
        if isinstance(source_value, bool) or isinstance(target_value, bool):
            return _mk(RULE_SCALAR, EQUAL if equal else DISTORTED,
                       subtype="" if equal else SUB_CONTENT)
        if "%s.%s" % (class_name, field_name) not in NUMERIC_INT_FIELDS:
            return _mk(RULE_SCALAR, "", performed=False,
                       reason=NOT_COMPARED_UNDECLARED_INT)
        return _mk(RULE_SCALAR, EQUAL if equal else DISTORTED,
                   subtype="" if equal else SUB_CONTENT)

    # ---- KIND_TEXT_VALUE: the T040 distortion rules --------------------
    if kind == KIND_TEXT_VALUE:
        d = classify_distortion(str(source_value), str(target_value), kind=KIND_TEXT)
        return _mk(RULE_TEXT, d.verdict, subtype=d.subtype)

    # ---- KIND_REFERENCE: the T042 link rules ---------------------------
    if kind == KIND_REFERENCE:
        if (natural_key_roster is not None
                and getattr(natural_key_roster, "admits", None) is not None
                and natural_key_roster.admits(class_name)
                and remap_record is None):
            # FR-085 forbids falling back to identifier comparison here, and
            # classify_link raises rather than guess. Refusing the comparison
            # -- visibly, with the reason -- is the honest third option.
            return _mk(RULE_LINK, "", performed=False,
                       reason=NOT_COMPARED_NO_REMAP_RECORD)
        result = classify_link(
            class_name=class_name, field_name=field_name,
            source_referent=source_value, target_referent=target_value,
            has_accounting_record=has_accounting_record,
            natural_key_roster=natural_key_roster, remap_record=remap_record,
        )
        return _mk(RULE_LINK, result.verdict, detail=result.as_dict())

    # ---- KIND_MULTISTRING: the T039 writing-system rules ---------------
    if kind == KIND_MULTISTRING:
        src_alts, src_unresolved = normalize_multistring(
            source_value, source_handle_to_tag)
        tgt_alts, tgt_unresolved = normalize_multistring(
            target_value, target_handle_to_tag)
        if src_unresolved or tgt_unresolved:
            return _mk(RULE_WS, "", performed=False,
                       reason=NOT_COMPARED_UNRESOLVED_HANDLE,
                       detail={"source_unresolved_handles": src_unresolved,
                               "target_unresolved_handles": tgt_unresolved})
        if not src_alts:
            return _mk(RULE_WS, VERDICT_TARGET_ONLY if tgt_alts else EQUAL)
        tags = frozenset(str(t) for t in (target_ws_tags or ()))
        rows = compare_ws_alternatives(
            src_alts, tgt_alts, mapping=ws_mapping,
            # FR-072 measures the OUTCOME: whether the mapped target writing
            # system exists in the TARGET PROJECT. The default callback asks
            # only whether this object happens to carry that alternative,
            # which would report an empty alternative as a lost writing
            # system.
            target_resolves=lambda tag: (ws_mapping.target_tag_for(tag) in tags),
        )
        bad = [r for r in rows
               if r.get("ws_verdict") != WS_OUT_OF_SCOPE
               and (r.get("ws_verdict") != WS_MAPPED
                    or r.get("verdict") == DISTORTED)]
        if bad:
            first = bad[0]
            return _mk(RULE_WS, DISTORTED,
                       subtype=(first.get("subtype")
                                or first.get("ws_verdict") or SUB_CONTENT),
                       detail={"alternatives": rows})
        return _mk(RULE_WS, EQUAL, detail={"alternatives": rows})

    # ---- KIND_REFERENCE_SEQUENCE / KIND_SCALAR_SET: the T041 order rules
    if kind in (KIND_REFERENCE_SEQUENCE, KIND_SCALAR_SET):
        src_seq = [str(v) for v in (source_value or ())]
        tgt_seq = [str(v) for v in (target_value or ())]
        significance = None
        if isinstance(source_value, (set, frozenset)) or isinstance(
                target_value, (set, frozenset)):
            # A Python set carries no order, so asserting order over it would
            # be asserting something the measurement cannot see. Membership is
            # the whole of what this value can support (FR-080/FR-081).
            src_seq, tgt_seq = sorted(src_seq), sorted(tgt_seq)
            significance = ORDER_NOT_ASSERTED
        result = compare_order(class_name, field_name, src_seq, tgt_seq,
                               significance=significance)
        return _mk(RULE_ORDER, EQUAL if result.passed else DISTORTED,
                   subtype="" if result.passed else SUB_CONTENT,
                   detail=result.as_dict())

    # ---- KIND_STRUCTURE / KIND_STRUCTURE_SEQUENCE ----------------------
    # A nested owned record has no rule of its own in FR-069..FR-090; it is
    # compared as the structure it is, after the same tag normalization, so a
    # handle nested inside a feature specification cannot silently decide the
    # verdict.
    src_canon = _canonical(source_value, source_handle_to_tag)
    tgt_canon = _canonical(target_value, target_handle_to_tag)
    if kind == KIND_STRUCTURE_SEQUENCE:
        src_keys = [_structure_key(r) for r in (source_value or ())]
        if src_keys and all(k is not None for k in src_keys):
            # Identity-bearing rows: compare as a set of records keyed by
            # their own GUID, so a reordering is not reported as a content
            # difference (FR-080) and a missing row is named.
            src_by = {_structure_key(r): _canonical(r, source_handle_to_tag)
                      for r in (source_value or ())}
            tgt_by = {_structure_key(r): _canonical(r, target_handle_to_tag)
                      for r in (target_value or ())}
            missing = sorted(k for k in src_by if k not in tgt_by)
            differing = sorted(k for k in src_by
                               if k in tgt_by and src_by[k] != tgt_by[k])
            if missing or differing:
                return _mk(RULE_STRUCTURE, DISTORTED, subtype=SUB_CONTENT,
                           detail={"missing_rows": missing,
                                   "differing_rows": differing,
                                   "source_row_count": len(src_by),
                                   "target_row_count": len(tgt_by)})
            return _mk(RULE_STRUCTURE, EQUAL,
                       detail={"rows_compared": len(src_by)})
    if src_canon == tgt_canon:
        return _mk(RULE_STRUCTURE, EQUAL)
    return _mk(RULE_STRUCTURE, DISTORTED, subtype=SUB_CONTENT,
               detail={"source": jsonable(src_canon),
                       "target": jsonable(tgt_canon)})


def _empty_class_counters() -> dict:
    return {
        "objects_compared": 0,
        "objects_not_read": 0,
        "objects_with_findings": 0,
        "comparisons_performed": 0,
        "comparisons_refused": 0,
        "findings": 0,
        "target_only": 0,
        "rules": {r: {"performed": 0, "findings": 0, "refused": 0} for r in RULES},
        "fields": {},
        "refusal_reasons": {},
    }


class FieldPlaneComparator:
    """The payload comparator ``reconcile_objects`` has been waiting for, and
    the accumulator the artifact's plane-2 block is written from.

    ``payload_equal(class_name, source_id, target_id)`` is the callable
    ``reconcile_objects`` invokes for every object it matched under an
    identity. Its three-valued return is the contract that matters:

    * ``None``  -- NO comparison was performed for this pair (neither side's
      fields could be read, or every field of it was refused). FR-097 turns
      that into ``present-under-matching-identity-but-never-compared``, which
      FAILS ``TOTAL-ACCOUNTING``. That is the correct answer: the object is
      unverified, and saying so is the whole point of this feature.
    * ``False`` -- at least one field comparison produced a finding.
    * ``True``  -- at least one field was compared and nothing was found.

    Nothing here ever returns ``True`` on the strength of zero comparisons.
    """

    def __init__(
        self,
        *,
        source_census,
        target_census,
        ws_mapping,
        source_ws_keys=(),
        target_ws_keys=(),
        source_handle_to_tag=None,
        target_handle_to_tag=None,
        target_ws_tags=(),
        natural_key_roster=None,
        remap_record=None,
        drops=(),
        category_for: Optional[Callable] = None,
        unreadable_classes: Optional[Mapping] = None,
        phase: str = "census_2",
        source_side=None,
        target_side=None,
        class_category_map=None,
    ) -> None:
        self.source_census = source_census
        self.target_census = target_census
        self.ws_mapping = ws_mapping
        self.source_ws_keys = frozenset(str(k) for k in (source_ws_keys or ()))
        self.target_ws_keys = frozenset(str(k) for k in (target_ws_keys or ()))
        self.source_handle_to_tag = dict(source_handle_to_tag or {})
        self.target_handle_to_tag = dict(target_handle_to_tag or {})
        self.target_ws_tags = frozenset(str(t) for t in (target_ws_tags or ()))
        self.natural_key_roster = natural_key_roster
        self.remap_record = remap_record
        self.category_for = category_for
        self.unreadable_classes = dict(unreadable_classes or {})
        self.phase = phase

        # FR-088's "a matching drop/skip record for this owner/field/item".
        # Indexed both ways: the engine's drop channel does not always carry a
        # field name, and an owner+item match is still a record OF that item,
        # which is what the rule asks for.
        self._drops_owner_field_item = set()
        self._drops_owner_item = set()
        for d in drops or ():
            owner = str(getattr(d, "owner", "") or "").lower()
            fname = str(getattr(d, "field_name", "") or "")
            item = str(getattr(d, "item", "") or "").lower()
            self._drops_owner_field_item.add((owner, fname, item))
            self._drops_owner_item.add((owner, item))

        # The gathers and the tracked join this comparator was built from.
        # Carried rather than re-derived: the artifact's depth, census and
        # coverage blocks are all written from the SAME measurement the
        # comparisons were made against, and re-reading either one later would
        # let the two drift.
        self.source_side = source_side
        self.target_side = target_side
        self.class_category_map = class_category_map

        self._per_class: dict = {}
        self._value_findings: list = []
        self._link_findings: list = []
        self._pairs_seen = 0

    # -- internals --------------------------------------------------------

    def _counters(self, class_name: str) -> dict:
        return self._per_class.setdefault(class_name, _empty_class_counters())

    def _has_accounting_record(self, owner_id, field_name, referent) -> bool:
        owner = str(owner_id or "").lower()
        item = str(referent or "").lower()
        if not item:
            return False
        return ((owner, str(field_name or ""), item) in self._drops_owner_field_item
                or (owner, item) in self._drops_owner_item)

    def _record(self, comparison: FieldComparison, source_id: str) -> None:
        counters = self._counters(comparison.class_name)
        rule = counters["rules"].setdefault(
            comparison.rule, {"performed": 0, "findings": 0, "refused": 0})
        per_field = counters["fields"].setdefault(
            comparison.field_name, {"performed": 0, "findings": 0, "refused": 0})

        if not comparison.performed:
            counters["comparisons_refused"] += 1
            rule["refused"] += 1
            per_field["refused"] += 1
            reason = comparison.reason or "(no reason recorded)"
            counters["refusal_reasons"][reason] = (
                counters["refusal_reasons"].get(reason, 0) + 1)
            return

        counters["comparisons_performed"] += 1
        rule["performed"] += 1
        per_field["performed"] += 1
        if comparison.verdict == VERDICT_TARGET_ONLY:
            counters["target_only"] += 1
        if comparison.rule == RULE_LINK and comparison.detail:
            # FR-085..FR-090: every classified reference is recorded, not only
            # the failing ones. A link plane that carries only its failures
            # cannot show how many links were resolved, and "no dangling
            # links" over an unknown denominator is not evidence.
            self._link_findings.append(dict(comparison.detail))
        if comparison.is_finding:
            counters["findings"] += 1
            rule["findings"] += 1
            per_field["findings"] += 1
            self._value_findings.append(self._finding_row(comparison, source_id))

    def _finding_row(self, comparison: FieldComparison, source_id: str) -> dict:
        category = None
        if self.category_for is not None:
            cats = self.category_for(comparison.class_name)
            if cats:
                category = (sorted(cats)[0] if not isinstance(cats, str) else cats)
        return {
            "phase": self.phase,
            "class": comparison.class_name,
            "category": category,
            "field": comparison.field_name,
            "source_value": jsonable(comparison.source_value),
            "target_value": jsonable(comparison.target_value),
            "verdict": comparison.verdict,
            "kind": comparison.rule,
            "subtype": comparison.subtype,
            "guid": source_id,
            "detail": jsonable(comparison.detail),
        }

    # -- the reconcile_objects callback ----------------------------------

    def payload_equal(self, class_name: str, source_id: str, target_id: str):
        """FR-097's payload comparator. See the class docstring for the
        three-valued contract."""
        self._pairs_seen += 1
        counters = self._counters(class_name)
        src_obj = (getattr(self.source_census, "values", {}) or {}).get(
            class_name, {}).get(source_id)
        tgt_obj = (getattr(self.target_census, "values", {}) or {}).get(
            class_name, {}).get(target_id)
        if src_obj is None or tgt_obj is None:
            # One side's fields were never read -- an unreadable class, or an
            # object the census did not reach. NOT a pass and NOT a failure:
            # no comparison happened, and FR-097 has a bucket for exactly that.
            counters["objects_not_read"] += 1
            return None

        performed = 0
        found = 0
        for field_name in sorted(set(src_obj) | set(tgt_obj)):
            source_value = src_obj.get(field_name)
            target_value = tgt_obj.get(field_name)
            comparison = compare_field(
                class_name, field_name, source_value, target_value,
                ws_mapping=self.ws_mapping,
                source_ws_keys=self.source_ws_keys,
                target_ws_keys=self.target_ws_keys,
                source_handle_to_tag=self.source_handle_to_tag,
                target_handle_to_tag=self.target_handle_to_tag,
                target_ws_tags=self.target_ws_tags,
                natural_key_roster=self.natural_key_roster,
                remap_record=self.remap_record,
                has_accounting_record=self._has_accounting_record(
                    source_id, field_name, source_value),
            )
            self._record(comparison, source_id)
            if comparison.performed:
                performed += 1
                if comparison.is_finding:
                    found += 1

        if performed == 0:
            # Every field of this object was refused (or the class has no
            # compared fields at all). The object is unverified; saying "equal"
            # here would be the silence this feature exists to remove.
            counters["objects_not_read"] += 1
            return None
        counters["objects_compared"] += 1
        if found:
            counters["objects_with_findings"] += 1
            return False
        return True

    # -- what the artifact and the guards read ---------------------------

    def class_counters(self) -> tuple:
        """``(comparisons_performed, objects_compared)`` per CLASS, ready for
        ``coverage.project_comparisons_to_categories``. The third input that
        bridge needs -- ``source_objects`` -- is the census's, not this
        object's: the comparator sees only the pairs plane 1 matched, and a
        source object plane 1 never matched is precisely what must not be
        counted as compared."""
        performed = {c: v["comparisons_performed"] for c, v in self._per_class.items()}
        objects = {c: v["objects_compared"] for c, v in self._per_class.items()}
        return performed, objects

    def findings_by_class(self) -> dict:
        return {c: v["findings"] for c, v in self._per_class.items() if v["findings"]}

    def value_findings(self) -> list:
        return list(self._value_findings)

    def link_findings(self) -> list:
        return list(self._link_findings)

    def comparisons_block(self) -> dict:
        """The artifact's ``comparisons`` block (T045f's field).

        Meta keys and class names live in SEPARATE sub-objects. A block that
        mixed them would make ``block["totals"]`` ambiguous the first time LCM
        gains a class called ``totals``, and this feature does not rely on
        that not happening.
        """
        totals = {
            "objects_compared": 0, "objects_not_read": 0,
            "objects_with_findings": 0, "comparisons_performed": 0,
            "comparisons_refused": 0, "findings": 0, "target_only": 0,
            "pairs_seen": self._pairs_seen,
            "classes_touched": len(self._per_class),
        }
        refusals: dict = {}
        rules_total = {r: {"performed": 0, "findings": 0, "refused": 0} for r in RULES}
        for counters in self._per_class.values():
            for key in ("objects_compared", "objects_not_read",
                        "objects_with_findings", "comparisons_performed",
                        "comparisons_refused", "findings", "target_only"):
                totals[key] += counters[key]
            for reason, n in counters["refusal_reasons"].items():
                refusals[reason] = refusals.get(reason, 0) + n
            for rule, row in counters["rules"].items():
                agg = rules_total.setdefault(
                    rule, {"performed": 0, "findings": 0, "refused": 0})
                for key in ("performed", "findings", "refused"):
                    agg[key] += row[key]
        return {
            "schema": "035-field-plane-1",
            "rule_vocabulary": list(RULES),
            "per_class": {c: self._per_class[c] for c in sorted(self._per_class)},
            "rules": rules_total,
            "totals": totals,
            "refusal_reasons": refusals,
            "unreadable_classes": dict(sorted(self.unreadable_classes.items())),
        }


# ===========================================================================
# THE LIVE SIDE: reading one project's field plane
# ===========================================================================
# Everything above this line is pure and unit-testable without FieldWorks.
# Everything below opens a project READ-ONLY and is exercised live.

WS_MODE_FULL = "full"
WS_MODE_DEFAULT_VERNACULAR = "default-vernacular"
WS_MODES: tuple = (WS_MODE_FULL, WS_MODE_DEFAULT_VERNACULAR)


@dataclass
class FieldPlaneSide:
    """One project's plane-2 measurement, and an explicit record of what it
    could NOT measure.

    ``unreadable_classes`` is the load-bearing half. Ten classes' flexicon
    accessors raise on ``GetSyncableProperties`` against a live project (see
    ``field_dispatch``'s "OTHER LIVE DEFECTS"); three more have no dispatch at
    all. A gather that let any of those abort the sweep would trade a partial
    measurement for none, and one that skipped them silently would report a
    coverage hole as a clean pass. They are recorded, per class, with the
    exception text, and the caller feeds them to the coverage report.
    """
    project: str = ""
    objects_by_class: dict = _dc_field(default_factory=dict)
    census: object = None
    ws_tags: tuple = ()
    ws_keys: frozenset = frozenset()
    handle_to_tag: dict = _dc_field(default_factory=dict)
    default_vernacular: str = ""
    default_analysis: str = ""
    unreadable_classes: dict = _dc_field(default_factory=dict)
    undispatchable_classes: dict = _dc_field(default_factory=dict)
    nesting: dict = _dc_field(default_factory=dict)
    cost: dict = _dc_field(default_factory=dict)

    def source_object_counts(self) -> dict:
        return {c: len(v) for c, v in self.objects_by_class.items()}

    def as_dict(self) -> dict:
        return {
            "project": self.project,
            "classes_enumerated": len(self.objects_by_class),
            "objects_enumerated": sum(len(v) for v in self.objects_by_class.values()),
            "writing_systems": list(self.ws_tags),
            "default_vernacular": self.default_vernacular,
            "default_analysis": self.default_analysis,
            "unreadable_classes": dict(sorted(self.unreadable_classes.items())),
            "undispatchable_classes": dict(sorted(self.undispatchable_classes.items())),
            "cost": dict(self.cost),
        }


def open_project_readonly(project_name: str):
    """Open a project read-only and return ``(proj, close)``.

    Same initialization sequence ``audit_guid_preservation.inventory_all``
    uses -- reused rather than reinvented -- so this module cannot drift from
    the open that every other census in this feature performs.
    """
    import flexicon  # noqa: PLC0415 -- lazy: no FieldWorks import at module load

    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001 -- the SLDR is optional for a read
        pass
    from flexicon import FLExProject  # noqa: PLC0415

    proj = FLExProject()
    proj.OpenProject(projectName=project_name, writeEnabled=False)

    def _close():
        # Recorded, never swallowed: FR-108's CLEAN-CLOSE guard reads close
        # outcomes, and a bare `except: pass` here is the exact shape T045b
        # (v) names as actively discarding the measurement.
        proj.CloseProject()

    return proj, _close


def _enumerate_objects(proj, nesting_classes) -> tuple:
    """``({class: [guid]}, {class: {"children_of": {...}, "roots": [...]}})``.

    The nesting half is collected in the SAME pass because FR-189's depth
    measurement needs same-class ownership, which no census in this feature
    carries: ``census_project`` records identity only.
    """
    from SIL.LCModel import ICmObjectRepository  # noqa: PLC0415

    repo = proj.project.ServiceLocator.GetService(ICmObjectRepository)
    wanted_nesting = frozenset(nesting_classes or ())
    by_class: dict = {}
    nesting: dict = {c: {"children_of": {}, "roots": []} for c in wanted_nesting}
    for obj in repo.AllInstances():
        try:
            cls = obj.ClassName
            guid = str(obj.Guid).lower()
        except Exception:  # noqa: BLE001 -- an object whose identity cannot be
            # read is counted by FR-103's accessor counters (T045b), not here
            continue
        by_class.setdefault(cls, []).append(guid)
        if cls in wanted_nesting:
            owner_guid = None
            try:
                owner = obj.Owner
                if owner is not None and owner.ClassName == cls:
                    owner_guid = str(owner.Guid).lower()
            except Exception:  # noqa: BLE001 -- treated as a root below
                owner_guid = None
            if owner_guid is None:
                nesting[cls]["roots"].append(guid)
            else:
                nesting[cls]["children_of"].setdefault(owner_guid, []).append(guid)
    return {c: sorted(v) for c, v in by_class.items()}, nesting


def _writing_systems(proj) -> tuple:
    """``(tags, handle_to_tag, default_vernacular, default_analysis)``.

    ``handle_to_tag`` is what makes a handle-keyed multistring comparable at
    all: the handle is meaningful only inside the project that issued it.
    """
    tags: list = []
    handle_to_tag: dict = {}
    for ws in proj.WritingSystems.GetAll():
        tag = str(ws.Id)
        tags.append(tag)
        handle = getattr(ws, "Handle", None)
        if handle is not None:
            handle_to_tag[str(handle)] = tag
    def_vern = ""
    def_anal = ""
    try:
        def_vern = str(proj.GetDefaultVernacularWS()[0])
    except Exception:  # noqa: BLE001 -- recorded as empty; the caller's mapping
        pass            # construction refuses an empty default explicitly
    try:
        def_anal = str(proj.GetDefaultAnalysisWS()[0])
    except Exception:  # noqa: BLE001
        pass
    return tuple(tags), handle_to_tag, def_vern, def_anal


def gather_field_plane_side(
    project_name: str,
    *,
    roster,
    classes=None,
    max_objects_per_class: Optional[int] = None,
    nesting_classes=None,
    open_project: Optional[Callable] = None,
) -> FieldPlaneSide:
    """Read ONE project's field plane, read-only, in a single open.

    ``classes`` (default: every class present) is intersected with what
    ``field_dispatch.partition_dispatchable`` can reach; the rest is recorded
    in ``undispatchable_classes`` rather than dropped.

    ``max_objects_per_class`` is a DELIBERATE cap, recorded in ``cost`` and
    carried onto the artifact. FR-135 forbids an exclusion expressed as an
    invisible default, and a sampled census is an exclusion of everything it
    did not read, so the default is ``None`` -- read every object -- and a cap
    is only ever something a caller asked for in writing.
    """
    from .census import census_fields  # noqa: PLC0415 -- keeps the import graph flat
    from .compare import SAME_CLASS_NESTING_CLASSES  # noqa: PLC0415
    from .field_dispatch import build_field_source, partition_dispatchable  # noqa: PLC0415

    started = time.time()
    opener = open_project or open_project_readonly
    proj, close = opener(project_name)
    side = FieldPlaneSide(project=project_name)
    try:
        nesting_wanted = (SAME_CLASS_NESTING_CLASSES if nesting_classes is None
                          else nesting_classes)
        objects_by_class, nesting = _enumerate_objects(proj, nesting_wanted)
        side.objects_by_class = objects_by_class
        side.nesting = nesting
        tags, handle_to_tag, def_vern, def_anal = _writing_systems(proj)
        side.ws_tags = tags
        side.handle_to_tag = handle_to_tag
        side.ws_keys = frozenset(tags) | frozenset(handle_to_tag)
        side.default_vernacular = def_vern
        side.default_analysis = def_anal

        present = set(objects_by_class)
        wanted = present if classes is None else (present & set(classes))
        dispatchable, undispatchable = partition_dispatchable(sorted(wanted))
        side.undispatchable_classes = dict(undispatchable or {})

        field_source = build_field_source(proj)
        values: dict = {}
        coverage: dict = {}
        field_reads = 0
        for cls in sorted(dispatchable):
            guids = objects_by_class.get(cls) or []
            if max_objects_per_class is not None:
                guids = guids[:max_objects_per_class]
            if not guids:
                continue
            try:
                one = census_fields({cls: guids}, field_source=field_source,
                                    roster=roster)
            except Exception as exc:  # noqa: BLE001 -- per CLASS, never per run
                # A live accessor defect (ten are known and recorded in
                # field_dispatch) must cost this class's measurement, not the
                # sweep's. The reason is kept verbatim: "unreadable" without
                # the exception text is not actionable.
                side.unreadable_classes[cls] = "%s: %s" % (
                    type(exc).__name__, str(exc)[:400])
                continue
            field_reads += len(guids)
            if cls in one.values:
                values[cls] = one.values[cls]
            if cls in one.coverage:
                coverage[cls] = one.coverage[cls]

        from .census import FieldCensus  # noqa: PLC0415
        side.census = FieldCensus(values=values, coverage=coverage)
        side.cost = {
            "field_reads": field_reads,
            "objects_enumerated": sum(len(v) for v in objects_by_class.values()),
            "classes_enumerated": len(objects_by_class),
            "classes_measured": len(coverage),
            "classes_unreadable": len(side.unreadable_classes),
            "classes_undispatchable": len(side.undispatchable_classes),
            "max_objects_per_class": max_objects_per_class,
            "seconds": round(time.time() - started, 3),
        }
        return side
    finally:
        close()


def build_ws_mapping_for_mode(
    mode: str,
    *,
    source_tags,
    target_tags,
    source_default_vernacular: str = "",
    target_default_vernacular: str = "",
    skip_records=(),
):
    """Build the FR-071 mapping that MIRRORS the mapping the transfer used.

    The transfer's own mapping is built by
    ``harness.full_run.run_full_transfer`` from its ``ws_mapping_mode``. The
    comparison must be made under THAT mapping and no other: comparing under
    a wider one would report as lost a writing system the run never declared
    it would carry, and comparing under a narrower one would hide a declared
    writing system that did not arrive. This function is the single place the
    two modes are translated into a ``WritingSystemMapping``, so the mirror
    cannot drift the way the category selection did before T045a(a).
    """
    from .compare import WritingSystemMapping, build_writing_system_mapping  # noqa: PLC0415

    if mode == WS_MODE_FULL:
        # Every source writing system is declared: mapped by tag identity
        # where the target already has it, created there where it does not.
        return build_writing_system_mapping(source_tags, target_tags,
                                            skip_records=skip_records)
    if mode == WS_MODE_DEFAULT_VERNACULAR:
        if not source_default_vernacular or not target_default_vernacular:
            raise HarnessError(
                "[FR-071] the %r writing-system mapping needs both projects' "
                "default vernacular tags and at least one is missing "
                "(source=%r, target=%r); a mapping built without them would "
                "silently declare nothing"
                % (mode, source_default_vernacular, target_default_vernacular)
            )
        # Deliberately narrow, and FR-070 then reports every OTHER source
        # writing system that carries content as
        # ``unmapped-writing-system-with-no-skip-record`` -- a defect in the
        # RUN's mapping construction, which is exactly what it is.
        return WritingSystemMapping(
            mapped={source_default_vernacular: target_default_vernacular},
            to_create=frozenset(),
            skip_records=frozenset(skip_records or ()),
        )
    raise HarnessError(
        "[FR-071] unknown writing-system mapping mode %r; the modes this "
        "sweep can mirror are %r" % (mode, list(WS_MODES))
    )


def depth_results(source_side: FieldPlaneSide, target_side: FieldPlaneSide,
                  *, classes=None) -> list:
    """FR-189/SC-017 per same-class-nesting class, from the ownership both
    sides recorded during their gather.

    A class absent from the source's nesting record is not skipped: it is
    measured with empty inputs, which ``compare_structural_depth`` reports as
    NOT-EVALUATED -- "the corpus never nested this class" -- rather than as a
    clean pass. That distinction is the whole of FR-189's closing clause.
    """
    from .compare import SAME_CLASS_NESTING_CLASSES, compare_structural_depth  # noqa: PLC0415

    wanted = SAME_CLASS_NESTING_CLASSES if classes is None else classes
    out: list = []
    for cls in wanted:
        src = (source_side.nesting or {}).get(cls) or {}
        tgt = (target_side.nesting or {}).get(cls) or {}
        out.append(compare_structural_depth(
            cls,
            source_children=src.get("children_of") or {},
            target_children=tgt.get("children_of") or {},
            source_roots=src.get("roots") or (),
            target_roots=tgt.get("roots") or (),
        ))
    return out
