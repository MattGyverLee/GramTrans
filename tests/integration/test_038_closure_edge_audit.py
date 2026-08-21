"""T067 / T068 / T069 -- the FR-018 audit that decides which closure edges may
be registered at all.

Asserted against COMMITTED MEASUREMENTS
(`_snapshots/closure-edge-audit-038-*.json`, produced by
`debug/audit038_closure_edges.py` over two live projects, read-only). Same
discipline as `test_038_process_rules.py`: measure once against a real
database, commit the numbers, assert against the record -- a suite invocation
may not open FLEx projects by surprise.

WHAT THE AUDIT FOUND, AND WHY IT MATTERS MORE THAN THE REGISTRATION IT BLOCKED.

FR-018 exists so no dependency relationship influences a plan before someone
checked it. Phase 7's plan assumed the checking would be a formality and the
three edges would register one after another. Two of them cannot register at
all, because their producers do not work on live data:

    AFFIX_TO_POS            uncast 0, cast 296 / 245   DEAD
    MSA_TO_FEAT_STRUC_TYPE  uncast 0, cast 216 /  40   DEAD
    SLOT_TO_POS             uncast/cast equal          OK
    TEMPLATE_TO_POS         uncast/cast equal          OK
    AFFIX_TO_SLOT           uncast/cast equal          OK

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

TWO CORPORA, DELIBERATELY. A DEAD verdict from one project could be a property
of that project's data. `Mbugwe LizzieHC practice` (255 entries, 279 MSAs) and
`Ejagham Mini` (252 entries, 247 MSAs) return identical verdicts on all five
edges, which makes it a property of the producer.

THESE TESTS PIN THE DEFECT, NOT THE FIX. `test_the_dead_edges_are_still_dead`
asserts the CURRENT broken behaviour on purpose, exactly as
`test_038_process_rules.py::test_the_reported_rules_are_not_yet_readable_as_
accounted` does for T087. Closing the defect is therefore a deliberate edit to
this file rather than a silent drift, and the assertion names the task that
must do it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_SNAPSHOT_DIR = Path(__file__).parent / "_snapshots"
_PATTERN = "closure-edge-audit-038-*.json"

#: The producers this audit proved DEAD on live data, with the task that must
#: fix each before its edge may be registered.
_DEAD_EDGES = {
    "AFFIX_TO_POS": "T088",
    "MSA_TO_FEAT_STRUC_TYPE": "T088",
}

#: The producers that audited clean and are therefore ELIGIBLE for
#: registration. Eligible is not the same as registered: registration still
#: needs its own census run (T068 / T069).
_LIVE_EDGES = ("SLOT_TO_POS", "TEMPLATE_TO_POS", "AFFIX_TO_SLOT")


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
        "the DEAD verdicts rest on cross-corpus agreement; got only "
        + ", ".join(_ids(snaps))
    )


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_audit_is_read_only_and_saw_real_pieces(snap) -> None:
    """A verdict computed over an empty enumeration is not a verdict. This is
    what makes `NO_DATA` distinct from `OK` in the driver."""
    assert snap["read_only"] is True
    pop = snap["population"]
    assert pop["lex_entries"] > 0
    assert pop["msas"] > 0
    assert pop["slots"] > 0
    assert pop["templates"] > 0


# ---------------------------------------------------------------------------
# The finding: two edges are dead, and must not be registered
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_dead_edges_are_still_dead(snap) -> None:
    """PINS THE DEFECT ON PURPOSE (the T087 pattern).

    `uncast == 0` while `cast > 0` is the whole finding: the producer reads
    nothing on live data, and the only reason anyone believed otherwise is
    that its unit tests use fakes that expose the attribute directly.

    When T088 casts the MSA to its concrete interface, these assertions
    SHOULD fail, and the failure is the signal to re-run the audit and edit
    this test -- not to delete it.
    """
    for edge, owner_task in _DEAD_EDGES.items():
        row = snap["edges"][edge]
        assert row["verdict"] == "DEAD", (
            edge + " changed verdict to " + row["verdict"] + " -- if "
            + owner_task + " fixed the producer, re-run "
            "debug/audit038_closure_edges.py and update this expectation"
        )
        assert row["uncast"] == 0, (
            edge + " now sees " + str(row["uncast"]) + " refs uncast"
        )
        assert row["cast"] > 0, (
            edge + " has nothing to find even WITH a cast, so this corpus "
            "cannot establish the producer is dead"
        )


@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_a_dead_edge_is_not_registered(snap) -> None:
    """The consequence that actually protects a user: an edge the audit
    failed must not be in the allowlist, because registering it would put a
    `verified_by` on a relationship that contributes nothing -- FR-018's
    mechanism inverted into a rubber stamp."""
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import DependencyKind

    for edge in _DEAD_EDGES:
        kind = getattr(DependencyKind, edge, None)
        if kind is None:
            continue
        assert kind not in categories.CLOSURE_EDGES_VERIFIED, (
            edge + " is registered in CLOSURE_EDGES_VERIFIED, but the live "
            "audit says its producer returns nothing on real data"
        )


# ---------------------------------------------------------------------------
# The other half: three edges audited clean
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("snap", _snapshots(), ids=_ids(_snapshots()))
def test_the_live_edges_read_correctly(snap) -> None:
    """These three read `Owner` and the template slot sequences, all of which
    ARE visible on the collections' element types -- so the uncast read the
    producer performs matches the cast ground truth exactly.

    This is the half that makes the DEAD verdicts meaningful: the audit is
    capable of returning OK, so a DEAD verdict is not just the harness
    failing to see anything.
    """
    for edge in _LIVE_EDGES:
        row = snap["edges"][edge]
        assert row["verdict"] == "OK", edge + " -> " + row["verdict"]
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
