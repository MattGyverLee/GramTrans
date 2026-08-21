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
    AFFIX_TO_SLOT           uncast/cast equal          no cast needed

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
_NO_CAST_EDGES = ("SLOT_TO_POS", "TEMPLATE_TO_POS", "AFFIX_TO_SLOT")

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


#: The relationships T067 registered, and the one it did not. Keyed by the
#: `DependencyKind` NAME so the table can be read next to the snapshot's
#: `relationships` block, which is keyed the same way.
_REGISTERED = ("AFFIX_TO_POS", "MSA_TO_FEAT_STRUC_TYPE", "SLOT_TO_POS")
_REFUSED = ("MSA_TO_INFL_FEATURE",)


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
    """
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import DependencyKind

    registered_names = {k.name for k in categories.CLOSURE_EDGES_VERIFIED}
    assert registered_names == set(_REGISTERED)

    for snap in _snapshots():
        rels = snap["relationships"]
        for name in _REGISTERED:
            assert rels[name]["verdict"] == "CONFIRMED", (
                name + " is REGISTERED but " + snap["source_project"]
                + " measured it " + rels[name]["verdict"]
            )
        for name in _REFUSED:
            assert rels[name]["verdict"].startswith("REFUSED"), (
                name + " measured " + rels[name]["verdict"] + " on "
                + snap["source_project"] + " -- if that is now CONFIRMED the "
                "registration decision has to be revisited deliberately, not "
                "by relaxing this test"
            )
            assert getattr(DependencyKind, name) \
                not in categories.CLOSURE_EDGES_VERIFIED


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
    """
    for name in _REGISTERED:
        row = snap["relationships"][name]
        assert row["edges"] > 0, name
        assert row["foreign_edges"] == 0, name
        assert row["unresolved"] == 0, (name, row["unresolved_sample"])
        assert row["resolved_as_owned_value"] == 0, name
        assert row["resolved_as_piece"] == row["distinct_far_guids"], name


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_refused_relationship_is_refused_for_the_recorded_reason(snap) -> None:
    """The refusal, pinned to its cause rather than to its verdict string.

    `MSA_TO_INFL_FEATURE` is not refused because its producer is broken -- it
    returns edges, and none of them is foreign. It is refused because most of
    its far GUIDs are `IFsSymFeatVal` symbolic values that
    `inflection_features_enumerate_source` never yields. If that ever stops
    being true, this test fails and the registration decision gets made again
    on new evidence, which is the correct way for it to change.
    """
    row = snap["relationships"]["MSA_TO_INFL_FEATURE"]
    assert row["edges"] > 0
    assert row["foreign_edges"] == 0
    assert row["resolved_as_owned_value"] > 0, (
        "the refusal rests on far GUIDs that are owned symbolic values; none "
        "was found, so the recorded reason no longer holds: " + repr(row)
    )
    assert row["verdict"] == "REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE"


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
            "MSA_TO_INFL_FEATURE": 206,
            "SLOT_TO_POS": 19,
        },
        "Ejagham Mini": {
            "AFFIX_TO_POS": 88,
            "MSA_TO_FEAT_STRUC_TYPE": 17,
            "MSA_TO_INFL_FEATURE": 34,
            "SLOT_TO_POS": 9,
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
    expected_population = {
        "AFFIX_TO_POS": None,          # AFFIXES: a subset of lex_entries
        "MSA_TO_FEAT_STRUC_TYPE": None,
        "MSA_TO_INFL_FEATURE": None,
        "SLOT_TO_POS": pop["slots"],
    }
    for name, want in expected_population.items():
        row = snap["relationships"][name]
        assert row["population"] > 0, name
        if want is None:
            # AFFIXES enumerates a SUBSET of the lexicon, so the exact number
            # is the corpus's business -- but it must not silently become the
            # whole lexicon, which is what the discredited measurement did.
            assert row["population"] <= pop["lex_entries"], name
            assert row["source_category"] == "affixes", name
        else:
            assert row["population"] == want, (name, row["population"], want)
            assert row["source_category"] == "slots", name


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
        "Mbugwe LizzieHC practice": 1063,
        "Ejagham Mini": 405,
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
