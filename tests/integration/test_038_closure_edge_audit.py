"""T067 / T068 / T069 -- the FR-018 audit that decides which closure edges may
be registered at all.

Asserted against COMMITTED MEASUREMENTS
(`_snapshots/closure-edge-audit-038-*.json`, produced by
`debug/audit038_closure_edges.py` over two live projects, read-only). Same
discipline as `test_038_process_rules.py`: measure once against a real
database, commit the numbers, assert against the record -- a suite invocation
may not open FLEx projects by surprise.

WHAT THE AUDIT FOUND, AND WHY IT MATTERED MORE THAN THE REGISTRATION IT BLOCKED.

FR-018 exists so no dependency relationship influences a plan before someone
checked it. Phase 7's plan assumed the checking would be a formality and the
three edges would register one after another. Two of them could not register
at all, because their producers did not work on live data:

    AFFIX_TO_POS            uncast 0, cast 296 / 245   cast mandatory
    MSA_TO_FEAT_STRUC_TYPE  uncast 0, cast 216 /  40   cast mandatory
    SLOT_TO_POS             uncast/cast equal          no cast needed
    TEMPLATE_TO_POS         uncast/cast equal          no cast needed
    TEMPLATE_TO_SLOT        uncast/cast equal          no cast needed

T088 supplied the missing cast (`categories._cast_to_concrete`). The
`CAST_REQUIRED` verdicts above did NOT change and never will -- they describe
pythonnet, not this repo. What changed is `producer_output`: over the same two
corpora `affixes_dependencies` went from 0 edges to 1063 and 405, and
`adhoc_compound_rules_dependencies` from 0 to 4. That split is why the two
signals are asserted separately below.

The cause is pythonnet static-type resolution. `ILexEntry.
MorphoSyntaxAnalysesOC` is a POLYMORPHIC collection typed
`IMoMorphSynAnalysis`, and `PartOfSpeechRA`, `InflFeatsOA` and `MsFeaturesOA`
are declared on the concrete MSA subclasses, NOT on that base interface. So
`categories._entry_pos_deps`'s `getattr(msa, "PartOfSpeechRA", None)` is
unconditionally None against a real project, while every offline test passes
because the duck-typed fakes carry the attribute directly on the fake.

This is the same defect shape as flexicon 4.5.0, which CLAUDE.md records at
length: a `hasattr(nc, "FeaturesOA")` gate that was ALWAYS False, dead for 100%
of live natural classes while all 1467 flexicon tests passed, because those
tests built factory-fresh CONCRETE-typed objects. The lesson repeated here is
that a producer's unit tests cannot establish that the producer reads anything.

TWO CORPORA, DELIBERATELY. A verdict from one project could be a property of
that project's data. `Mbugwe LizzieHC practice` (255 entries, 279 MSAs) and
`Ejagham Mini` (252 entries, 247 MSAs) return identical verdicts on all five
edges, which makes it a property of the producer.

WHAT T067 REGISTERED, AND WHAT IT REFUSED A SECOND TIME.

T088 made the producers read. It registered nothing, because "the producer
works" is not "the edge is verified" -- and because `affixes_dependencies`
returns a MIXED edge set (measured: gram_categories, feature_struct_types and
inflection_features all in one return value) that a single-`DependencyKind`
registry row would mislabel under one `verified_by`.

T067 resolved that with NARROW per-relationship producers and then audited each
one separately -- the `relationships` block of the snapshot. Per relationship it
measures three things a composite count cannot: `foreign_edges` (is the producer
actually narrow?), and whether each distinct far GUID resolves against the far
category's OWN `enumerate_source` as an enumerable piece, as a co-created owned
value, or not at all.

    AFFIX_TO_POS            144 / 88 edges, foreign 0, unresolved 0  REGISTERED
    MSA_TO_FEAT_STRUC_TYPE   73 / 17 edges, foreign 0, unresolved 0  REGISTERED
    MSA_TO_INFL_FEATURE     206 / 34 edges, foreign 0               REFUSED

The refusal is the interesting one, and it is a different defect from T088's.
The producer is narrow and its edges are live. But of its 34 distinct far GUIDs
on Mbugwe (10 on Ejagham Mini), only 4 (2) are pieces
`inflection_features_enumerate_source` yields -- that enumerator walks
`FeatureGetAll()`, the feature DEFNS. The other 30 (8) are `IFsSymFeatVal`
SYMBOLIC VALUES, which `inflection_features_dependencies` itself records are
"co-created in execute_action, not separately planned". A pulled-in ref naming
a piece no category can enumerate cannot be planned, marked (T070) or
deselected (T072). Filed as T089; NOT registered.

WHAT T089 DID TO THAT REFUSAL, AND WHY THE ROW IS STILL NOT REGISTERED.

    MSA_TO_INFL_FEATURE      99 /  4 edges, foreign 0, unresolved 0  CONFIRMED
                             17 /  2 edges, owned 0                  CONFIRMED

T089 re-pointed each `ValueRA` edge at the feature that OWNS the value -- the
piece that IS planned, and whose `execute_action` creates the value -- so the
far endpoint became one the category can enumerate. The numbers moved the way
a CORRECTION moves numbers rather than the way a registration does: the edge
set got SMALLER (206 -> 99, 34 -> 17) and the distinct far GUIDs collapsed onto
the ones that already existed (34 -> 4, 10 -> 2), because many values of one
feature are one feature. `resolved_as_owned_value` is 0 on both corpora.

The row stayed absent from `CLOSURE_EDGES_VERIFIED` for one more task, and that
was not an oversight -- see `_CONFIRMED_NOT_REGISTERED` below, which is the
vocabulary this file grew to say so. T089's own task text separates the two:
"the fix is a live-behaviour change and must not be folded into a
registration". The fix has its OWN census (`debug/run038_t089_census.py`,
`_snapshots/closure-producer-038-t089.json`), whose axis is the producer rather
than the registry, and which measured what the structural argument predicted:
with the registry held fixed at 7 rows, the full-copy plan and the AFFIXES-only
plan are IDENTICAL before and after the fix (0 and 259 closure edges either
way), and the resulting census reproduces `census-038-t076-registered.json` row
for row.

WHAT T104 REGISTERED, AND WHY IT IS A SEPARATE TASK RATHER THAN T089'S LAST
PARAGRAPH.

    MSA_TO_INFL_FEATURE      99 /  4 edges, foreign 0, unresolved 0  REGISTERED
                             17 /  2 edges, owned 0

The audit above was already done -- this is the only row in the registry whose
confirming measurement was committed by a PREVIOUS task -- so T104 is not a new
investigation. What it adds is the OTHER AXIS. A registration census varies the
REGISTRY with the producer held fixed (`debug/run038_closure_census.py T104`),
and answers "does registering this row change a decision it should not?".
T089's census varies the PRODUCER with the registry held fixed, and answers
"did the fix change a plan?". A driver that answers one cannot answer the
other, and running the second one twice would look like diligence while
measuring nothing new.

Its `expect_kinds` names ALL FIVE AFFIXES rows, not just the new one, because
the observing selection is AFFIXES-only and the same pieces carry every AFFIXES
relationship -- a list naming only `MSA_TO_INFL_FEATURE` would fail for the
four that were already correct.

WHAT T068 REGISTERED, AND THE MEMBER IT HAD TO ADD.

    SLOT_TO_POS              19 /  9 edges, foreign 0, unresolved 0  REGISTERED

`slots_dependencies` audited clean the first time it was measured, and the
reason is checkable rather than lucky: it reads only `Owner`, which IS declared
on `ICmObject`, so the bare `getattr` sees it on the base-typed proxy
`AffixSlotsOC` yields and T088's defect cannot apply. 19 edges over 5 distinct
POSes on Mbugwe, 9 over 6 on Ejagham Mini.

What it did NOT have was a `DependencyKind`. The plan's member list named
`SLOT_TO_TEMPLATE`, and that is a different relationship pointing the other
way: `IMoInflAffixSlot`'s own properties are Name, Description, Optional,
Affixes and OtherInflectionalAffixLexEntries -- no template reference exists to
read, so no producer can emit a slot->template edge, while
`IMoInflAffixTemplate` references its slots through five `*SlotsRS` sequences.
`DependencyKind.SLOT_TO_POS` was added instead of the wrong member being
borrowed. A live relationship filed under another relationship's name passes
registration and then mislabels every FR-015 surface (T070) and every
deselection (T072) -- the substitution FR-018 forbids, moved one step
downstream to where nothing checks for it.

WHAT T069 REGISTERED, AND THE SECOND MEMBER IT HAD TO ADD.

    TEMPLATE_TO_POS          11 /  7 edges, foreign 0, unresolved 0  REGISTERED
    TEMPLATE_TO_SLOT         24 /  9 edges, foreign 0, unresolved 0  REGISTERED

`affix_templates_dependencies` is the module's second MIXED producer -- one
call returns the owning POS (GRAM_CATEGORIES) and every slot referenced across
the five `*SlotsRS` sequences (SLOTS) -- so it needed T067's split: two narrow
producers, two rows, each with an EXPLICIT `dependency_category`. Unlike T067
the split is bookkeeping rather than a blocked audit: both halves measured
`NO_CAST_NEEDED` on both corpora, because `Owner` is on `ICmObject` and the
`*SlotsRS` sequences are on `IMoInflAffixTemplate` itself.

`TEMPLATE_TO_POS` already existed. The slot half did not, and the `edges` block
above was reporting it under `AFFIX_TO_SLOT` -- a different arrow off a
different owner (`IMoInflAffMsa.SlotsRC`, carried as
`RunPlan.msa_slot_bindings` for the 17.1 sub-pass, FR-019 / SC-003 / T074's
surface). T069 added `DependencyKind.TEMPLATE_TO_SLOT` and RENAMED the `edges`
key to match what it has always measured.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_SNAPSHOT_DIR = Path(__file__).parent / "_snapshots"
_PATTERN = "closure-edge-audit-038-*.json"

#: Sites where a cast is MANDATORY -- the attribute is subclass-only, so a
#: bare `getattr` sees nothing. A permanent property of pythonnet and LCM, not
#: a defect report: T088 fixed the producers and these stayed CAST_REQUIRED.
_CAST_REQUIRED_EDGES = ("AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE")

#: Sites where no cast is needed, because the attribute IS declared on the
#: collection's element type (`Owner` on `ICmObject`, the `*SlotsRS`
#: sequences on `IMoInflAffixTemplate`). This is why T068 / T069 audited
#: clean while T067 did not.
#: `TEMPLATE_TO_SLOT` was called `AFFIX_TO_SLOT` here until T069. The block
#: has always measured `IMoInflAffixTemplate`'s five `*SlotsRS` sequences --
#: a TEMPLATE->slot reference. `AFFIX_TO_SLOT` is `IMoInflAffMsa.SlotsRC`, a
#: different arrow off a different owner, carried as
#: `RunPlan.msa_slot_bindings` rather than as a dependency edge.
_NO_CAST_EDGES = ("SLOT_TO_POS", "TEMPLATE_TO_POS", "TEMPLATE_TO_SLOT")

#: Producers that must return edges on any corpus that actually holds their
#: input. This is the T088 regression guard: it is the signal that moved.
_PRODUCERS = (
    "affixes_dependencies",
    "stems_dependencies",
    "adhoc_compound_rules_dependencies",
)


def _snapshots() -> list:
    files = sorted(_SNAPSHOT_DIR.glob(_PATTERN))
    if not files:
        pytest.skip(
            "no committed audit measurement matching "
            + str(_SNAPSHOT_DIR / _PATTERN)
            + " -- produce it with `python debug/audit038_closure_edges.py`"
        )
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def _ids(snaps) -> list:
    return [s["source_project"] for s in snaps]


# ---------------------------------------------------------------------------
# The audit ran at all, on real data
# ---------------------------------------------------------------------------

def test_the_audit_covered_two_independent_corpora() -> None:
    """One project agreeing with itself is not corroboration. A verdict that
    should be a property of the PRODUCER has to reproduce on a second corpus
    with different data."""
    snaps = _snapshots()
    assert len(snaps) >= 2, (
        "these verdicts rest on cross-corpus agreement; got only "
        + ", ".join(_ids(snaps))
    )


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_audit_is_read_only_and_saw_real_pieces(snap) -> None:
    """A verdict computed over an empty enumeration is not a verdict. This is
    what makes `NO_DATA` a distinct verdict in the driver."""
    assert snap["read_only"] is True
    pop = snap["population"]
    assert pop["lex_entries"] > 0
    assert pop["msas"] > 0
    assert pop["slots"] > 0
    assert pop["templates"] > 0


# ---------------------------------------------------------------------------
# Signal 1 -- the read pattern. Permanent; describes pythonnet, not this repo.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_a_cast_is_still_mandatory_at_the_msa_sites(snap) -> None:
    """`uncast == 0` while `cast > 0` is the finding that blocked T067, and it
    must NOT go away now that T088 has fixed the producers.

    If this ever flips to `NO_CAST_NEEDED`, the honest reading is not "the bug
    fixed itself" -- a base-typed pythonnet proxy cannot grow a subclass-only
    property. It means the driver stopped measuring the raw pattern, and the
    T088 regression guard below has quietly lost its baseline.
    """
    for edge in _CAST_REQUIRED_EDGES:
        row = snap["edges"][edge]
        assert row["verdict"] == "CAST_REQUIRED", edge + " -> " + row["verdict"]
        assert row["uncast"] == 0
        assert row["cast"] > 0


#: The registered relationships, and the one that is not. Keyed by the
#: `DependencyKind` NAME so the table can be read next to the snapshot's
#: `relationships` block, which is keyed the same way.
_REGISTERED = ("AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE", "SLOT_TO_POS",
               "TEMPLATE_TO_POS", "TEMPLATE_TO_SLOT",
               "PROCESS_RULE_TO_PHONEME", "PROCESS_RULE_TO_NATURAL_CLASS",
               "MSA_TO_INFL_FEATURE")
#: Relationships the audit REFUSES. Empty since T089, and deliberately kept
#: as a name rather than deleted: it is the list a future refusal goes on, and
#: the tests below still enforce that everything on it stays out of the
#: registry.
_REFUSED: tuple = ()

#: CONFIRMED by the audit and NOT registered, on purpose.
#:
#: EMPTY since T104, and deliberately kept as a name rather than deleted --
#: for the same reason `_REFUSED` is kept. This third state is the one that
#: most needs a place to live, because a row sitting in it is
#: indistinguishable from an oversight if there is nowhere to write down that
#: it is not one.
#:
#: `MSA_TO_INFL_FEATURE` is the row that put it here and the row that
#: emptied it. It measured `REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE` until
#: 2026-08-22: 30 of its 34 distinct far GUIDs on `Mbugwe LizzieHC practice`
#: (8 of 10 on `Ejagham Mini`) were `IFsSymFeatVal` symbolic values that
#: `inflection_features_enumerate_source` never yields, so a pulled-in ref
#: naming one could be neither planned (FR-015) nor deselected (FR-016).
#: T089 re-pointed the `ValueRA` edge at the feature that OWNS the value and
#: the relationship went CONFIRMED on both corpora with the edge set
#: SMALLER (206 edges over 34 far GUIDs -> 99 over 4; 34 over 10 -> 17 over
#: 2, `resolved_as_owned_value` 0 in both) -- and T089 still did not
#: register it, because its own task text forbids folding a live-behaviour
#: change into a registration. It sat here, CONFIRMED and unregistered, until
#: **T104** ran the census that a registration actually requires
#: (`debug/run038_closure_census.py T104`, the axis that holds the producer
#: fixed and varies the REGISTRY, which T089's census could not measure).
#:
#: A future row goes here the same way: measured registrable, not yet
#: measured safe to register.
_CONFIRMED_NOT_REGISTERED: tuple = ()

#: How many of the audited corpora must return CONFIRMED for each registered
#: relationship. T076 is the reason this is a table rather than "all of them".
#:
#: `Ejagham Mini` holds ZERO `MoAffixProcess` rules, so its reading for the
#: two process-rule rows is `NO_DATA` -- which the driver deliberately
#: distinguishes from `CONFIRMED` precisely so a corpus that holds nothing
#: cannot rubber-stamp an edge. A corpus with no instances can neither confirm
#: NOR refuse a relationship, and demanding CONFIRMED from it would force one
#: of two bad answers: refuse a relationship whose only corpus confirms it, or
#: teach `NO_DATA` to count as a pass, which is the exact failure the verdict
#: vocabulary exists to prevent.
#:
#: So the rule the tests enforce is: **CONFIRMED by at least this many
#: corpora, and REFUSED by none.** The number is pinned per relationship so a
#: single-corpus row stays visibly weaker than a two-corpus one, and so that
#: a second corpus with affix process rules -- if one is ever sanctioned --
#: has to be reckoned with here rather than absorbed silently.
_MIN_CONFIRMING_CORPORA = {
    "AFFIX_TO_POS": 2,
    "MSA_TO_FEAT_STRUC_TYPE": 2,
    "SLOT_TO_POS": 2,
    "TEMPLATE_TO_POS": 2,
    "TEMPLATE_TO_SLOT": 2,
    "PROCESS_RULE_TO_PHONEME": 1,
    "PROCESS_RULE_TO_NATURAL_CLASS": 1,
    # T104. TWO, not one: unlike the process-rule rows above, this
    # relationship has data on BOTH corpora (99 edges over 4 distinct far
    # GUIDs on `Mbugwe LizzieHC practice`, 17 over 2 on `Ejagham Mini`), so
    # there is no corpus here whose silence has to be excused. A floor of 1
    # would be a weaker claim than the evidence supports and would let a
    # future regression on one corpus pass unnoticed.
    "MSA_TO_INFL_FEATURE": 2,
}


def test_only_the_confirmed_relationships_are_registered() -> None:
    """THE TEST BOTH REGISTERED ROWS NAME IN THEIR `verified_by`.

    It closes the loop FR-018 depends on: the registry may hold a row only if
    the committed live measurement says CONFIRMED for that relationship, and
    must hold no row whose measurement says otherwise. Both directions are
    asserted, on every corpus, because either one alone is satisfiable by a
    mistake -- a missing row passes a "registered implies confirmed" check, and
    a rubber-stamped row passes a "confirmed implies registered" one.

    This is deliberately NOT "the registry is non-empty". A count assertion
    would pass on a registry that had grown a row nobody measured.

    T076 WIDENED the CONFIRMED clause, and the widening is narrow enough to
    state exactly. It used to read "CONFIRMED on every corpus". `Ejagham Mini`
    holds zero `MoAffixProcess` rules, so it reads `NO_DATA` for the two
    process-rule rows -- a verdict that is neither evidence for the
    relationship nor against it. The clause is now:

      * REFUSED on NO corpus (unchanged, and this is the half that bites);
      * CONFIRMED on at least `_MIN_CONFIRMING_CORPORA[name]` of them, which
        is 2 for every row that has data on both and 1 for the two that can
        only be measured where the rules exist;
      * every non-CONFIRMED reading is `NO_DATA` and nothing else, so
        "confirmed by fewer corpora" can only ever mean "the corpus held
        none", never "the corpus disagreed".

    That last clause is what keeps this from being a relaxation: a row cannot
    reach the registry on zero confirmations, and it cannot reach it with a
    single dissent hidden behind a single agreement.
    """
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import DependencyKind

    registered_names = {k.name for k in categories.CLOSURE_EDGES_VERIFIED}
    assert registered_names == set(_REGISTERED)
    assert set(_MIN_CONFIRMING_CORPORA) == set(_REGISTERED), (
        "every registered relationship needs a confirming-corpora floor"
    )

    snaps = _snapshots()
    for name in _REGISTERED:
        verdicts = {s["source_project"]: s["relationships"][name]["verdict"]
                    for s in snaps}
        confirmed = [p for p, v in verdicts.items() if v == "CONFIRMED"]
        others = {p: v for p, v in verdicts.items() if v != "CONFIRMED"}
        assert all(v == "NO_DATA" for v in others.values()), (
            name + " is REGISTERED but some corpus measured it something "
            "other than CONFIRMED or NO_DATA: " + repr(others)
        )
        assert len(confirmed) >= _MIN_CONFIRMING_CORPORA[name], (
            name + " is REGISTERED on " + str(len(confirmed))
            + " confirming corpus/corpora, below its recorded floor of "
            + str(_MIN_CONFIRMING_CORPORA[name]) + ": " + repr(verdicts)
        )

    for snap in snaps:
        rels = snap["relationships"]
        for name in _REFUSED:
            assert rels[name]["verdict"].startswith("REFUSED"), (
                name + " measured " + rels[name]["verdict"] + " on "
                + snap["source_project"] + " -- if that is now CONFIRMED the "
                "registration decision has to be revisited deliberately, not "
                "by relaxing this test"
            )
            assert getattr(DependencyKind, name) \
                not in categories.CLOSURE_EDGES_VERIFIED

        # T089's third state. Both halves, because each alone is satisfied
        # by the mistake the other catches: asserting only "confirmed" would
        # pass on a row that had been quietly registered, and asserting only
        # "not registered" would pass on a row that had quietly gone back to
        # being refused.
        for name in _CONFIRMED_NOT_REGISTERED:
            assert rels[name]["verdict"] == "CONFIRMED", (
                name + " measured " + rels[name]["verdict"] + " on "
                + snap["source_project"] + " -- T089 fixed its far endpoint, "
                "so a non-CONFIRMED reading means the fix regressed or the "
                "corpus changed under it"
            )
            assert getattr(DependencyKind, name) not in (
                categories.CLOSURE_EDGES_VERIFIED), (
                name + " is CONFIRMED and is now REGISTERED. That is the "
                "right end state reached the wrong way: registering it needs "
                "its own census against a restored target (T104), and T089's "
                "task text forbids folding the two together. Move the name "
                "from _CONFIRMED_NOT_REGISTERED to _REGISTERED when that "
                "census exists."
            )

    assert not (set(_REGISTERED) & set(_CONFIRMED_NOT_REGISTERED))
    assert not (set(_REFUSED) & set(_CONFIRMED_NOT_REGISTERED))


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_a_confirmed_relationship_means_narrow_and_resolvable(snap) -> None:
    """What CONFIRMED is allowed to mean, spelled out so the verdict string
    cannot drift away from the numbers behind it.

    `foreign_edges == 0` is the narrowness half: a producer emitting a second
    far category would put an unaudited relationship into a plan under this
    one's `verified_by`. `unresolved == 0` and `resolved_as_owned_value == 0`
    are the far-endpoint half: every GUID the producer emits must name a piece
    the far category's own `enumerate_source` yields, or the pulled-in item
    cannot be planned or deselected.

    T076: a `NO_DATA` row on a corpus that holds none of the relationship is
    skipped HERE and only here, because these five numbers describe what a
    producer returned and a producer that was handed nothing returned nothing.
    The zero-edge case is not waved through, though -- the four assertions
    below still run on it, and `test_only_the_confirmed_relationships_are_
    registered` separately proves that every `NO_DATA` reading belongs to a
    relationship confirmed somewhere else. Asserting `edges > 0` on a corpus
    with no affix process rules would be asserting that `Ejagham Mini` has
    data it does not have.
    """
    # T089 adds `_CONFIRMED_NOT_REGISTERED`. Its whole content is a claim
    # about resolvability -- the fix exists so every far GUID names a piece
    # the far category can enumerate -- so the row that carries that claim
    # has to be held to it here, not only where registration is checked.
    for name in _REGISTERED + _CONFIRMED_NOT_REGISTERED:
        row = snap["relationships"][name]
        if row["verdict"] == "NO_DATA":
            assert row["edges"] == 0, name
            assert row["foreign_edges"] == 0, name
            assert row["unresolved"] == 0, name
            assert row["distinct_far_guids"] == 0, name
            continue
        assert row["edges"] > 0, name
        assert row["foreign_edges"] == 0, name
        assert row["unresolved"] == 0, (name, row["unresolved_sample"])
        assert row["resolved_as_owned_value"] == 0, name
        assert row["resolved_as_piece"] == row["distinct_far_guids"], name


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_formerly_refused_relationship_now_names_only_enumerable_defns(snap) -> None:
    """T089, and the inversion of what this test used to assert.

    It used to demand `resolved_as_owned_value > 0` and the
    `REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE` verdict, with the note that "if that
    ever stops being true, this test fails and the registration decision gets
    made again on new evidence, which is the correct way for it to change."
    That is what happened: it was made to stop being true, deliberately, and
    the decision was made again on the new numbers.

    `MSA_TO_INFL_FEATURE` was never refused for a broken producer -- it
    returned edges and none was foreign. It was refused because most of its
    far GUIDs were `IFsSymFeatVal` symbolic values that
    `inflection_features_enumerate_source` never yields, so a pulled-in ref
    naming one had no `PlannedAction`, no FR-015 row and no FR-016 checkbox.
    T089 re-pointed those edges at the feature that OWNS the value.

    What is asserted now is the SAME property from the other side, and it is
    stricter than the old assertion rather than looser: not merely "few owned
    values" but ZERO, every distinct far GUID resolving as an enumerable
    piece, and the edge set SMALLER than before (99 / 17 against 206 / 34) --
    because the fix collapses many values onto the one feature that owns them
    rather than adding a second endpoint beside each.
    """
    row = snap["relationships"]["MSA_TO_INFL_FEATURE"]
    assert row["edges"] > 0
    assert row["foreign_edges"] == 0
    assert row["resolved_as_owned_value"] == 0, (
        "an owned symbolic value is still reaching the far endpoint, which is "
        "the defect T089 fixed: " + repr(row)
    )
    assert row["unresolved"] == 0, (row["unresolved_sample"],)
    assert row["resolved_as_piece"] == row["distinct_far_guids"] > 0
    assert row["verdict"] == "CONFIRMED"


def test_the_per_relationship_counts_are_recorded_per_corpus() -> None:
    """The narrow-producer figures, pinned like the composite ones above.

    Note they do NOT sum to `affixes_dependencies`' total: that producer is
    measured over EVERY LexEntry, while these are measured over
    `affixes_enumerate_source`'s output -- the pieces the registry will
    actually hand them. The gap is stems, and it is the reason the composite
    count could not have earned these rows their `verified_by`.
    """
    expected = {
        "Mbugwe LizzieHC practice": {
            "AFFIX_TO_POS": 144,
            "MSA_TO_FEAT_STRUC_TYPE": 73,
            "MSA_TO_INFL_FEATURE": 99,   # T089: was 206 over 34 far GUIDs
            "SLOT_TO_POS": 19,
            "TEMPLATE_TO_POS": 11,
            "TEMPLATE_TO_SLOT": 24,
        },
        "Ejagham Mini": {
            "AFFIX_TO_POS": 88,
            "MSA_TO_FEAT_STRUC_TYPE": 17,
            "MSA_TO_INFL_FEATURE": 17,   # T089: was 34 over 10 far GUIDs
            "SLOT_TO_POS": 9,
            "TEMPLATE_TO_POS": 7,
            "TEMPLATE_TO_SLOT": 9,
        },
    }
    got = {
        snap["source_project"]: {
            name: snap["relationships"][name]["edges"]
            for name in expected[snap["source_project"]]
        }
        for snap in _snapshots()
        if snap["source_project"] in expected
    }
    assert got == expected, (
        "narrow-producer edge counts moved: " + repr(got) + " -- re-run "
        "debug/audit038_closure_edges.py and update this if the change is "
        "intended"
    )


# ---------------------------------------------------------------------------
# Signal 2 -- what the producers return. This is the T088 regression guard.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_each_relationship_was_measured_over_its_own_source_category(snap) -> None:
    """The instrument error T067's journal records, pinned so it cannot come
    back when a fourth relationship is added.

    T067's first per-relationship measurement counted a COMPOSITE producer
    over every LexEntry, and was therefore worth nothing to a registry keyed
    per relationship. The fix was to measure each producer over the pieces the
    registry will actually hand it -- its OWN source category's
    `enumerate_source`. `SLOT_TO_POS` is the row that makes that concrete: its
    population is the SLOT count (19 / 9), not the entry count, and a row
    measured over the wrong pieces would show up here as a population that
    matches some other category's.
    """
    pop = snap["population"]
    expected = {
        # AFFIXES enumerates a SUBSET of the lexicon, so the exact number is
        # the corpus's business -- but it must not silently become the whole
        # lexicon, which is what the discredited measurement did.
        "AFFIX_TO_POS": ("affixes", None),
        "MSA_TO_FEAT_STRUC_TYPE": ("affixes", None),
        "MSA_TO_INFL_FEATURE": ("affixes", None),
        "SLOT_TO_POS": ("slots", pop["slots"]),
        "TEMPLATE_TO_POS": ("affix_templates", pop["templates"]),
        "TEMPLATE_TO_SLOT": ("affix_templates", pop["templates"]),
        # T076. Measured over AFFIXES pieces, the same population as the three
        # rows above -- the rules are allomorphs hanging off those entries, so
        # a population equal to the SLOT or TEMPLATE count here would mean the
        # producer had been handed the wrong pieces.
        "PROCESS_RULE_TO_PHONEME": ("affixes", None),
        "PROCESS_RULE_TO_NATURAL_CLASS": ("affixes", None),
    }
    assert set(expected) == set(snap["relationships"]), (
        "a relationship was added to or removed from the audit without this "
        "population check being extended: "
        + repr(sorted(set(expected) ^ set(snap["relationships"])))
    )
    for name, (src_cat, want) in expected.items():
        row = snap["relationships"][name]
        assert row["population"] > 0, name
        assert row["source_category"] == src_cat, (name, row["source_category"])
        if want is None:
            assert row["population"] <= pop["lex_entries"], name
        else:
            assert row["population"] == want, (name, row["population"], want)


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_every_producer_returns_edges_on_a_corpus_that_has_them(snap) -> None:
    """The assertion that would have failed before T088, on every producer,
    over both corpora.

    Gated on `population` because 0 edges is the CORRECT answer for a producer
    whose input the corpus does not contain -- Ejagham Mini holds no adhoc
    rules. Reporting that as a pass would be the same mistake in the other
    direction, so it is reported as untested instead.
    """
    for label in _PRODUCERS:
        row = snap["producer_output"][label]
        if row["population"] == 0:
            continue
        assert row["total_edges"] > 0, (
            label + " returned no edges over " + str(row["population"])
            + " piece(s) -- T088 has regressed"
        )


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_affix_producer_returns_all_three_far_categories(snap) -> None:
    """A non-zero total is not enough: it would be satisfied by the POS half
    working while T034's feature-structure half stayed dead, which is exactly
    the state the audit found.

    Both halves are asserted separately, and their presence together is also
    the evidence for T067's remaining member-split problem -- one producer,
    three far categories, one registry key.
    """
    row = snap["producer_output"]["affixes_dependencies"]
    by_far = row["by_far_category"]
    for far in ("gram_categories", "feature_struct_types", "inflection_features"):
        assert by_far.get(far, 0) > 0, (
            "affixes_dependencies returned no " + far + " edges: " + repr(by_far)
        )


def test_the_producer_counts_are_recorded_per_corpus() -> None:
    """The measured figures, pinned so a change is visible rather than
    inferred. These are the numbers that were 0 before T088."""
    expected = {
        # T089 moved both, and DOWNWARD: 1063 -> 756 and 405 -> 345. The
        # composite's `inflection_features` half is where it all happened
        # (606 -> 299 and 120 -> 60), because each `FeatureSpecsOC` entry used
        # to contribute a `FeatureRA` edge AND a distinct `ValueRA` edge and
        # now contributes one de-duplicated edge naming the owning feature.
        # A registration is the only thing that can make a plan larger; this
        # was a correction, and a correction that ADDED edges would have been
        # the suspicious outcome.
        "Mbugwe LizzieHC practice": 756,
        "Ejagham Mini": 345,
    }
    got = {
        snap["source_project"]:
            snap["producer_output"]["affixes_dependencies"]["total_edges"]
        for snap in _snapshots()
    }
    assert got == expected, (
        "affixes_dependencies edge counts moved: " + repr(got)
        + " -- re-run debug/audit038_closure_edges.py and update this if the "
        "change is intended"
    )


# ---------------------------------------------------------------------------
# The other half: three edges audited clean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_no_cast_edges_read_correctly_uncast(snap) -> None:
    """These three read `Owner` and the template slot sequences, all of which
    ARE declared on the collections' element types -- so the uncast read the
    producer performs matches the cast ground truth exactly.

    This is the half that makes `CAST_REQUIRED` meaningful: the audit is
    capable of returning `NO_CAST_NEEDED`, so a `CAST_REQUIRED` verdict is a
    real difference and not just the harness failing to see anything.
    """
    for edge in _NO_CAST_EDGES:
        row = snap["edges"][edge]
        assert row["verdict"] == "NO_CAST_NEEDED", edge + " -> " + row["verdict"]
        assert row["uncast"] == row["cast"] > 0


def test_the_verdicts_agree_across_corpora() -> None:
    """The cross-corpus check, stated as one assertion over the whole edge
    set rather than per project: a producer-level property must not depend on
    which project it was measured in."""
    snaps = _snapshots()
    per_edge: dict = {}
    for snap in snaps:
        for edge, row in snap["edges"].items():
            per_edge.setdefault(edge, set()).add(row["verdict"])
    disagreements = {e: v for e, v in per_edge.items() if len(v) > 1}
    assert not disagreements, (
        "these edges got different verdicts on different corpora, so the "
        "verdict is a property of the data rather than of the producer: "
        + repr(disagreements)
    )


# ---------------------------------------------------------------------------
# T067's CENSUS -- what registering the two rows actually did to a live plan
# ---------------------------------------------------------------------------
#
# Driver: `debug/run038_t067_census.py` (restores a throwaway target first).
# Artifacts: `_snapshots/closure-registration-038-t067.json` (the plan
# measurements) and `_snapshots/census-038-t067-registered.json` (the census
# run), the latter directly comparable with `census-038-mbugwe-phase6.json` --
# T063/T064's run over the SAME source, the SAME backup and the SAME full-copy
# selection, with the registry EMPTY.
#
# THE SEED-SEMANTICS FINDING, which the driver's first version got wrong. A
# FULL COPY carries ZERO closure edges with the registry live, and that is
# correct: `closure.walk` never records a seed as pulled in, and in a full copy
# every POS and every `FsFeatStrucType` is a seed in its own right. So a
# registered edge is observable ONLY under a partial selection -- Phase 7's own
# Independent Test, "select only affixes". Both selections are asserted below,
# because each one alone is satisfied by a different mistake: the full copy
# alone would call a working edge inert, and the narrow one alone could not
# tell "adds edges" from "changes the plan".

def _census_table(doc) -> dict:
    """One census artifact reduced to the per-class row every comparison
    below is made on.

    Shared rather than nested inside one test, because each registration is
    compared against the PREVIOUS one and a second copy of this projection is
    how two comparisons quietly stop meaning the same thing.
    """
    return {
        row["class"]: (
            row["source_count"],
            row["destination_count_total"],
            row["destination_count_net"],
            row["difference"],
            row["verdict_class"],
            row["unexplained_shortfall"],
        )
        for row in doc["classes"]
    }


_REG_SNAPSHOT = _SNAPSHOT_DIR / "closure-registration-038-t067.json"
_CENSUS_POST = _SNAPSHOT_DIR / "census-038-t067-registered.json"
_CENSUS_PRE = _SNAPSHOT_DIR / "census-038-mbugwe-phase6.json"


def _registration() -> dict:
    if not _REG_SNAPSHOT.is_file():
        pytest.skip(
            "no committed registration measurement at " + str(_REG_SNAPSHOT)
            + " -- produce it with `python debug/run038_t067_census.py`")
    return json.loads(_REG_SNAPSHOT.read_text(encoding="utf-8"))


def test_a_full_copy_carries_no_closure_edges_and_that_is_correct() -> None:
    """Seed semantics, pinned so nobody reads this 0 as "the rows are inert".

    Every far endpoint of both registered relationships is itself a seed in a
    full copy, and `closure.walk`'s contract is that an item the user picked
    directly is never reported as pulled in by another. A non-zero count here
    would mean the walk started manufacturing edges for items already chosen,
    which would double-count them in every downstream FR-015 surface.
    """
    reg = _registration()
    assert reg["full_copy"]["registry_live"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["registry_empty"]["closure"]["total_edges"] == 0


def test_an_affixes_only_plan_carries_the_registered_edges() -> None:
    """The claim registration actually makes, measured on the one selection
    that can observe it.

    Both relationships are asserted separately and by far category, because a
    single total would be satisfied by the POS half working while T034's
    feature-structure half stayed dead -- the exact state the first audit
    found. Every edge must be `origin="pulled_in"` (a "chosen" edge here would
    mean the seed set leaked into the closure) and must carry a non-empty
    `verified_by` (a registry validated at build time and then losing its
    evidence on the way to the plan would defeat FR-018 silently).
    """
    reg = _registration()
    live = reg["affixes_only"]["registry_live"]["closure"]
    assert live["total_edges"] == 217
    assert set(live["by_kind"]) == {"AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE"}
    assert live["by_kind"]["AFFIX_TO_POS"] == {
        "edges": 144,
        "far_categories": {"gram_categories": 144},
        "origins": {"pulled_in": 144},
        "verified_by_nonempty": True,
    }
    assert live["by_kind"]["MSA_TO_FEAT_STRUC_TYPE"] == {
        "edges": 73,
        "far_categories": {"feature_struct_types": 73},
        "origins": {"pulled_in": 73},
        "verified_by_nonempty": True,
    }
    # 217 edges over only 8 distinct dependencies: many affixes share a POS.
    # That is what makes closure worth having, and it is also why the edge
    # count and the pulled-in-item count are reported separately.
    assert live["distinct_pulled_in_refs"] == 8
    assert live["pulled_in_by_category"] == {
        "feature_struct_types": 2, "gram_categories": 6}


def test_the_edges_come_from_the_registry_and_nowhere_else() -> None:
    """Emptying the registry must take the edges with it.

    Without this, `test_an_affixes_only_plan_carries_the_registered_edges` is
    satisfied by any code path that produces closure edges -- including one
    that ignores `CLOSURE_EDGES_VERIFIED` entirely, which is precisely the
    fall-through FR-018 forbids.
    """
    reg = _registration()
    assert reg["affixes_only"]["registry_empty"]["closure"]["total_edges"] == 0


def test_registration_changed_no_plan_decision_under_either_selection() -> None:
    """T070 (marking pulled-in items) and T072 (deselecting them) have not
    landed, so at this stage registration must add EDGES and change nothing
    else -- not one action, skip or overwrite, under either selection.

    This is the assertion that makes the registration safe to land ahead of
    T070/T072 rather than a silent change of what gets transferred.
    """
    reg = _registration()
    assert reg["full_copy"]["composition_unchanged_by_registration"] is True
    assert reg["affixes_only"]["composition_unchanged_by_registration"] is True
    assert reg["plan_composition_unchanged_by_registration"] is True
    for scope in ("full_copy", "affixes_only"):
        assert (reg[scope]["registry_live"]["composition"]
                == reg[scope]["registry_empty"]["composition"]), scope


def test_the_census_is_unchanged_by_the_registration() -> None:
    """The census T067 owed, expressed as the comparison that makes it mean
    something.

    A census artifact on its own says only "this transfer lost these objects".
    The question registration raises is whether it lost DIFFERENT ones, so the
    post-registration artifact is compared row by row against T063/T064's
    pre-registration run -- same source, same backup, same full-copy selection,
    two separately restored targets. Identical class tables and identical
    totals is the answer: registering the two rows moved no object count.

    The shared `DUPLICATE_IDENTITY` / exit 3 is NOT a US3 regression and is
    already recorded under T064: `PhNCFeatures` carries 23 duplicate
    natural-key groups over 66 extra objects, all FLEx-auto-generated
    "Created automatically for rule ..." classes that the source itself
    duplicates. Asserting the two runs agree on it keeps that reading intact.
    """
    for path in (_CENSUS_PRE, _CENSUS_POST):
        if not path.is_file():
            pytest.skip("missing census artifact " + str(path))
    pre = json.loads(_CENSUS_PRE.read_text(encoding="utf-8"))
    post = json.loads(_CENSUS_POST.read_text(encoding="utf-8"))

    assert _census_table(post) == _census_table(pre)
    assert post["totals"] == pre["totals"]
    assert (post["verdict"], post["exit_code"]) \
        == (pre["verdict"], pre["exit_code"]) == ("DUPLICATE_IDENTITY", 3)


# ---------------------------------------------------------------------------
# T068's CENSUS -- what registering the SLOTS row did to a live plan
# ---------------------------------------------------------------------------
#
# Driver: `debug/run038_closure_census.py T068` (restores a throwaway target
# first). Artifacts: `_snapshots/closure-registration-038-t068.json` (the plan
# measurements) and `_snapshots/census-038-t068-registered.json` (the census
# run), the latter directly comparable with `census-038-t067-registered.json`
# -- the SAME source, the SAME backup and the SAME full-copy selection, with
# the registry holding T067's two rows instead of three.
#
# The selection that can observe this row is SLOTS-only, for the reason T067's
# journal records: `closure.walk` never reports a seed as pulled in, so in a
# full copy -- where every owning POS is a seed in its own right -- a correctly
# registered edge is INVISIBLE. Reading that 0 as "the row is inert" is the
# instrument error, not a finding.

_REG_T068 = _SNAPSHOT_DIR / "closure-registration-038-t068.json"
_CENSUS_T068 = _SNAPSHOT_DIR / "census-038-t068-registered.json"


def _reg_t068() -> dict:
    if not _REG_T068.is_file():
        pytest.skip(
            "no committed registration measurement at " + str(_REG_T068)
            + " -- produce it with `python debug/run038_closure_census.py "
            "T068`")
    return json.loads(_REG_T068.read_text(encoding="utf-8"))


def test_a_slots_only_plan_carries_the_registered_slot_to_pos_edges() -> None:
    """THE TEST T068's `verified_by` NAMES, alongside the audit one.

    19 edges over 5 distinct POSes is the shape that makes closure worth
    having, and it is why the EDGE count and the pulled-in ITEM count are
    asserted separately -- FR-015's surfaces (T070) and FR-016's deselection
    (T072) both act on the second number, not the first.

    Every edge must be `origin="pulled_in"` (a "chosen" edge here would mean
    the seed set leaked into the closure and every downstream surface would
    double-count it) and must carry a non-empty `verified_by` (a registry
    validated at build time and then losing its evidence on the way to the plan
    would defeat FR-018 silently).

    `by_kind` is asserted as an EXACT set: under a SLOTS-only selection the
    AFFIXES rows have no seeds, so an AFFIX_TO_POS edge appearing here would
    mean the walk had started from something the user did not select.
    """
    reg = _reg_t068()
    assert reg["task"] == "T068"
    assert reg["narrow_selection"] == "SLOTS"
    live = reg["narrow"]["registry_live"]["closure"]
    assert set(live["by_kind"]) == {"SLOT_TO_POS"}
    assert live["by_kind"]["SLOT_TO_POS"] == {
        "edges": 19,
        "far_categories": {"gram_categories": 19},
        "origins": {"pulled_in": 19},
        "verified_by_nonempty": True,
    }
    assert live["total_edges"] == 19
    assert live["distinct_pulled_in_refs"] == 5
    assert live["pulled_in_by_category"] == {"gram_categories": 5}


def test_the_slot_edges_come_from_the_registry_and_nowhere_else() -> None:
    """Emptying the registry must take the edges with it.

    Without this, the test above is satisfied by any code path that produces
    closure edges -- including one that ignores `CLOSURE_EDGES_VERIFIED`
    entirely, which is precisely the fall-through FR-018 forbids.
    """
    reg = _reg_t068()
    assert reg["narrow"]["registry_empty"]["closure"]["total_edges"] == 0


def test_a_full_copy_still_carries_no_closure_edges_after_t068() -> None:
    """Seed semantics, re-measured with three rows registered instead of two.

    Pinned per registration rather than once, because the claim is about the
    SEED SET and each new row adds a source category whose far endpoints might
    not have been seeds. A non-zero count here would mean the walk had started
    manufacturing edges for items the user picked directly.
    """
    reg = _reg_t068()
    assert reg["full_copy"]["registry_live"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["registry_empty"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["closure_edges_expected"] == 0


def test_t068_changed_no_plan_decision_under_either_selection() -> None:
    """T070 (marking pulled-in items) and T072 (deselecting them) have not
    landed, so at this stage a registration must add EDGES and change nothing
    else -- not one action, skip or overwrite, under either selection.

    This is the assertion that makes the row safe to land ahead of T070/T072
    rather than a silent change of what gets transferred.
    """
    reg = _reg_t068()
    assert reg["full_copy"]["composition_unchanged_by_registration"] is True
    assert reg["narrow"]["composition_unchanged_by_registration"] is True
    assert reg["plan_composition_unchanged_by_registration"] is True
    for scope in ("full_copy", "narrow"):
        assert (reg[scope]["registry_live"]["composition"]
                == reg[scope]["registry_empty"]["composition"]), scope


def test_the_census_is_unchanged_by_the_slots_registration() -> None:
    """The census T068 owed, expressed as the comparison that makes it mean
    something.

    A census artifact on its own says only "this transfer lost these objects".
    The question a registration raises is whether it lost DIFFERENT ones, so
    the post-registration artifact is compared row by row against T067's --
    same source, same backup, same full-copy selection, two separately
    restored targets. Identical class tables and identical totals is the
    answer: registering the SLOTS row moved no object count.

    The shared `DUPLICATE_IDENTITY` / exit 3 is NOT a US3 regression and is
    already recorded under T064: `PhNCFeatures` carries 23 duplicate
    natural-key groups over 66 extra objects, all FLEx-auto-generated
    "Created automatically for rule ..." classes that the source itself
    duplicates. Asserting the two runs agree on it keeps that reading intact
    rather than letting exit 3 be re-read later as a Phase 7 regression.
    """
    for path in (_CENSUS_POST, _CENSUS_T068):
        if not path.is_file():
            pytest.skip("missing census artifact " + str(path))
    pre = json.loads(_CENSUS_POST.read_text(encoding="utf-8"))
    post = json.loads(_CENSUS_T068.read_text(encoding="utf-8"))
    assert _census_table(post) == _census_table(pre)
    assert post["totals"] == pre["totals"]
    assert (post["verdict"], post["exit_code"]) \
        == (pre["verdict"], pre["exit_code"]) == ("DUPLICATE_IDENTITY", 3)


# ---------------------------------------------------------------------------
# T069's CENSUS -- and the first TWO-HOP closure this feature has measured
# ---------------------------------------------------------------------------
#
# Driver: `debug/run038_closure_census.py T069`. Artifacts:
# `_snapshots/closure-registration-038-t069.json` and
# `_snapshots/census-038-t069-registered.json`, the latter compared row for row
# against T068's.
#
# The narrow selection here is AFFIX_TEMPLATES-only, and it produces something
# neither earlier registration could: a closure walk TWO HOPS deep. The
# templates pull in their slots (`TEMPLATE_TO_SLOT`), and the walk then applies
# T068's registered row to each pulled-in slot, pulling in the slots' owning
# POSes (`SLOT_TO_POS`). The third kind in this plan is therefore not an
# accident to be tolerated -- it is the closure doing the job FR-014 asks for,
# and it only works because T068 landed first.

_REG_T069 = _SNAPSHOT_DIR / "closure-registration-038-t069.json"
_CENSUS_T069 = _SNAPSHOT_DIR / "census-038-t069-registered.json"


def _reg_t069() -> dict:
    if not _REG_T069.is_file():
        pytest.skip(
            "no committed registration measurement at " + str(_REG_T069)
            + " -- produce it with `python debug/run038_closure_census.py "
            "T069`")
    return json.loads(_REG_T069.read_text(encoding="utf-8"))


def test_a_templates_only_plan_carries_the_registered_edges() -> None:
    """THE TEST BOTH T069 ROWS NAME IN THEIR `verified_by`.

    Each kind is asserted separately and by far category, because a single
    total of 53 would be satisfied by the POS half working while the slot half
    stayed dead -- the exact asymmetry the first audit found on the MSA sites.

    Every edge must be `origin="pulled_in"` (a "chosen" edge here would mean
    the seed set leaked into the closure) and must carry a non-empty
    `verified_by` (a registry validated at build time and then losing its
    evidence on the way to the plan would defeat FR-018 silently).
    """
    reg = _reg_t069()
    assert reg["task"] == "T069"
    assert reg["narrow_selection"] == "AFFIX_TEMPLATES"
    live = reg["narrow"]["registry_live"]["closure"]
    assert live["by_kind"]["TEMPLATE_TO_POS"] == {
        "edges": 11,
        "far_categories": {"gram_categories": 11},
        "origins": {"pulled_in": 11},
        "verified_by_nonempty": True,
    }
    assert live["by_kind"]["TEMPLATE_TO_SLOT"] == {
        "edges": 24,
        "far_categories": {"slots": 24},
        "origins": {"pulled_in": 24},
        "verified_by_nonempty": True,
    }
    assert live["total_edges"] == 53


def test_the_templates_plan_walks_two_hops_through_t068s_row() -> None:
    """The finding this selection produced, pinned as a claim rather than
    tolerated as extra output.

    53 edges over 23 distinct pulled-in refs decomposes as: 11 template->POS,
    24 template->slot, and **18 slot->POS** -- the second hop. The walk applies
    T068's `SLOT_TO_POS` row to each slot it just pulled in, so the 18 slots
    bring their owning POSes with them. That is FR-014's promise ("include the
    items it depends on") holding transitively, and it is only reachable
    because T068 landed first: with `SLOT_TO_POS` unregistered,
    `closure_dependencies_for` returns `()` for SLOTS and the walk stops one
    hop short.

    The 5 distinct POSes against 29 POS-bound edges (11 + 18) is the same
    many-to-one shape T067 and T068 measured, now arriving from two different
    source categories at once.
    """
    reg = _reg_t069()
    live = reg["narrow"]["registry_live"]["closure"]
    assert set(live["by_kind"]) == {"TEMPLATE_TO_POS", "TEMPLATE_TO_SLOT",
                                   "SLOT_TO_POS"}
    assert live["by_kind"]["SLOT_TO_POS"] == {
        "edges": 18,
        "far_categories": {"gram_categories": 18},
        "origins": {"pulled_in": 18},
        "verified_by_nonempty": True,
    }
    assert live["distinct_pulled_in_refs"] == 23
    assert live["pulled_in_by_category"] == {"gram_categories": 5, "slots": 18}
    assert reg["expected_kinds"] == ["TEMPLATE_TO_POS", "TEMPLATE_TO_SLOT",
                                     "SLOT_TO_POS"]


def test_the_template_edges_come_from_the_registry_and_nowhere_else() -> None:
    """Emptying the registry must take all 53 edges with it, including the
    transitive hop.

    Without this, the two tests above are satisfied by any code path that
    produces closure edges -- including one that ignores
    `CLOSURE_EDGES_VERIFIED` entirely, the fall-through FR-018 forbids.
    """
    reg = _reg_t069()
    assert reg["narrow"]["registry_empty"]["closure"]["total_edges"] == 0


def test_a_full_copy_still_carries_no_closure_edges_after_t069() -> None:
    """Seed semantics, re-measured with five rows registered instead of three.

    Pinned per registration rather than once, because the claim is about the
    SEED SET and each new row adds a source category whose far endpoints might
    not have been seeds. Two-hop closure makes this worth re-checking rather
    than assuming: in a full copy the slots are seeds too, so the second hop
    has nothing to pull in either.
    """
    reg = _reg_t069()
    assert reg["full_copy"]["registry_live"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["registry_empty"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["closure_edges_expected"] == 0


def test_t069_changed_no_plan_decision_under_either_selection() -> None:
    """T070 and T072 have not landed, so at this stage a registration must add
    EDGES and change nothing else -- not one action, skip or overwrite, under
    either selection. Including the transitive hop: pulling 18 slots and 5
    POSes into the closure must not put them into the PLAN, because
    `Selection` still says AFFIX_TEMPLATES only.

    That last clause is what makes two-hop closure safe to land ahead of T070:
    the edges record a dependency, they do not (yet) transfer anything.
    """
    reg = _reg_t069()
    assert reg["full_copy"]["composition_unchanged_by_registration"] is True
    assert reg["narrow"]["composition_unchanged_by_registration"] is True
    assert reg["plan_composition_unchanged_by_registration"] is True
    for scope in ("full_copy", "narrow"):
        assert (reg[scope]["registry_live"]["composition"]
                == reg[scope]["registry_empty"]["composition"]), scope
    narrow_actions = reg["narrow"]["registry_live"]["composition"]["actions"]
    assert set(narrow_actions) == {"affix_templates"}, narrow_actions


def test_the_census_is_unchanged_by_the_template_registration() -> None:
    """The census T069 owed, compared against T068's -- same source, same
    backup, same full-copy selection, separately restored targets, registry
    holding three rows instead of five.

    Identical class tables and identical totals is the answer: registering
    both template rows moved no object count. The shared `DUPLICATE_IDENTITY`
    / exit 3 is `PhNCFeatures`' 23 duplicate natural-key groups over 66 extra
    objects, recorded under T064 and unrelated to US3; asserting the two runs
    agree on it keeps that reading intact rather than letting exit 3 be
    re-read later as a Phase 7 regression.
    """
    for path in (_CENSUS_T068, _CENSUS_T069):
        if not path.is_file():
            pytest.skip("missing census artifact " + str(path))
    pre = json.loads(_CENSUS_T068.read_text(encoding="utf-8"))
    post = json.loads(_CENSUS_T069.read_text(encoding="utf-8"))
    assert _census_table(post) == _census_table(pre)
    assert post["totals"] == pre["totals"]
    assert (post["verdict"], post["exit_code"]) \
        == (pre["verdict"], pre["exit_code"]) == ("DUPLICATE_IDENTITY", 3)


def test_every_registration_census_agrees_with_the_pre_phase7_baseline() -> None:
    """The chain, closed end to end rather than link by link.

    Each registration is compared with the one before it, which is the right
    diff for finding what a single row did -- but a chain of pairwise
    comparisons can drift if one link is ever re-measured and the others are
    not. So the LAST artifact is also compared with `census-038-mbugwe-
    phase6.json`: T063/T064's run with the registry EMPTY, before any of
    Phase 7 existed. Five registered relationships, no object count moved.
    """
    for path in (_CENSUS_PRE, _CENSUS_T069):
        if not path.is_file():
            pytest.skip("missing census artifact " + str(path))
    base = json.loads(_CENSUS_PRE.read_text(encoding="utf-8"))
    post = json.loads(_CENSUS_T069.read_text(encoding="utf-8"))
    assert _census_table(post) == _census_table(base)
    assert post["totals"] == base["totals"]
    assert (post["verdict"], post["exit_code"]) \
        == (base["verdict"], base["exit_code"])


# ---------------------------------------------------------------------------
# T070 / T071 / T072 -- the pull-in, and the first measurement of what a
# narrow transfer was LOSING
# ---------------------------------------------------------------------------
#
# Driver: `debug/run038_pull_in_census.py`. Artifact:
# `_snapshots/closure-pull-in-038-t070.json`.
#
# Everything above this line measures EDGES. T069's driver says so in as many
# words -- `plan_composition_unchanged_by_registration` was true "at this
# stage" only "because T070 (marking pulled-in items) and T072 (deselecting
# them) have not landed". These tests measure the moment that stops holding:
# the same AFFIX_TEMPLATES-only selection, the same source, the same backup,
# and now the plan gains MEMBERS for the 23 refs the edges named.
#
# The row that makes the case is not any of the plan-shape numbers. It is
# `D_arrival_in_target`: transferring templates alone used to land 8 of 11
# templates and ZERO of their 19 slots, because the 3 templates whose owning
# POS was not already in the destination could not resolve an owner and were
# abandoned. Nothing reported a closure failure -- the plan had never claimed
# to transfer a POS.

_PULL_IN = _SNAPSHOT_DIR / "closure-pull-in-038-t070.json"


def _pull_in() -> dict:
    if not _PULL_IN.is_file():
        pytest.skip(
            "no committed pull-in measurement at " + str(_PULL_IN)
            + " -- produce it with `python debug/run038_pull_in_census.py`")
    return json.loads(_PULL_IN.read_text(encoding="utf-8"))


def test_a_templates_only_plan_now_carries_the_pulled_in_members() -> None:
    """FR-014/FR-015 at plan level. 23 members, matching T069's 23 distinct
    pulled-in refs exactly -- 5 POSes and 18 slots.

    The member count and the EDGE count are asserted separately on purpose:
    53 edges over 23 refs means a ref can be named by more than one edge, and
    a pull-in that planned one member per EDGE would duplicate objects.
    """
    reg = _pull_in()
    assert reg["narrow_selection"] == "AFFIX_TEMPLATES"
    live = reg["A_narrow_registry_live"]
    assert {cat: row["count"]
            for cat, row in live["pulled_in_members"].items()} == {
        "gram_categories": 5, "slots": 18}
    assert live["closure"]["total_edges"] == 53
    assert live["closure"]["distinct_pulled_in_refs"] == 23


def test_the_pulled_in_members_split_into_adds_and_matches() -> None:
    """The pull-in routes through the category's own `plan_action`, so it
    inherits the match decision rather than creating blindly: of the 5 POSes,
    3 are ADDs and 2 are OVERWRITEs onto destination objects that already
    existed. A pull-in that hand-rolled its own create would have made two
    duplicate POSes here -- the create-anyway defect 038 exists to remove.
    """
    live = _pull_in()["A_narrow_registry_live"]["composition"]
    assert live["actions"] == {
        "affix_templates": 11, "gram_categories": 3, "slots": 18}
    assert live["overwrites"] == {"gram_categories": 2}


def test_nothing_is_pulled_in_without_the_registry() -> None:
    """The FR-018 column. Without it "the plan gained 23 members" is satisfied
    by a pull-in that ignores `CLOSURE_EDGES_VERIFIED` -- and this is the layer
    that CREATES OBJECTS, so a fall-through here writes data."""
    reg = _pull_in()
    empty = reg["A_narrow_registry_empty"]
    assert empty["pulled_in_members"] == {}
    assert empty["composition"]["actions"] == {"affix_templates": 11}
    assert reg["A_pull_in_requires_the_registry"] is True


def test_every_pulled_in_member_is_planned_before_the_selection() -> None:
    """`transfer.execute` walks `plan.actions` in order, so a dependency
    planned after its dependent is created after it. All 23 pulled-in members
    sit at indices 0..20, the first template at 21."""
    ordering = _pull_in()["A_narrow_registry_live"]["ordering"]
    assert ordering["every_pulled_in_member_precedes_the_selection"] is True
    assert ordering["first_selected_member_index"] == 21


def test_the_run_report_counts_what_the_plan_marked() -> None:
    """The mark has to TRAVEL: `report.build_from_plan` counts a member with a
    non-empty `pulled_in_by` into `CategoryReport.closure_pulled_in`, which is
    the column `Lib/ui/stats_panel.py` renders. A plan-level number the report
    does not show would mean the marking stopped at the plan."""
    assert _pull_in()["D_run_report_closure_pulled_in"] == {
        "gram_categories": 5, "slots": 18}


def test_deselecting_every_pulled_in_guid_restores_the_narrow_plan() -> None:
    """FR-016 (T071/T072) live. With all 23 GUIDs in
    `Selection.excluded_deps` -- what the wizard's deps and skeleton pages now
    put there -- the plan returns to exactly the registry-emptied composition.
    Same registry, same source, same selection; the ONLY difference is the
    user's refusal."""
    reg = _pull_in()
    b = reg["B_narrow_all_deselected"]
    assert b["composition"]["actions"] == {"affix_templates": 11}
    assert b["pulled_in_members"] == {}
    assert reg["B_deselection_restores_the_unregistered_composition"] is True


