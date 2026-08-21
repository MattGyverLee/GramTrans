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

WHAT IS STILL NOT REGISTERED. T088 made the producers read. It did NOT
register anything: `CLOSURE_EDGES_VERIFIED` is still empty, so no edge
influences a plan yet, and T067 still owes the member-split decision --
`affixes_dependencies` returns a MIXED edge set (measured: gram_categories,
feature_struct_types and inflection_features all in one return value), which a
single-`DependencyKind` registry row would mislabel under one `verified_by`.
The counts asserted here are what make that concrete rather than theoretical.
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


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_nothing_is_registered_on_the_strength_of_this_audit(snap) -> None:
    """T088 made the producers read; it did not earn anyone a `verified_by`.

    Registration is still T067's / T068's / T069's, each behind its own census
    run. Asserting the registry is empty keeps "the producer works" from
    silently becoming "the edge is verified" -- which is the substitution
    FR-018 exists to prevent.
    """
    from gramtrans.Lib import categories

    assert categories.CLOSURE_EDGES_VERIFIED == {}


# ---------------------------------------------------------------------------
# Signal 2 -- what the producers return. This is the T088 regression guard.
# ---------------------------------------------------------------------------

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
