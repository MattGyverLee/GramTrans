"""T045f -- plane 2 has a home on the artifact, and it is not plane 1's.

Feature 035, Phase 5 / US2 wave 3b. Contract:
``specs/035-fullsweep-fidelity/contracts/artifact-schema.md``.

What these tests are actually defending. Before T045f the field plane was
computed and thrown away: ``compare.py``'s T039-T043 rules and
``coverage.py``'s report both produced records with ``as_dict()``, and
``ProjectArtifact`` had nowhere to put any of them. A run could therefore
only ever report the object plane, and the document said nothing at all
about whether a correctly-counted object arrived with its fields intact.

So the tests below check three things that are easy to regress and silent
when they do:

1. the five blocks survive a real ``flush_artifact`` round trip;
2. FR-093's plane separation holds in both directions;
3. a record stored raw is REFUSED rather than written as its repr --
   ``_atomic_write_json`` passes ``default=str``, so an unserializable value
   would otherwise land in the document looking like evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO / "debug") not in sys.path:
    sys.path.insert(0, str(_REPO / "debug"))

from fullsweep import artifact as A            # noqa: E402
from fullsweep import compare                  # noqa: E402
from fullsweep.moves import HarnessError       # noqa: E402


def _artifact(**kw) -> A.ProjectArtifact:
    base = dict(
        project="Ejagham Mini", run_intent="baseline", revision_pair={},
        dirty_gramtrans=False, coverage_categories=[],
    )
    base.update(kw)
    return A.ProjectArtifact(**base)


# ---------------------------------------------------------------------------
# The fields exist, default to empty, and are declared on the dataclass
# ---------------------------------------------------------------------------

def test_every_plane_two_field_is_a_declared_dataclass_field():
    """``flush_artifact`` is ``asdict(artifact)``, so a block that is not a
    declared field never reaches the document at all."""
    declared = {f.name for f in A.ProjectArtifact.__dataclass_fields__.values()}
    assert set(A.FIELD_PLANE_ARTIFACT_FIELDS) <= declared


def test_plane_two_fields_default_empty_not_absent():
    art = _artifact()
    assert art.comparisons == {}
    assert art.link_findings == []
    assert art.depth == {}
    assert art.coverage == {}
    assert art.census == {}


def test_blocks_survive_a_real_flush_round_trip(tmp_path):
    art = _artifact()
    A.record_field_plane(
        art,
        comparisons={"LexEntry": {"rule": "ws-mapped", "performed": 12, "findings": 0}},
        link_findings=[compare.LinkResult(
            verdict="SILENTLY_UNSET", basis="no accounting record",
            class_name="LexSense", field_name="MorphoSyntaxAnalysisRA",
            source_referent="abc", target_referent=None)],
        depth=A.depth_block(()),
        coverage={"counts": {}},
        census=A.census_block(),
    )
    out = A.flush_artifact(art, tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    for name in A.FIELD_PLANE_ARTIFACT_FIELDS:
        assert name in doc, "%s never reached the document" % name
    assert doc["link_findings"][0]["verdict"] == "SILENTLY_UNSET"
    assert doc["link_findings"][0]["field"] == "MorphoSyntaxAnalysisRA"


# ---------------------------------------------------------------------------
# FR-093 -- the two planes stay structurally separate
# ---------------------------------------------------------------------------

def test_field_plane_keys_are_still_refused_in_the_object_block():
    """The constraint T045f was written around: plane-2 output gets its own
    artifact field, and folding it into ``accounting`` still fails."""
    art = _artifact()
    art.accounting = {"project": "X", "link_findings": []}
    with pytest.raises(HarnessError) as exc:
        A.record_field_plane(art, comparisons={})
    assert "FR-093" in str(exc.value)


def test_recording_plane_two_leaves_the_object_block_untouched():
    art = _artifact()
    art.accounting = {"project": "X", "counts": {"transferred_equal_payload": 3}}
    A.record_field_plane(art, comparisons={"LexEntry": {}}, link_findings=[])
    assert art.accounting == {"project": "X", "counts": {"transferred_equal_payload": 3}}
    assert not (compare.FIELD_PLANE_KEYS & set(art.accounting))


# ---------------------------------------------------------------------------
# FR-145 -- a record stored raw is refused, not stringified
# ---------------------------------------------------------------------------

def test_an_unserializable_block_is_refused_at_the_point_of_record():
    art = _artifact()
    with pytest.raises(HarnessError) as exc:
        A.record_field_plane(art, comparisons={"LexEntry": object()})
    assert "FR-145" in str(exc.value)


def test_a_raw_record_in_link_findings_is_coerced_not_stringified():
    art = _artifact()
    A.record_field_plane(art, link_findings=[compare.LinkResult(
        verdict="RESOLVED", basis="identity", class_name="LexEntry",
        field_name="SensesOS")])
    assert art.link_findings == [{
        "verdict": "RESOLVED", "basis": "identity", "class": "LexEntry",
        "field": "SensesOS", "source_referent": None, "target_referent": None,
    }]


def test_a_non_record_non_dict_link_finding_is_refused():
    art = _artifact()
    with pytest.raises(HarnessError) as exc:
        A.record_field_plane(art, link_findings=["SILENTLY_UNSET"])
    assert "FR-145" in str(exc.value)


def test_none_means_unmeasured_and_leaves_the_field_alone():
    """An argument omitted is "this run did not measure it", which must not
    overwrite a block an earlier phase already recorded."""
    art = _artifact()
    A.record_field_plane(art, coverage={"counts": {"attempted_and_clean": 4}})
    A.record_field_plane(art, comparisons={"LexEntry": {}})
    assert art.coverage == {"counts": {"attempted_and_clean": 4}}


# ---------------------------------------------------------------------------
# FR-189 -- the depth block keeps its three dispositions apart
# ---------------------------------------------------------------------------

def _depth(class_name, src, tgt, *, evaluated=True, mismatches=(), verdict="EQUAL"):
    return compare.StructuralDepthResult(
        class_name=class_name, source_max_depth=src, target_max_depth=tgt,
        degree_mismatches=tuple(mismatches), parents_compared=1,
        evaluated=evaluated, verdict=verdict,
    )


def test_depth_block_separates_vacuous_from_not_evaluated_from_disagreement():
    block = A.depth_block([
        _depth("LexSense", 3, 3),
        _depth("ReversalIndexEntry", 4, 2),                       # vacuous
        _depth("CmPossibility", 1, 1, evaluated=False,
               verdict=compare.DEPTH_NOT_EVALUATED),              # never nested
        _depth("PartOfSpeech", 2, 2, mismatches=[("p1", 5, 4)]),  # disagreement
    ])
    assert block["vacuous_classes"] == ["ReversalIndexEntry"]
    assert block["not_evaluated_classes"] == ["CmPossibility"]
    assert block["per_parent_degree_findings"] == [
        {"class": "PartOfSpeech", "parent_source_id": "p1",
         "source_children": 5, "target_children": 4},
    ]
    assert block["max_nesting_depth"]["LexSense"] == {"source": 3, "target": 3}
    assert block["classes_compared"] == 4


def test_a_not_evaluated_class_is_never_also_called_vacuous():
    """The two mean different things -- "the corpus never nested it" versus
    "the target lost the nesting" -- and a class must land in exactly one."""
    block = A.depth_block([
        _depth("CmPossibility", 3, 1, evaluated=False,
               verdict=compare.DEPTH_NOT_EVALUATED),
    ])
    assert block["not_evaluated_classes"] == ["CmPossibility"]
    assert block["vacuous_classes"] == []


def test_depth_block_of_nothing_measured_is_empty_not_clean():
    block = A.depth_block(())
    assert block["classes_compared"] == 0
    assert block["max_nesting_depth"] == {}


# ---------------------------------------------------------------------------
# The 038 cut -- the census block REFERENCES 038's artifact, never copies it
# ---------------------------------------------------------------------------

def test_a_census_reference_carrying_rows_is_refused():
    with pytest.raises(HarnessError) as exc:
        A.assert_census_is_reference_only({"path": "x.json", "classes": [{"a": 1}]})
    assert "038 cut" in str(exc.value)


def test_record_field_plane_refuses_an_embedded_census():
    art = _artifact()
    block = A.census_block()
    block["plane1_reference"]["classes"] = [{"object_class": "LexEntry"}]
    with pytest.raises(HarnessError):
        A.record_field_plane(art, census=block)


def test_reference_to_a_real_census_records_path_hash_and_identity(tmp_path):
    doc = {"schema_version": 1, "census_id": "CENSUS-20260919-101500",
           "taken_at": "2026-09-19T10:15:00", "verdict": "CENSUS_CLEAN",
           "classes": [{"object_class": "LexEntry"}, {"object_class": "LexSense"}]}
    path = tmp_path / "census.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    ref = A.plane1_census_reference(path)
    assert ref["present"] is True
    assert ref["error"] == ""
    assert ref["content_hash"].startswith("sha256:")
    assert ref["census_id"] == "CENSUS-20260919-101500"
    assert ref["class_row_count"] == 2
    assert "classes" not in ref, "the reference must not carry the rows"


def test_the_hash_changes_when_the_census_does(tmp_path):
    """The whole point of recording the hash: a reader can tell whether the
    census this run was gated against is the one still on disk."""
    path = tmp_path / "census.json"
    base = {"schema_version": 1, "classes": [{"object_class": "LexEntry"}]}
    path.write_text(json.dumps(base), encoding="utf-8")
    first = A.plane1_census_reference(path)["content_hash"]

    base["classes"].append({"object_class": "LexSense"})
    path.write_text(json.dumps(base), encoding="utf-8")
    assert A.plane1_census_reference(path)["content_hash"] != first


def test_a_missing_census_is_recorded_not_raised(tmp_path):
    ref = A.plane1_census_reference(tmp_path / "absent.json")
    assert ref["present"] is False
    assert ref["error"]
    assert ref["content_hash"] is None


def test_a_stranger_json_is_refused_as_a_census(tmp_path):
    path = tmp_path / "not-a-census.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    ref = A.plane1_census_reference(path)
    assert ref["present"] is True
    assert "not a census artifact" in ref["error"]
    assert ref["class_row_count"] is None


def test_census_block_with_no_reference_says_so_rather_than_looking_clean():
    block = A.census_block()
    assert block["plane1_reference"]["present"] is False
    assert block["field_census_measured"] is False
    assert block["omitted_properties_per_class"] == {}