def test_a_deselection_is_reported_and_not_merely_absent() -> None:
    """23 `DEPENDENCY_DESELECTED` skips, each naming the item that needed the
    thing the user refused. The reason existed since the Phase 2 foundational
    work with no emitter; a deselection that leaves no trace is
    indistinguishable from a closure that never found the dependency."""
    b = _pull_in()["B_narrow_all_deselected"]
    assert b["deselection_skips"]["count"] == 23
    assert b["deselection_skips"]["by_category"] == {
        "gram_categories": 5, "slots": 18}
    assert b["deselection_skips"]["every_skip_names_its_puller"] is True


def test_the_deselection_is_recorded_on_the_edges_too() -> None:
    """`ClosureEdge.deselected` landed with T066 and was never written. T073
    builds its `IncompletenessRecord`s from it, so all 53 edges -- not just
    the 23 refs -- have to carry the fact."""
    by_kind = _pull_in()["B_narrow_all_deselected"]["closure"]["by_kind"]
    assert {k: (v["edges"], v["deselected"]) for k, v in by_kind.items()} == {
        "TEMPLATE_TO_POS": (11, 11),
        "TEMPLATE_TO_SLOT": (24, 24),
        "SLOT_TO_POS": (18, 18),
    }


def test_a_full_copy_is_untouched_by_the_pull_in() -> None:
    """The regression guard, and the reason the whole mechanism is safe to
    land: in a full copy every far endpoint is already a seed, `walk` records
    no seed as pulled in, so there are 0 edges and nothing to pull. The
    feature that completes a narrow selection must change a full copy by
    nothing at all."""
    reg = _pull_in()
    assert reg["C_full_copy_registry_live"]["closure"]["total_edges"] == 0
    assert reg["C_full_copy_registry_live"]["pulled_in_members"] == {}
    assert reg["C_full_copy_unchanged_by_the_pull_in"] is True


