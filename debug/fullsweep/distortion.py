"""Feature 035 T045b -- the three distortion detectors' inputs.

FR-098, FR-099 and FR-102 each name a way a measurement can be distorted into
looking clean:

* an EMPTY source collection compared against an empty target one, where
  "there was nothing to copy" and "everything was lost" produce the same
  number (FR-098);
* an unhandled LCM SUBTYPE reduced to an absent-or-empty value, which then
  compares equal to the absent-or-empty value on the other side (FR-099);
* an object present in the TARGET and in no source, which a source-driven
  walk cannot see at all (FR-102/FR-183).

Their guards were built by T033 and have been reporting ``not-evaluated``
since, because nothing produced their inputs. This module produces them.

DERIVED, NOT RE-MEASURED
------------------------
Two of the three are derivations over measurements the run has ALREADY taken,
per the 038 cut recorded in T045b's task note: ``empty_measurements`` from the
per-class source census plus an independent corroborating count, and
``extras`` from the census arithmetic the reconciliation already holds in its
locals (``source_inventory``, ``census_before``, ``census_after_second``).
Taking a second live reading for either would measure the same thing twice
and give the run two numbers that can disagree with no way to adjudicate.

Everything in this module is PURE. No project is opened here; every input
arrives as a dict the caller already had. That is what makes these derivations
unit-testable without FieldWorks, and it is why the reverse walk -- the
"hardest" of T045b's eight on first reading -- turned out to be the cheapest:
all three of its inputs were already in ``run_one_project``'s locals.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

from .guards import (
    EMPTY_OUTCOME_ABSENT_OR_NULL,
    EMPTY_OUTCOME_PRESENT_BUT_EMPTY,
)
from .identity import (
    TOOL_OWNED_IDENTITY_CLASSES,
    classify_tool_owned_instances,
    is_tool_owned_class,
)

# ---------------------------------------------------------------------------
# FR-098 -- empty source collections
# ---------------------------------------------------------------------------

#: Why a class with no instances got the outcome it got. Recorded per record
#: so a reader never has to infer the rule from the value.
_ABSENT_REASON = (
    "the class has no row in the source census AND no <rt class=...> row in "
    "the source .fwdata: the collection is absent or null, not present-empty"
)
_PRESENT_EMPTY_REASON = (
    "the class is present in the source project (the independent .fwdata scan "
    "found rows) but the census enumerated no instance of it: present, empty "
    "as measured -- which is NOT the same statement as absent"
)
_DISAGREEMENT_REASON = (
    "the census and the independent .fwdata scan disagree about this class; "
    "recorded as present-but-empty because the independent count is the one "
    "that does not depend on AllInstances succeeding"
)


def empty_measurements(
    *,
    source_census: Mapping,
    in_scope_classes: Iterable[str],
    corroborating_counts: Optional[Mapping] = None,
) -> list:
    """FR-098: one record per in-scope class with no instance in the source.

    ``source_census``
        ``{class: {guid, ...}}`` -- ``moves.census_project`` output.
    ``in_scope_classes``
        The coverage floor's roster. Iterating the CENSUS instead would make
        this vacuous: a class with no instances is precisely the one the
        census does not mention (``inventory_all`` builds from a
        ``defaultdict(set)``, so a zero-instance class is ABSENT from the dict
        rather than present with an empty set).
    ``corroborating_counts``
        ``{class: n}`` from ``coverage.scan_class_presence`` over THIS project
        -- a byte regex over the ``.fwdata`` that never calls ``AllInstances``
        and is therefore genuinely independent of the census it corroborates.
        ``None`` means the corroborating scan did not run, and every record
        then carries ``corroborating_count: None``, which is exactly what
        ``guard_empty_corroboration`` fails on. That is deliberate: an
        uncorroborated empty measurement must not pass, and substituting 0
        here would be inventing the corroboration.

    **What the independent count buys, and what it does not.** With it, the
    two FR-098 outcomes become distinguishable at class granularity: a class
    the ``.fwdata`` scan finds rows for, but the census enumerated none of, is
    ``present-but-empty``; one neither can see is ``absent-or-null``. Without
    it they collapse -- the 2026-08-19 survey recorded that collapse as a
    known weakness of the census-only reading, and this is what closes it.

    It does NOT make the PROPERTY-granular distinction, which is a different
    and finer question (a present object whose own collection field is empty)
    and belongs to the field plane, not here. Each record says which of the
    two granularities produced it, so a reader cannot mistake one for the
    other.
    """
    records: list = []
    counts = dict(corroborating_counts or {})
    have_corroboration = corroborating_counts is not None

    for cls in sorted(set(in_scope_classes)):
        instances = source_census.get(cls)
        if instances:
            continue
        corroborating = counts.get(cls) if have_corroboration else None
        present_in_census = cls in source_census   # present, but empty set

        if not have_corroboration:
            outcome = EMPTY_OUTCOME_PRESENT_BUT_EMPTY if present_in_census \
                else EMPTY_OUTCOME_ABSENT_OR_NULL
            reason = ("no independent count was taken, so this outcome rests "
                      "on the census alone and the guard will fail it")
        elif corroborating:
            outcome = EMPTY_OUTCOME_PRESENT_BUT_EMPTY
            reason = _DISAGREEMENT_REASON if not present_in_census \
                else _PRESENT_EMPTY_REASON
        elif present_in_census:
            outcome = EMPTY_OUTCOME_PRESENT_BUT_EMPTY
            reason = _PRESENT_EMPTY_REASON
        else:
            outcome = EMPTY_OUTCOME_ABSENT_OR_NULL
            reason = _ABSENT_REASON

        records.append({
            "class": cls,
            "outcome": outcome,
            "reason": reason,
            "census_instances": 0,
            "present_in_census_as_empty": present_in_census,
            "corroborating_count": corroborating,
            "corroborating_source": (
                "coverage.scan_class_presence over this project's .fwdata"
                if have_corroboration else None),
            "granularity": "class",
        })
    return records


# ---------------------------------------------------------------------------
# FR-099 -- subtypes the engine did not handle
# ---------------------------------------------------------------------------

#: The three ways a class can end up unmeasured, each a DIFFERENT statement.
#: FR-099's whole point is that they must not collapse into one another, nor
#: into "measured and equal".
OUTCOME_UNDISPATCHABLE = "no-dispatch-for-subtype"
OUTCOME_UNREADABLE = "accessor-raised-on-subtype"
OUTCOME_OUT_OF_SCOPE = "in-source-but-not-on-the-in-scope-roster"

UNHANDLED_OUTCOMES: tuple[str, ...] = (
    OUTCOME_UNDISPATCHABLE, OUTCOME_UNREADABLE, OUTCOME_OUT_OF_SCOPE,
)


def unhandled_subtypes(
    *,
    source_census: Mapping,
    undispatchable: Optional[Mapping] = None,
    unreadable: Optional[Mapping] = None,
    in_scope_classes: Optional[Iterable[str]] = None,
) -> list:
    """FR-099: each subtype the engine did not handle, NAMED and COUNTED.

    ``undispatchable`` / ``unreadable``
        ``{class: reason}`` from ``fieldplane.FieldPlaneSide`` -- the classes
        for which no Operations accessor exists at all, and the classes whose
        accessor raised against a live project. ``field_dispatch`` records
        thirteen of these between them; they are the concrete population
        FR-099 is about.
    ``in_scope_classes``
        When given, a class present in the source census, absent from both
        unmeasured maps, and NOT on the roster is reported as
        ``in-source-but-not-on-the-in-scope-roster``. A class the run never
        considered is unhandled in the sense that matters -- nothing compared
        it -- and leaving it out would let the roster's own gaps read as
        clean.

    Every record carries ``reduced_to_equal_comparison: False``, and that is a
    MEASURED fact rather than a convenient constant: each of these classes is
    recorded as unmeasured by the gather and is therefore never handed to the
    comparator at all. FR-099's failure mode is the opposite path -- a subtype
    the comparator DID see, reduced to an absent/empty value that then
    compared equal to the other side's absent/empty value. Should such a path
    ever exist, it must set this flag, and the guard will fail the run.
    """
    records: list = []
    undis = dict(undispatchable or {})
    unread = dict(unreadable or {})
    roster = set(in_scope_classes) if in_scope_classes is not None else None

    def _count(cls: str) -> int:
        return len(source_census.get(cls) or ())

    for cls in sorted(undis):
        records.append({
            "subtype": cls,
            "outcome_name": OUTCOME_UNDISPATCHABLE,
            "count": _count(cls),
            "reason": undis[cls],
            "reduced_to_equal_comparison": False,
            "why_not_reduced": "the gather recorded this class as unmeasured; "
                               "no object of it reached the comparator, so no "
                               "comparison of it returned equal",
        })
    for cls in sorted(unread):
        if cls in undis:
            # A class cannot be both; recording it twice would double its
            # count and make the guard's total meaningless.
            continue
        records.append({
            "subtype": cls,
            "outcome_name": OUTCOME_UNREADABLE,
            "count": _count(cls),
            "reason": unread[cls],
            "reduced_to_equal_comparison": False,
            "why_not_reduced": "the accessor raised; the class is recorded "
                               "unreadable and never compared",
        })
    if roster is not None:
        for cls in sorted(source_census):
            if cls in undis or cls in unread or cls in roster:
                continue
            if not source_census.get(cls):
                continue
            records.append({
                "subtype": cls,
                "outcome_name": OUTCOME_OUT_OF_SCOPE,
                "count": _count(cls),
                "reason": "present in the source with %d instance(s) but absent "
                          "from the in-scope roster, so no rule was ever "
                          "selected for it" % _count(cls),
                "reduced_to_equal_comparison": False,
                "why_not_reduced": "never entered the comparison at all",
            })
    return records


# ---------------------------------------------------------------------------
# FR-102 / FR-183 -- the reverse walk
# ---------------------------------------------------------------------------

def extras(
    *,
    source_census: Mapping,
    target_before: Mapping,
    target_after: Mapping,
    allowlisted_classes: Optional[Iterable[str]] = None,
) -> list:
    """FR-102: target objects that are newly present and trace to no source.

    ``reconcile_objects`` walks source -> target only, so an object the
    transfer ADDED to the target under an identity no source object carries is
    invisible to it. This is that walk, run backwards.

    The population is ``(after - before)`` per class -- objects this run
    created -- minus the source's own identities. An object already in the
    target before the run is not an extra; it is the target's own data, and
    counting it would make every run's extras list the whole target.

    ``tool_owned_duplicate`` (FR-183)
        A SECOND instance of a tool-owned-identity class is unexplained loss
        and is never allowlistable, however an allowlist entry is written.

        **The population this is judged over is NOT every instance of the
        class, and getting that wrong is easy.** FR-183 reads "exactly one
        instance expected per target", and the only class on the roster is
        ``CmAgent`` -- of which every real FieldWorks project natively
        contains several (the default user, the parser agents). Measured
        against ``Ejagham Mini``: four, in a walk that preserved every
        identity and lost nothing. Judging over the whole post-run set
        therefore reports a duplicate on a clean transfer, which is a false
        FR-102 failure on every project in the corpus.

        What FR-183 counts is instances purporting to record THE TOOL'S OWN
        act, which is
        ``(instances carrying the pinned GUID) | (newly-created instances
        that trace to no source object)``. A pre-existing native agent is the
        target's own data; a newly-present agent that IS traceable to the
        source is a copied source object, and FR-183 handles that case
        separately through ``assert_identity_not_derived_from_source``.
        Neither is the tool recording itself, and neither may be counted as
        one.

    ``allowlisted``
        ``False`` for every record unless the caller names classes, and the
        caller does not. ``LossAllowlistMatcher`` keys on
        ``(project, class_name, field_name, reason)`` and matches a DROP
        REASON byte-for-byte; a target-native addition has no drop reason and
        no field, so no existing entry can match one, and no
        "expected target-native addition" roster exists in ``contracts/``.
        Inventing one before the first measurement would decide in advance
        what the measurement is allowed to find.

        **One exception, and it is enumerated rather than invented.** An
        object carrying a PINNED tool-owned GUID is allowlisted, because
        FR-183 does not merely expect that object -- it REQUIRES the engine to
        create it, under exactly that identity, derived from no source value.
        Failing it as an unexplained extra would report the contract being
        honoured as a fidelity defect. The roster that "does not exist" for
        arbitrary target-native additions DOES exist for this one object:
        ``identity.TOOL_OWNED_IDENTITY_CLASSES``. Note the asymmetry is safe
        in the direction that matters -- a SECOND such object is caught on
        ``guard_no_extra``'s duplicate branch, which is checked BEFORE the
        allowlist branch and ignores it, so FR-183's "never allowlistable"
        survives intact.

        **Consequence, stated plainly** (the 2026-08-19 ruling, unchanged): if
        the pilot corpus produces extras at all, this flips those projects
        from ``VACUOUS`` to ``UNEXPLAINED_LOSS``. That is a worse-looking
        result and a truer one. Whether a roster is warranted is a decision
        for after the first measurement.
    """
    allow = set(allowlisted_classes or ())
    # FR-183's pinned constants. The ONE expected target-native addition that
    # IS enumerated in a tracked contract -- see the ``allowlisted`` note in
    # this function's docstring for why it, and only it, is exempt.
    pinned_guids = {
        spec["pinned_guid"] for spec in TOOL_OWNED_IDENTITY_CLASSES.values()
        if spec.get("pinned_guid")
    }
    source_ids: dict = {c: set(v or ()) for c, v in source_census.items()}
    all_source_ids: set = set()
    for ids in source_ids.values():
        all_source_ids |= ids

    records: list = []
    for cls in sorted(set(target_after) | set(target_before)):
        before = set(target_before.get(cls) or ())
        after = set(target_after.get(cls) or ())
        new = after - before
        if not new:
            continue

        duplicate_outcome = None
        tool_owned_population: set = set()
        if is_tool_owned_class(cls):
            # The instances that PURPORT TO RECORD THE TOOL'S OWN ACT -- not
            # every instance of the class. See the docstring: a FieldWorks
            # project ships several native CmAgents, and counting those would
            # fail FR-102 on every clean transfer in the corpus.
            pinned = TOOL_OWNED_IDENTITY_CLASSES[cls]["pinned_guid"]
            tool_owned_population = {
                g for g in after
                if g == pinned or (g in new and g not in source_ids.get(cls, set()))
            }
            if tool_owned_population:
                duplicate_outcome = classify_tool_owned_instances(
                    cls, sorted(tool_owned_population))

        for obj_id in sorted(new):
            traceable = obj_id in source_ids.get(cls, set())
            # An identity the source carries under a DIFFERENT class is not a
            # clean trace, but it is not nothing either -- recorded distinctly
            # so a class-renaming defect does not read as a fresh identity.
            traceable_other_class = (not traceable) and obj_id in all_source_ids
            records.append({
                "class": cls,
                "id": obj_id,
                "traceable_to_source": bool(traceable),
                "traceable_to_source_under_another_class": bool(traceable_other_class),
                # Only an object IN the tool-owned population carries the
                # duplicate flag. A native agent sitting beside a duplicated
                # pair is not itself the duplicate.
                "tool_owned_duplicate": bool(
                    duplicate_outcome is not None
                    and duplicate_outcome.no_extra_failure
                    and obj_id in tool_owned_population),
                "tool_owned_outcome": (
                    duplicate_outcome.outcome
                    if (duplicate_outcome and obj_id in tool_owned_population)
                    else None),
                "allowlisted": bool(cls in allow or obj_id in pinned_guids),
                "allowlist_note": (
                    "carries the pinned tool-owned identity FR-183 REQUIRES "
                    "the engine to create; allowlisted by "
                    "identity.TOOL_OWNED_IDENTITY_CLASSES, which is the one "
                    "tracked roster of expected target-native additions"
                    if obj_id in pinned_guids else
                    ("" if cls in allow else
                     "no expected-target-native-addition roster covers this "
                     "class; see distortion.extras")),
            })
    return records


def extras_summary(records: Sequence[Mapping]) -> dict:
    """A countable summary of the reverse walk, for the artifact.

    The guard reads the RECORDS; this is for a human reading the document, and
    it exists because "0 extras" and "the reverse walk did not run" are the
    same number of records.
    """
    by_class: dict = {}
    for rec in records:
        cls = rec.get("class")
        row = by_class.setdefault(
            cls, {"new": 0, "traceable": 0, "untraceable": 0,
                  "tool_owned_duplicate": 0})
        row["new"] += 1
        if rec.get("traceable_to_source"):
            row["traceable"] += 1
        else:
            row["untraceable"] += 1
        if rec.get("tool_owned_duplicate"):
            row["tool_owned_duplicate"] += 1
    return {
        "walk": "target -> source (the reverse of reconcile_objects)",
        "extras_examined": len(records),
        "untraceable": sum(1 for r in records if not r.get("traceable_to_source")),
        "tool_owned_duplicates": sum(
            1 for r in records if r.get("tool_owned_duplicate")),
        "by_class": {c: by_class[c] for c in sorted(by_class)},
    }