def test_the_narrow_transfer_used_to_lose_three_templates_and_all_its_slots():
    """THE MEASUREMENT THIS TASK EXISTS FOR, and the only one stated the way a
    linguist would ask it: after transferring templates alone, is what they
    need actually in the target?

    Two real transfers into the same restored throwaway target, differing only
    in whether the registry is live:

        class                 baseline   with T070   without
        PartOfSpeech                 5           8         5
        MoInflAffixSlot              0          19         0
        MoInflAffixTemplate          0          11         8

    Without the pull-in, 3 of 11 templates never arrive: their owning POS is
    absent from the destination, `_resolve_target_pos` returns None and the
    item is abandoned -- and the run reports no closure failure, because the
    plan never claimed to transfer a POS. The 19 slots are a cleaner loss
    still: not one of them arrives.

    The 19th slot is worth naming rather than rounding off: 18 slots are
    pulled in by the closure and the 19th arrives through the ENRICHMENT pass
    (FR-020..FR-022) on a pulled-in POS, whose `AffixSlotsOC` is add-only
    merged. The arrival column is therefore the union of two mechanisms, not
    a restatement of the pull-in count -- which is exactly why the isolating
    claims are A and B above, and this one is the outcome.
    """
    arrival = _pull_in()["D_arrival_in_target"]
    assert arrival["MoInflAffixTemplate"] == {
        "before": 0, "after": 11, "arrived": 11,
        "after_without_pull_in": 8, "arrived_without_pull_in": 8}
    assert arrival["MoInflAffixSlot"] == {
        "before": 0, "after": 19, "arrived": 19,
        "after_without_pull_in": 0, "arrived_without_pull_in": 0}
    assert arrival["PartOfSpeech"] == {
        "before": 5, "after": 8, "arrived": 3,
        "after_without_pull_in": 5, "arrived_without_pull_in": 0}


# ===========================================================================
# T073 -- FR-017 / SC-010: the items that ARRIVE INCOMPLETE, measured live
# ===========================================================================
#
# Asserted against `_snapshots/incompleteness-038-t073.json`, produced by
# `debug/run038_incompleteness_census.py` against the same pair and the same
# AFFIX_TEMPLATES-only selection as the T070 block above, so the two artifacts
# are directly comparable. That driver WRITES NOTHING: FR-017 is a plan-time
# determination, so every measurement is `preview_only=True` -- the restore is
# only so "is this dependency already in the destination" is a known quantity.
#
# THE BEFORE. `closure-pull-in-038-t070.json`, committed at the parent commit,
# carries no `incompleteness` key anywhere: 53 edges marked deselected, 23
# DEPENDENCY_DESELECTED skips naming the refused DEPENDENCIES, and not one word
# about the 11 templates that still transfer and now arrive unwired.

# T093 (2026-08-24) RE-MEASURED THIS BLOCK. The repair changed what is
# reported -- 35 records to 27, and P2's 29 to 7 -- so the artifact it changed
# is NOT overwritten: `incompleteness-038-t073.json` stays as the BEFORE and
# `incompleteness-038-t093.json` carries the behaviour the engine has now.
# Re-measuring a committed link in place is the drift T102 filed; the driver
# refuses to do it. Every test below that states what the code DOES reads the
# T093 artifact; the ones that state what it USED TO do say so in their names
# and read the T073 one.

_INCOMPLETE = _SNAPSHOT_DIR / "incompleteness-038-t073.json"
_INCOMPLETE_AFTER = _SNAPSHOT_DIR / "incompleteness-038-t093.json"


def _load_incompleteness(path) -> dict:
    if not path.is_file():
        pytest.skip(
            "no committed incompleteness measurement at " + str(path)
            + " -- produce it with "
            "`python debug/run038_incompleteness_census.py T093`")
    return json.loads(path.read_text(encoding="utf-8"))


def _incompleteness_before() -> dict:
    """T073's measurement, kept because T093 changed the numbers in it."""
    return _load_incompleteness(_INCOMPLETE)


def _incompleteness() -> dict:
    """What the engine reports NOW (T073 as repaired by T093)."""
    return _load_incompleteness(_INCOMPLETE_AFTER)


def test_a_satisfied_closure_reports_no_incompleteness() -> None:
    """THE QUIET CASE FIRST, because it is what makes the loud one mean
    anything. Same registry, same narrow selection, nothing deselected: all 53
    edges resolve, all 23 dependencies are pulled in, and the report says
    nothing. A warning that is always on is indistinguishable from no
    warning."""
    p0 = _incompleteness()["measured"]["P0_nothing_deselected"]
    assert p0["closure"]["total_edges"] == 53
    assert p0["incompleteness"]["records"] == 0


def test_a_full_deselection_reports_every_item_it_leaves_incomplete() -> None:
    """FR-017 live. With all 23 pulled-in GUIDs refused, 11 templates still
    transfer and each loses its slots and -- for the 3 whose POS is not
    already in the destination -- its POS: 27 records over 11 distinct
    arriving items, naming 21 distinct missing dependencies.

        TEMPLATE_TO_POS    11 edges  ->   3 records   (8 already in target)
        TEMPLATE_TO_SLOT   24 edges  ->  24 records
        SLOT_TO_POS        18 edges  ->   0 records

    21 = the 23 pulled-in refs minus the 2 the destination already has, which
    is the arithmetic T093's repair turns on.
    """
    p1 = _incompleteness()["measured"]["P1_everything_deselected"]
    assert p1["closure"]["edges_marked_deselected"] == 53
    assert p1["incompleteness"]["records"] == 27
    assert p1["incompleteness"]["by_category_pair"] == {
        "affix_templates": {"gram_categories": 3, "slots": 24}}
    assert p1["incompleteness"]["distinct_incomplete_items"] == 11
    assert p1["incompleteness"]["distinct_missing_dependencies"] == 21
    assert p1["incompleteness"]["by_cause"] == {"deselected": 27}


def test_an_item_that_does_not_arrive_is_not_reported_as_incomplete() -> None:
    """WHY NOT 53, stated as its own claim because it is a deliberate
    accounting decision and not a shortfall. The 18 `SLOT_TO_POS` edges name
    slots that were themselves deselected: they do not arrive at all, so they
    are dropped-with-reason (their own `DEPENDENCY_DESELECTED` skip, 18 of the
    23) and not "arriving incomplete". Reporting both would count one loss
    twice under two SC-010 buckets and would assert, of an object that never
    reaches the destination, that it arrives broken."""
    p1 = _incompleteness()["measured"]["P1_everything_deselected"]
    assert p1["skips"] == {"gram_categories": 5, "slots": 18}
    assert p1["closure"]["by_kind"]["SLOT_TO_POS"]["edges"] == 18
    assert "slots" not in p1["incompleteness"]["by_category_pair"]


def test_a_pulled_in_item_can_itself_arrive_incomplete() -> None:
    """THE TWO-HOP CASE T069's census warned Phase 7 to expect, and the one a
    full deselection cannot show. Deselect only the 5 POSes: the 18 slots are
    still pulled in, so they arrive -- and the ones whose part of speech is
    not already in the destination arrive missing it. 7 records over 7
    distinct items (3 templates + 4 slots) and 3 distinct missing
    dependencies, which is the 5 refused POSes minus the 2 the destination
    already has.

    T093 moved this case hardest: 29 records to 7. The 2 already-present
    POSes carried 22 of the 29, so three quarters of THIS reading was phantom
    -- which is what "8 of 35" understated when the defect was filed."""
    p2 = _incompleteness()["measured"][
        "P2_only_the_parts_of_speech_deselected"]
    assert p2["incompleteness"]["records"] == 7
    assert p2["incompleteness"]["by_category_pair"] == {
        "affix_templates": {"gram_categories": 3},
        "slots": {"gram_categories": 4}}
    assert p2["incompleteness"]["distinct_incomplete_items"] == 7
    assert p2["incompleteness"]["distinct_missing_dependencies"] == 3


def test_a_full_copy_reports_no_incompleteness() -> None:
    """The regression guard, in the same shape T070's carries: a full copy has
    every far endpoint as a seed, so 0 edges, so 0 records. A mechanism that
    completes a narrow selection must change the case every existing caller
    uses by nothing at all."""
    p3 = _incompleteness()["measured"]["P3_full_copy"]
    assert p3["closure"]["total_edges"] == 0
    assert p3["incompleteness"]["records"] == 0


def test_the_record_reaches_every_surface_a_user_reads() -> None:
    """SC-010 is stated in terms of the REPORT, not the plan.
    `RunReport.incompleteness`, `has_incomplete_items`, the snapshot JSON's
    `incompleteness` list and the console's "Items arriving INCOMPLETE" block
    all predate this task and all rendered an empty tuple."""
    s = _incompleteness()["measured"]["P4_surfaces_for_P1"]
    assert s["run_report_records"] == 27
    assert s["snapshot_json_records"] == 27
    assert s["has_incomplete_items"] is True
    assert s["console_block_present"] is True
    assert s["console_states_a_cause"] is True


def test_every_record_names_its_items_or_says_it_cannot() -> None:
    """A record whose labels are blank tells the reader which GUIDs are
    involved and nothing about which ITEMS. 47 of 54 labels in P1 are real
    source names ("basic noun" needs "Noun", "aug", "np"); the 7 fallbacks are
    3 AFFIX TEMPLATES whose source `Name` is genuinely empty -- a fact about
    the corpus, not a failure of the label reader, which is why the fallback
    is the console form of the ref rather than an empty string.

    54 rather than T073's 70 because T093 removed 8 records; the 7 unnamed
    labels are the same 7, so the fallbacks did not move."""
    p1 = _incompleteness()["measured"][
        "P1_everything_deselected"]["incompleteness"]
    assert p1["labels_total"] == 54
    assert p1["labels_falling_back_to_the_ref"] == 7
    assert len(p1["distinct_refs_with_no_resolvable_name"]) == 3
    assert all(ref.startswith("affix_templates:")
               for ref in p1["distinct_refs_with_no_resolvable_name"])
    assert p1["every_record_has_a_consequence"] is True


# ===========================================================================
# T093 -- the over-report T073 pinned, and what closing it moved
# ===========================================================================
#
# Artifact: `_snapshots/incompleteness-038-t093.json`
# (`python debug/run038_incompleteness_census.py T093`, same source, same
# backup, same AFFIX_TEMPLATES-only selection as T073, `preview_only=True`).
#
# THE DEFECT. A deselected dependency that is ALREADY IN THE DESTINATION was
# reported as missing. T071 refuses a deselected ref BEFORE its planner runs
# -- correct for the plan, and what `test_a_deselected_dependency_is_not_
# planned` pins -- so no `ALREADY_PRESENT_BY_*` skip exists on that path and
# `_plan_incompleteness` had nothing to consult.
#
# THE REPAIR asks the refused dependency's OWN `plan_action` whether the
# destination already has it and keeps nothing but that verdict: no plan
# member, no skip, so T071's composition is untouched. Not a GUID probe --
# `guid in target` without a field-identity comparison is Defect G3's exact
# shape, the premise this feature exists to remove. And the presence test sits
# ABOVE the cause ladder rather than inside the `deselected` branch, because
# cause precedence orders explanations for an incompleteness and cannot decide
# whether there is one.


def test_no_record_names_a_dependency_that_is_already_in_the_destination(
) -> None:
    """THE CLAIM, replacing T073's pin of the same number at 8. The 2 POSes
    the destination already has are named by 0 records; T073 named them 8
    times."""
    now = _incompleteness()["measured"][
        "T093_dependencies_already_in_the_destination"]
    assert len(now["refs_already_there"]) == 2
    assert all(ref.startswith("gram_categories:")
               for ref in now["refs_already_there"])
    assert now["P1_records_naming_one_of_them"] == 0


def test_the_repair_removed_exactly_the_phantom_records_and_no_others(
) -> None:
    """THE ACCOUNTING, and the reason a delta is asserted rather than just an
    after-value: 35 - 27 == 8 == the number of records that named an
    already-present dependency. Every record that disappeared is one of the
    over-reports; none of the real ones went with them."""
    ba = _incompleteness()["measured"]["T093_before_and_after"]
    assert ba["before_task"] == "T073"
    before, after = ba["P1_records"]["before"], ba["P1_records"]["after"]
    assert (before, after) == (35, 27)
    assert ba["P1_records_naming_a_dependency_already_there"] == {
        "before": 8, "after": 0}
    assert before - after == 8


def test_the_same_two_dependencies_are_present_before_and_after() -> None:
    """THE CONTROL. Same source, same backup, same selection: if the set of
    already-in-the-destination refs had moved, the delta above would be
    measuring a different target rather than a repair."""
    ba = _incompleteness()["measured"]["T093_before_and_after"]
    assert ba["refs_already_there"]["before"] == ba[
        "refs_already_there"]["after"]
    assert len(ba["refs_already_there"]["after"]) == 2


def test_the_refusal_is_still_a_refusal() -> None:
    """WHY THIS IS NOT REPAIR (a) FROM THE TASK LINE, measured. Running the
    refused ref's planner to learn the presence fact must not change what the
    user is told about the REFUSAL: the deselection skips are the same 5
    gram_categories and 18 slots T071 measured, not an `ALREADY_PRESENT_*`
    skip standing where a `DEPENDENCY_DESELECTED` one stood."""
    ba = _incompleteness()["measured"]["T093_before_and_after"]
    assert ba["deselection_skips_P1"]["before"] == ba[
        "deselection_skips_P1"]["after"] == {
            "gram_categories": 5, "slots": 18}


def test_the_two_hop_case_moved_furthest() -> None:
    """P2 -- only the POSes deselected -- went from 29 records to 7, because
    the 2 already-present POSes were between them the dependency of 22 of the
    29 arriving items. The headline "8 of 35" understated the defect; on the
    selection a user is most likely to make, three quarters of the report was
    phantom."""
    ba = _incompleteness()["measured"]["T093_before_and_after"]
    assert ba["P2_records"] == {"before": 29, "after": 7}


def test_the_before_artifact_still_records_the_defect() -> None:
    """THE BEFORE IS NOT OVERWRITTEN. T102 filed what happens when a committed
    artifact is re-measured in place -- the evidence for the old behaviour
    stops existing and every comparison against it turns red for a reason
    unrelated to what it asserts. `incompleteness-038-t073.json` therefore
    still holds 35 records and 8 over-reports, and the driver refuses to
    rewrite it without an explicit override."""
    before = _incompleteness_before()
    assert before["task"] == "T073"
    assert before["measured"]["P1_everything_deselected"][
        "incompleteness"]["records"] == 35
    assert before["measured"][
        "T093_dependencies_already_in_the_destination"][
            "P1_records_naming_one_of_them"] == 8


def test_the_pre_t073_artifact_reported_none_of_this() -> None:
    """THE BEFORE, from the committed record rather than from memory. T070's
    own snapshot -- same source, same target, same selection, same full
    deselection -- carries 53 edges marked deselected and no `incompleteness`
    key at any depth."""
    blob = json.dumps(_pull_in())
    assert "incompleteness" not in blob
    b = _pull_in()["B_narrow_all_deselected"]
    assert b["deselection_skips"]["count"] == 23
    assert sum(r["deselected"] for r in b["closure"]["by_kind"].values()) == 53


# ===========================================================================
# T076 (2026-08-22) -- the process-rule referent rows, and the claim that
# expired between T069 and this registration
# ===========================================================================
#
# Artifact: `_snapshots/closure-registration-038-t076.json`
# (`python debug/run038_closure_census.py T076`, AFFIXES-only against a target
# restored from `Target 2026-07-06 0218.fwbackup`).
#
# TWO THINGS ARE DIFFERENT HERE and both are deliberate.
#
# 1. `comparable_prior_artifact` is None. The `-t067-`/`-t068-`/`-t069-`
#    census artifacts form a chain of pairwise equality comparisons that T102
#    measured as ALREADY behind the instrument (3 changed rows, 2 changed
#    totals, from T087 and T099). A fourth link would fail for that
#    pre-existing drift and say nothing about T076, so this registration's
#    census stands alone and the chain stays T102's to repair.
#
# 2. The narrow selection's composition CHANGES, and that is the registration
#    working rather than a regression. `test_t069_changed_no_plan_decision_
#    under_either_selection` above is still true OF ITS OWN ARTIFACT, which
#    was measured before T070 and T072 landed; planning the pulled-in items IS
#    T070. What replaces "nothing changed" is a one-for-one accounting.

_REG_T076 = _SNAPSHOT_DIR / "closure-registration-038-t076.json"


def _reg_t076() -> dict:
    if not _REG_T076.is_file():
        pytest.skip(
            "no committed registration measurement at " + str(_REG_T076)
            + " -- produce it with `python debug/run038_closure_census.py "
            "T076`")
    return json.loads(_REG_T076.read_text(encoding="utf-8"))


def test_an_affixes_only_plan_carries_the_registered_process_rule_edges():
    """THE TEST BOTH T076 ROWS NAME IN THEIR `verified_by`.

    Each kind separately and by far category: one total would be satisfied by
    the phoneme half working while the natural-class half stayed dead, which
    is the asymmetry every audit in this file exists to catch.
    """
    reg = _reg_t076()
    assert reg["task"] == "T076"
    assert reg["narrow_selection"] == "AFFIXES"
    live = reg["narrow"]["registry_live"]["closure"]
    assert live["by_kind"]["PROCESS_RULE_TO_PHONEME"] == {
        "edges": 32,
        "far_categories": {"phonemes": 32},
        "origins": {"pulled_in": 32},
        "verified_by_nonempty": True,
    }
    assert live["by_kind"]["PROCESS_RULE_TO_NATURAL_CLASS"] == {
        "edges": 10,
        "far_categories": {"natural_classes": 10},
        "origins": {"pulled_in": 10},
        "verified_by_nonempty": True,
    }
    assert set(live["by_kind"]) == {
        "AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE",
        "PROCESS_RULE_TO_PHONEME", "PROCESS_RULE_TO_NATURAL_CLASS",
    }
    assert live["total_edges"] == 259
    assert live["pulled_in_by_category"] == {
        "feature_struct_types": 2, "gram_categories": 6,
        "natural_classes": 2, "phonemes": 16,
    }


def test_the_process_rule_edges_come_from_the_registry_and_nowhere_else():
    """Emptying the registry must take all 259 edges with it. Without this,
    the test above is satisfied by any code path that produces closure edges,
    including one that ignores `CLOSURE_EDGES_VERIFIED` -- the fall-through
    FR-018 forbids."""
    reg = _reg_t076()
    assert reg["narrow"]["registry_empty"]["closure"]["total_edges"] == 0


def test_a_full_copy_still_carries_no_closure_edges_after_t076():
    """Seed semantics, re-measured with seven rows registered instead of five.

    Pinned per registration rather than once, because each new row adds far
    endpoints that might not have been seeds. Phonemes and natural classes
    are, so a full copy still records nothing -- and its composition is
    therefore still required to be byte-identical with the registry emptied.
    """
    reg = _reg_t076()
    assert reg["full_copy"]["registry_live"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["registry_empty"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["composition_unchanged_by_registration"] is True
    assert (reg["full_copy"]["registry_live"]["composition"]
            == reg["full_copy"]["registry_empty"]["composition"])


def test_t076_added_exactly_one_decision_per_pulled_in_reference():
    """What replaced "the registration changed no decision", and it is a
    stronger claim than the one it replaced was by the time T076 ran.

    26 distinct pulled-in references and 26 added decisions, matching per
    category. Actions and overwrites BOTH count, because a pulled-in item the
    destination already holds arrives as an overwrite -- 5 phoneme adds beside
    11 phoneme overwrites is 16, the phoneme pull-in exactly.

    A registration that perturbed anything else -- a skip, a dropped item, a
    lost process rule, an action in a category nothing was pulled into --
    breaks this even though the composition is allowed to move.
    """
    reg = _reg_t076()
    live = reg["narrow"]["registry_live"]["composition"]
    empty = reg["narrow"]["registry_empty"]["composition"]
    pulled = reg["narrow"]["registry_live"]["closure"]["pulled_in_by_category"]

    added: dict = {}
    for bucket in ("actions", "overwrites"):
        for category in set(live[bucket]) | set(empty[bucket]):
            delta = live[bucket].get(category, 0) - empty[bucket].get(category, 0)
            if delta:
                added[category] = added.get(category, 0) + delta
    assert added == pulled
    assert sum(added.values()) == 26

    # AFFIXES itself is untouched: the selection decided those, not the walk.
    assert live["actions"]["affixes"] == empty["actions"]["affixes"] == 118
    # ...and nothing but `enrichments` moved among the un-categorised counters.
    for key in ("excluded_lossy", "dropped_items", "process_rules",
                "skips_total"):
        assert live[key] == empty[key], key
    assert live["enrichments"] - empty["enrichments"] == 2


# ---------------------------------------------------------------------------
# T089 -- the fix's OWN census. The axis is the PRODUCER, not the registry.
#
# Every block above this one measures a REGISTRATION: two plans differing only
# in whether `CLOSURE_EDGES_VERIFIED` holds a row. T089 registers nothing, so
# that instrument cannot answer its question. Its task text is explicit that
# the fix "is a live-behaviour change and must not be folded into a
# registration ... it changes `affixes_dependencies`' output for every caller,
# so it needs its own census", and `debug/run038_t089_census.py` is it: the
# registry is held FIXED at its 7 rows and `categories._value_defn_ref` is
# monkeypatched back to the pre-T089 identity.
#
# The expected answer is zero plan difference, and the reason is structural --
# of the producers the fix reaches, only `affixes_feat_struc_type_dependencies`
# is registered at all, and it is narrowed to FEATURE_STRUCT_TYPES, the far
# category the `TypeRA` arrow lands in and the fix does not touch. A structural
# argument is exactly what T088 and flexicon 4.5.0 both refuted on live data,
# which is why it was measured.
# ---------------------------------------------------------------------------

_PRODUCER_T089 = _SNAPSHOT_DIR / "closure-producer-038-t089.json"


def _prod_t089():
    if not _PRODUCER_T089.is_file():
        pytest.skip(
            "no committed producer census at " + str(_PRODUCER_T089)
            + " -- produce it with `python debug/run038_t089_census.py`"
        )
    return json.loads(_PRODUCER_T089.read_text(encoding="utf-8"))


def test_t089_was_measured_with_the_row_still_unregistered() -> None:
    """The precondition that makes the rest of this block mean anything.

    With `MSA_TO_INFL_FEATURE` registered, the run would be varying the
    producer AND the registry at once and could attribute the outcome to
    neither. The driver refuses to run in that state; this asserts the
    committed artifact came from a run that did not have to.
    """
    prod = _prod_t089()
    assert prod["task"] == "T089"
    assert prod["msa_to_infl_feature_registered"] is False
    assert "MSA_TO_INFL_FEATURE" not in prod["registered"]
    # T104 (2026-08-22). This read `== set(_REGISTERED)` until the day
    # `MSA_TO_INFL_FEATURE` joined that table, and the assertion was RIGHT to
    # fail then -- it is the whole point of this test that T089's run happened
    # with this one row out of the registry and every other row in it.
    #
    # The bug was that the claim was written against a MUTABLE table. What it
    # means is "the registry as it stood on the day, which is today's registry
    # minus the row T104 added", and stating that difference explicitly is
    # what keeps the test honest through the next registration too: an eighth
    # row appearing in `_REGISTERED` for some other relationship would make
    # this fail again, correctly, because T089's artifact would then no longer
    # describe the registry it was measured against.
    assert set(prod["registered"]) == set(_REGISTERED) - {
        "MSA_TO_INFL_FEATURE"}
    assert len(prod["registered"]) == len(_REGISTERED) - 1
    assert prod["axis"].startswith("categories._value_defn_ref")


def test_t089_changed_no_plan_under_either_selection() -> None:
    """The claim itself, on both selections the fix could reach.

    A FULL COPY is unconditional: every far endpoint is its own seed there, so
    the closure is empty and any difference at all would mean the fix had
    leaked into the seed set. AFFIXES-only is the selection that can observe
    the registered AFFIXES rows -- 259 closure edges either way, which is the
    number that would move if `_feat_struc_deps`' INFLECTION_FEATURES half
    were reaching a plan by some path the registry does not describe.
    """
    prod = _prod_t089()
    assert prod["plan_unchanged_by_fix"] is True
    for label, expected_edges in (("full copy", 0), ("AFFIXES only", 259)):
        pair = prod["selections"][label]
        assert pair["composition_unchanged_by_fix"] is True, label
        assert pair["closure_unchanged_by_fix"] is True, label
        assert pair["fixed"]["closure"]["total_edges"] == expected_edges, label
        assert pair["pre_t089"]["closure"]["total_edges"] == expected_edges, label
        assert pair["fixed"]["composition"] == pair["pre_t089"]["composition"]


def test_t089_reproduces_the_previous_census_row_for_row() -> None:
    """The other half, and the one a plan comparison cannot give.

    A plan is what the engine INTENDS; a census is what the target actually
    holds afterwards. The fix changes no registered edge, so the transfer it
    produces must be the same transfer -- and `census-038-t076-registered.json`
    is the right comparand precisely because it is the most recent full-copy
    census over the same source, backup and selection, with T089 as the only
    code difference between the two runs.
    """
    prod = _prod_t089()
    assert prod["census"]["comparable_prior_artifact"] == (
        "census-038-t076-registered.json")
    assert prod["census"]["rows_match_prior"] is True, (
        "the census did not reproduce the prior artifact row for row, so "
        "either the fix reached the writer or something else drifted"
    )
    # Same gate reading as the run it reproduces. Asserted as EQUALITY to that
    # artifact rather than to a literal: the value is the pre-existing state of
    # the corpus pair (DUPLICATE_IDENTITY, exit 3), not something T089 is
    # entitled to change, and pinning it to a literal here would quietly make
    # this test a second, weaker copy of the census gate.
    prior = json.loads(
        (_SNAPSHOT_DIR / "census-038-t076-registered.json").read_text(
            encoding="utf-8"))
    current = json.loads(
        (_SNAPSHOT_DIR / "census-038-t089-fixed.json").read_text(
            encoding="utf-8"))
    assert current["verdict"] == prior["verdict"]
    assert current["exit_code"] == prior["exit_code"]
    assert prod["census"]["gate_exit_code"] == prior["exit_code"]


def test_t089_recorded_the_producer_change_it_did_not_measure_here() -> None:
    """Coverage honesty, made mechanical.

    This driver deliberately does NOT re-measure the producer -- that is
    `debug/audit038_closure_edges.py`'s job over two corpora. What it carries
    is the BEFORE numbers, so a reader of one artifact can see that the
    producer really did change on the very run where the plan did not, and so
    that "no plan changed" can never be read as "nothing changed".
    """
    prod = _prod_t089()
    before = prod["producer_change_recorded_by_the_audit"]
    for corpus, edges, distinct, owned in (
            ("Mbugwe LizzieHC practice", 206, 34, 30),
            ("Ejagham Mini", 34, 10, 8)):
        row = before[corpus]["before"]
        assert row["edges"] == edges
        assert row["distinct_far_guids"] == distinct
        assert row["resolved_as_owned_value"] == owned
        assert row["verdict"] == "REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE"

    # ...and the AFTER numbers really are smaller, read from the audit
    # snapshots rather than from the census artifact's own prose.
    after = {s["source_project"]: s["relationships"]["MSA_TO_INFL_FEATURE"]
             for s in _snapshots()}
    for corpus in ("Mbugwe LizzieHC practice", "Ejagham Mini"):
        row = after[corpus]
        assert row["edges"] < before[corpus]["before"]["edges"]
        assert row["distinct_far_guids"] < before[corpus]["before"][
            "distinct_far_guids"]
        assert row["resolved_as_owned_value"] == 0


# ===========================================================================
# T104 (2026-08-22) -- the registration T089 unblocked and deliberately did
# not perform
# ===========================================================================
#
# Artifact: `_snapshots/closure-registration-038-t104.json`
# (`python debug/run038_closure_census.py T104`, AFFIXES-only against a target
# restored from `Target 2026-07-06 0218.fwbackup`).
#
# THIS IS THE ONLY ROW IN THE REGISTRY WHOSE CONFIRMING AUDIT WAS COMMITTED BY
# AN EARLIER TASK, and the reason is the distinction the block above this one
# exists to draw. T089 fixed the far endpoint and re-ran the audit; the row
# measured CONFIRMED on both corpora that day and STILL was not registered,
# because the two questions need different instruments:
#
#   * T089's census varies the PRODUCER with the registry held fixed --
#     "did the fix change a plan?" (measured: no, under both selections).
#   * A registration census varies the REGISTRY with the producer held fixed
#     -- "does registering this row change a decision it should not?"
#
# Running the first one twice would look like diligence and measure nothing
# new. So the audit assertions for this relationship live in
# `test_only_the_confirmed_relationships_are_registered` and
# `test_the_formerly_refused_relationship_now_names_only_enumerable_defns`
# above, and what is asserted HERE is only what the registration itself
# produced.

_REG_T104 = _SNAPSHOT_DIR / "closure-registration-038-t104.json"


def _reg_t104() -> dict:
    if not _REG_T104.is_file():
        pytest.skip(
            "no committed registration measurement at " + str(_REG_T104)
            + " -- produce it with `python debug/run038_closure_census.py "
            "T104`")
    return json.loads(_REG_T104.read_text(encoding="utf-8"))


def test_an_affixes_only_plan_carries_the_infl_feature_edges() -> None:
    """THE TEST T104'S ROW NAMES IN ITS `verified_by`.

    The new row on its own first, then the whole set, because a single total
    would be satisfied by the four AFFIXES rows that were already working
    while the fifth stayed dead -- the asymmetry every audit in this file
    exists to catch.

    99 edges over 4 distinct pulled-in references is the shape that makes this
    relationship worth registering AND the shape that got it refused for so
    long. Before T089 it was 206 edges over 34 far GUIDs, 30 of which named an
    `IFsSymFeatVal` no category could enumerate. The count of EDGES fell and
    the count of distinct DEPENDENCIES fell further, because many values of
    one feature are one feature.

    The 4 is the cross-check worth having: `debug/audit038_closure_edges.py`
    measured 4 distinct far GUIDs by resolving them against
    `inflection_features_enumerate_source`, and the plan's closure walk
    arrives at 4 pulled-in `inflection_features` references by a completely
    different route. Two instruments, one number.
    """
    reg = _reg_t104()
    assert reg["task"] == "T104"
    assert reg["narrow_selection"] == "AFFIXES"

    live = reg["narrow"]["registry_live"]["closure"]
    assert live["by_kind"]["MSA_TO_INFL_FEATURE"] == {
        "edges": 99,
        "far_categories": {"inflection_features": 99},
        "origins": {"pulled_in": 99},
        "verified_by_nonempty": True,
    }
    # All five AFFIXES rows, which is what `expect_kinds` declares and why it
    # cannot name only the new one: the same pieces carry every AFFIXES
    # relationship, so a narrower list would fail for four rows doing their
    # job -- while this exact-set form still fails on a sixth relationship
    # nobody audited.
    assert set(live["by_kind"]) == {
        "AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE", "MSA_TO_INFL_FEATURE",
        "PROCESS_RULE_TO_PHONEME", "PROCESS_RULE_TO_NATURAL_CLASS",
    }
    assert set(reg["expected_kinds"]) == set(live["by_kind"])
    assert live["total_edges"] == 358
    assert live["pulled_in_by_category"] == {
        "feature_struct_types": 2, "gram_categories": 6,
        "inflection_features": 4, "natural_classes": 2, "phonemes": 16,
    }
    assert live["distinct_pulled_in_refs"] == 30


def test_t104_added_its_own_row_and_nothing_else() -> None:
    """The registration's delta against T076's run, which is the previous
    measurement under the SAME selection.

    Asserted as a difference rather than as two independent totals because
    that is the actual claim: +99 edges and +4 pulled-in references, all of
    them `MSA_TO_INFL_FEATURE` and `inflection_features`, with every other
    kind and every other far category unmoved to the unit. A registration
    that perturbed a sibling row would pass a totals check and fail here.
    """
    prior = json.loads(_REG_T076.read_text(encoding="utf-8"))
    now = _reg_t104()
    before = prior["narrow"]["registry_live"]["closure"]
    after = now["narrow"]["registry_live"]["closure"]

    assert before["total_edges"] == 259
    assert after["total_edges"] - before["total_edges"] == 99
    assert after["distinct_pulled_in_refs"] \
        - before["distinct_pulled_in_refs"] == 4

    # Every kind T076 measured is byte-identical; the only new key is the
    # registered row.
    assert set(after["by_kind"]) - set(before["by_kind"]) == {
        "MSA_TO_INFL_FEATURE"}
    for kind, row in before["by_kind"].items():
        assert after["by_kind"][kind] == row, kind
    for category, count in before["pulled_in_by_category"].items():
        assert after["pulled_in_by_category"][category] == count, category
    assert set(after["pulled_in_by_category"]) \
        - set(before["pulled_in_by_category"]) == {"inflection_features"}


def test_the_infl_feature_edges_come_from_the_registry_and_nowhere_else():
    """Emptying the registry must take all 358 edges with it. Without this,
    the test above is satisfied by any code path that produces closure edges,
    including one that ignores `CLOSURE_EDGES_VERIFIED` -- the fall-through
    FR-018 forbids."""
    reg = _reg_t104()
    assert reg["narrow"]["registry_empty"]["closure"]["total_edges"] == 0


def test_a_full_copy_still_carries_no_closure_edges_after_t104() -> None:
    """Seed semantics, re-measured with eight rows registered instead of
    seven.

    Pinned per registration rather than once, because each new row adds far
    endpoints that might not have been seeds. Inflection features are -- a
    full copy selects them in their own right -- so a full copy still records
    nothing, and its composition is therefore still required to be identical
    with the registry emptied.
    """
    reg = _reg_t104()
    assert reg["full_copy"]["registry_live"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["registry_empty"]["closure"]["total_edges"] == 0
    assert reg["full_copy"]["composition_unchanged_by_registration"] is True
    assert (reg["full_copy"]["registry_live"]["composition"]
            == reg["full_copy"]["registry_empty"]["composition"])


def test_t104_added_exactly_one_decision_per_pulled_in_reference() -> None:
    """The one-for-one accounting T076 put in place of "the registration
    changed no decision", closing on T104's numbers.

    30 distinct pulled-in references and 30 added decisions, matching PER
    CATEGORY -- the per-category match is what makes this more than an
    arithmetic coincidence. Actions and overwrites both count, because a
    pulled-in item the destination already holds arrives as an overwrite.

    The four inflection features this registration adds are all ACTIONS with
    no overwrite leg, which is worth pinning: the destination held none of
    them, so the row is adding objects a narrow transfer used to leave out
    rather than re-writing objects it already had.
    """
    reg = _reg_t104()
    live = reg["narrow"]["registry_live"]["composition"]
    empty = reg["narrow"]["registry_empty"]["composition"]
    pulled = reg["narrow"]["registry_live"]["closure"][
        "pulled_in_by_category"]

    added: dict = {}
    for bucket in ("actions", "overwrites"):
        for category in set(live[bucket]) | set(empty[bucket]):
            delta = (live[bucket].get(category, 0)
                     - empty[bucket].get(category, 0))
            if delta:
                added[category] = added.get(category, 0) + delta
    assert added == pulled
    assert sum(added.values()) == 30

    assert live["actions"]["inflection_features"] == 4
    assert "inflection_features" not in live["overwrites"]

    # AFFIXES itself is untouched: the selection decided those, not the walk.
    assert live["actions"]["affixes"] == empty["actions"]["affixes"] == 118
    # ...and nothing but `enrichments` moved among the un-categorised
    # counters. A skip, a dropped item or a lost process rule may not move.
    for key in ("excluded_lossy", "dropped_items", "process_rules",
                "skips_total"):
        assert live[key] == empty[key], key
    assert live["enrichments"] - empty["enrichments"] == 2


def test_the_t104_census_reproduces_the_previous_one_row_for_row() -> None:
    """A stronger result than this registration was required to produce, and
    the reason it is asserted rather than merely noted.

    `compare_census_to` is None for T104 -- the `-t067-`/`-t068-`/`-t069-`
    chain of pairwise census equalities is already behind the instrument (3
    changed rows and 2 changed totals, from T087 and T099; T102's to repair),
    so the driver was not asked to compare anything. The comparison holds
    anyway, and holding anyway is the point: the census is taken under a FULL
    COPY, where this row contributes no closure edge at all, so a full-copy
    census that MOVED would mean the registration had reached a path the
    seed semantics say it cannot.

    74 classes, 0 differing rows, every total equal, same verdict. The gate
    exit is 3 (`DUPLICATE_IDENTITY`) for a cause that predates Phase 7 and is
    recorded under T064 -- `PhNCFeatures`' 23 duplicate natural-key groups
    over 66 extra objects, the `Created automatically for rule "***"` classes
    the SOURCE itself duplicates. Asserted as equality with the prior
    artifact rather than as a literal, so this cannot quietly become a second
    weaker copy of the census gate.
    """
    reg = _reg_t104()
    assert reg["census"]["comparable_prior_artifact"] is None

    prior = json.loads(
        (_SNAPSHOT_DIR / "census-038-t076-registered.json").read_text(
            encoding="utf-8"))
    current = json.loads(
        (_SNAPSHOT_DIR / "census-038-t104-registered.json").read_text(
            encoding="utf-8"))

    assert current["verdict"] == prior["verdict"] == "DUPLICATE_IDENTITY"
    assert current["exit_code"] == prior["exit_code"]
    assert reg["census"]["gate_exit_code"] == prior["exit_code"]
    assert current["totals"] == prior["totals"]

    rows_now = {row["class"]: row for row in current["classes"]}
    rows_prior = {row["class"]: row for row in prior["classes"]}
    assert set(rows_now) == set(rows_prior)
    differing = [name for name, row in rows_now.items()
                 if row != rows_prior[name]]
    assert differing == [], (
        "the full-copy census moved under a registration that contributes no "
        "closure edge to a full copy: " + repr(differing))

    # The exit-3 cause, named, so a later reader cannot re-read it as a
    # Phase 7 regression.
    nc_features = rows_now["PhNCFeatures"]["duplicates"]
    assert nc_features["groups"] == 23
    assert nc_features["extra_objects"] == 66
    assert current["totals"]["duplicate_extra_objects"] == 66


# ===========================================================================
# T095 -- the two categories the link pass could not find, measured live
# ===========================================================================
#
# Artifacts: `_snapshots/skips-038-t095-ngoreme.json` (the slice of both run
# reports the claim rests on), `census-038-t095-ngoreme.json`,
# `census-038-t095-ejagham.json`.
# Driver: `python debug/run038_before_after_pairs.py ngoreme --tag t095`,
# `Ngoreme FLEx` -> `GT038 Ngoreme After` restored from
# `Target 2026-07-06 0218.fwbackup`.
#
# WHY THE EVIDENCE IS COMMITTED AS ITS OWN ARTIFACT. `_run_reports/` is
# gitignored, and T095's own filing cited a run report in the `038-t091`
# worktree, which has since been removed -- so the evidence for the defect
# could not be re-read when the task was picked up. That is T102's shape one
# more time (evidence that stops existing), and the fix is to commit the slice
# rather than the path.
#
# WHY THE CENSUS CANNOT SHOW THIS. `InflectableFeatsRC` is a REFERENCE
# COLLECTION, not a counted object class, so losing it moves no census row and
# `total_shortfall` reads clean. The instrument is the run report's skip list.

_T095 = _SNAPSHOT_DIR / "skips-038-t095-ngoreme.json"


def _t095() -> dict:
    if not _T095.is_file():
        pytest.skip(
            "no committed T095 measurement at " + str(_T095)
            + " -- produce it with `python debug/run038_before_after_pairs.py "
            "ngoreme --tag t095`")
    return json.loads(_T095.read_text(encoding="utf-8"))


def test_the_two_reused_categories_were_reported_unresolved() -> None:
    """THE BEFORE, from a committed record rather than from memory. Both GUIDs
    belong to categories the SAME run reused by natural key -- the report's
    own `identity_substitution` counts 5 for GRAM_CATEGORIES -- and the link
    pass called them absent."""
    before = _t095()["before"]
    assert before["identity_substitution_per_category"]["GRAM_CATEGORIES"] == 5
    skips = before["gram_categories_skips"]
    assert len(skips) == 2
    assert {s["source_guid"][:8] for s in skips} == {"c46c8242", "ff5c5e07"}
    assert all(s["reason"] == "DEPENDENCY_UNRESOLVED" for s in skips)
    assert all("not in target after" in s["detail"] for s in skips)


def test_after_the_sweep_no_category_is_reported_unresolved() -> None:
    """THE AFTER. Same pair, same backup, same selection, same branch plus the
    sweep: 0. The categories resolve by natural key and their inflectable
    features are wired."""
    after = _t095()["after"]
    assert after["gram_categories_skips"] == []
    assert "GRAM_CATEGORIES" not in after["skips_by_category"]


def test_the_sweep_moved_nothing_else_in_the_report() -> None:
    """THE CONTROL INSIDE THE SAME RUN. A resolver that started answering
    where it used to return None could have changed any number of other
    outcomes; the rest of the report is identical. `leaf_failed` matters most
    -- 11 swallowed `natural_classes_execute_action` raises before and after,
    so the sweep neither introduced a raise nor hid one."""
    blob = _t095()
    before, after = blob["before"], blob["after"]
    assert before["skips_by_category"]["AFFIXES"] == 20
    assert after["skips_by_category"]["AFFIXES"] == 20
    assert before["leaf_failed"] == after["leaf_failed"] == 11
    assert (before["identity_substitution_total"]
            == after["identity_substitution_total"] == 26)
    assert before["skips_total"] - after["skips_total"] == 2


def test_the_census_delta_is_source_drift_and_not_this_task() -> None:
    """THE HONESTY METRIC. `total_shortfall` moves 70638 -> 70646, and none of
    the +8 is T095's: `Ngoreme FLEx` drifted again between the runs (+11
    across short classes) and three rows improved (-3) from the process-rule
    tasks that landed between them. Stating the arithmetic is what separates a
    measurement from a number."""
    c = _t095()["census_ngoreme"]
    assert c["totals_before"]["total_shortfall"] == 70638
    assert c["totals_after"]["total_shortfall"] == 70646
    drift = sum(r["source_drift"] for r in c["rows_that_moved"])
    shortfall = sum(r["shortfall_delta"] for r in c["rows_that_moved"])
    assert shortfall == 8
    assert drift == 25, "source drift across every moved row"
    improved = [r["class"] for r in c["rows_that_moved"]
                if r["shortfall_delta"] < 0]
    assert sorted(improved) == [
        "MoAffixProcess", "PhSequenceContext", "PhSimpleContextNC"]


def test_the_part_of_speech_row_did_not_move() -> None:
    """T091's clause, still closed. A sweep that bought its repair by putting
    the duplicates back would show here first."""
    c = _t095()["census_ngoreme"]
    assert "PartOfSpeech" not in {r["class"] for r in c["rows_that_moved"]}
    assert (c["totals_before"]["duplicate_extra_objects"]
            == c["totals_after"]["duplicate_extra_objects"] == 21)


def test_ejagham_is_byte_stable() -> None:
    """THE REGRESSION CHECK. Ejagham's starters carry the GOLD catalog GUIDs
    and match on identity, so it never enters the natural-key fallback -- it
    could not see T091's defect and cannot see T095's. Every total identical;
    the only two rows that moved are a NOT_EVALUATED reporting shape
    (`source_count` 0 -> None) that contributes 0 to either total and is
    present on the Ngoreme run too."""
    c = _t095()["census_ejagham_control"]
    assert c["totals_before"] == c["totals_after"]
    assert c["totals_after"]["total_shortfall"] == 4781
    assert c["totals_after"]["unexplained_shortfall"] == 3063
    assert sorted(r["class"] for r in c["rows_that_moved"]) == [
        "MoForm", "MoMorphSynAnalysis"]
    assert all(r["shortfall_delta"] == 0 for r in c["rows_that_moved"])
