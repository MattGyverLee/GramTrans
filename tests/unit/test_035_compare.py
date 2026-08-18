"""Feature 035 -- T036: the field-plane classification tests.

Source: spec.md Section E (FR-051..FR-092), contracts/rosters.md section 1,
contracts/expected-divergent.json.

NO FLEx project and NO LCM. ``census_fields`` takes an injected ``field_source``
exactly so this plane is testable offline; every fixture below is a plain dict.

SCOPE, stated honestly. tasks.md T036 lists the whole of FR-051..FR-092, but
Phase 5 gates its waves: Wave 1 (T037 census surface + T038 roster) is what
exists at the time this file lands. So this file covers **FR-051..FR-068** --
the census surface, the EXPECTED_DIVERGENT roster's effective composition,
tag-stripping, and the coverage-growth rule.

The Wave-2 rules -- writing-system mapping (FR-069..FR-072), the DISTORTED
classes (FR-073..FR-078), order semantics (FR-079..FR-084), the five link
verdicts (FR-085..FR-090), and structural depth (FR-189) -- are asserted in the
``TestWave2NotYetImplemented`` guard at the bottom, which fails the moment those
surfaces appear without their tests. That is deliberate: a test file that
silently covered less than its task claims would be the same silent-absorption
failure FR-052 exists to prevent.

Per FR-176 the contract facts below are transcribed as INDEPENDENT literals from
spec.md and the measured LCM enumeration, so the module is never checked against
its own constants.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import census  # noqa: E402

# ---------------------------------------------------------------------------
# Contract literals -- transcribed, NOT imported.
# ---------------------------------------------------------------------------

#: FR-055/FR-056/FR-059..FR-064: the fields the roster excludes, and the FR that
#: excludes each. Transcribed from spec.md Section E.2.
CONTRACT_EXCLUDED_FIELDS = {
    "DateCreated": "FR-055",
    "DateModified": "FR-056",
    "OwnOrd": "FR-059",
    "OwningFlid": "FR-060",
    "HomographNumber": "FR-061",
    "ImportResidue": "FR-062",
    "LiftResidue": "FR-062",
    "Checksum": "FR-064",
}

#: FR-067: the discriminating case for FR-053. This field is excluded from the
#: interactive merge-preview UI's diff pane and MUST STILL be fidelity-checked.
#: If it ever appears in the roster's exclusions, the roster has been derived
#: from the UI's exclusion set, which FR-053 forbids in whole or in part.
CONTRACT_MUST_BE_COMPARED = (("PhRegularRule", "Direction"),)

#: FR-065: boolean/flag fields measured live on transferred classes. Each MUST be
#: ordinary content unless the engine's own syncable surface omits it -- never
#: waved through by a naming heuristic.
CONTRACT_BOOLEANS_COMPARED = (
    ("MoAffixAllomorph", "IsAbstract"),
    ("MoEndoCompound", "Disabled"),
    ("MoInflAffixTemplate", "Disabled"),
    ("MoMorphAdhocProhib", "Disabled"),
    ("PhRegularRule", "Disabled"),
)

#: FR-063: the Carrier-B provenance marker and wire format.
CONTRACT_TAG_MARKER = "[GT-Tag]: "

#: Per-class presence measured live on 2026-08-19 (read-only FLExToolsMCP,
#: op-002401657-002, IFwMetaDataCacheManaged.GetFields over 'Ejagham Mini').
#: Transcribed here so the roster is checked against the MEASUREMENT, not
#: against the generator that produced it.
CONTRACT_MEASURED_PRESENCE = {
    "HomographNumber": {"LexEntry"},
    "ImportResidue": {"LexEntry", "LexSense"},
    "Checksum": {"WfiWordform"},
    "LiftResidue": {"LexEntry", "LexSense", "MoAffixAllomorph", "MoDerivAffMsa",
                    "MoInflAffMsa", "MoStemMsa"},
}

#: The class universe the roster was built over: the classes actually measured
#: in batch 1's censuses across the three FR-160 pilots.
CONTRACT_CLASS_COUNT = 66


@pytest.fixture(scope="module")
def roster():
    return census.load_expected_divergent()


def _roster(tmp_path, doc) -> census.ExpectedDivergentRoster:
    p = tmp_path / "expected-divergent.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return census.load_expected_divergent(p)


def _minimal(**kw) -> dict:
    doc = {"schema_version": 1, "entries": []}
    doc.update(kw)
    return doc


# ===========================================================================
# FR-052 / FR-053: the roster is REQUIRED, validated, and not the UI's set
# ===========================================================================

class TestRosterContract:

    def test_absent_roster_raises_rather_than_meaning_no_exclusions(self, tmp_path):
        """FR-052 permits no exclusion mechanism other than this roster, so an
        absent roster is NOT 'no exclusions' -- it would report every excluded
        field as loss. It must refuse to run."""
        with pytest.raises(census.CensusContractError, match="REQUIRED"):
            census.load_expected_divergent(tmp_path / "nope.json")

    def test_wrong_schema_version_refused(self, tmp_path):
        with pytest.raises(census.CensusContractError, match="schema_version"):
            _roster(tmp_path, {"schema_version": 2, "entries": []})

    def test_unreadable_roster_refused(self, tmp_path):
        p = tmp_path / "expected-divergent.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(census.CensusContractError, match="unreadable"):
            census.load_expected_divergent(p)

    @pytest.mark.parametrize("missing", ["class", "field", "rationale"])
    def test_entry_missing_any_required_key_refused(self, tmp_path, missing):
        """FR-056: promoting a field onto the roster is a recorded, reviewable
        act, so an entry with no rationale is not an entry."""
        e = {"class": "LexEntry", "field": "DateCreated", "rationale": "because"}
        e.pop(missing)
        with pytest.raises(census.CensusContractError, match=missing):
            _roster(tmp_path, _minimal(entries=[e]))

    def test_field_both_excluded_and_compared_is_refused(self, tmp_path):
        """A self-contradictory roster would make the verdict depend on lookup
        order, which is not a verdict."""
        doc = _minimal(
            entries=[{"class": "PhRegularRule", "field": "Direction",
                      "rationale": "wrong -- FR-067 says compare it"}],
            compared_not_excluded=[{"class": "PhRegularRule", "field": "Direction"}],
        )
        with pytest.raises(census.CensusContractError, match="self-contradictory"):
            _roster(tmp_path, doc)

    def test_shipped_roster_loads(self, roster):
        assert roster.schema_version == 1
        assert len(roster.excluded) == CONTRACT_CLASS_COUNT

    def test_ui_legibility_exclusion_is_not_a_fidelity_exclusion(self, roster):
        """FR-053 + FR-067. The single most diagnostic assertion in this file:
        a phonological rule's direction-of-application field is excluded from the
        merge-preview UI's diff pane, so if the roster had been derived by
        re-scraping that UI -- in whole OR IN PART -- this field would be
        excluded here. It must not be."""
        for cls, field in CONTRACT_MUST_BE_COMPARED:
            assert not roster.is_roster_excluded(cls, field), (
                "%s.%s is EXCLUDED, which means the roster was derived from the "
                "merge-preview UI's exclusion set (FR-053)" % (cls, field)
            )

    def test_booleans_are_compared_not_named_away(self, roster):
        """FR-065: a boolean is EXPECTED_DIVERGENT only when the ENGINE omits it,
        never by a blanket naming heuristic on the roster."""
        for cls, field in CONTRACT_BOOLEANS_COMPARED:
            assert not roster.is_roster_excluded(cls, field)
            assert field in roster.compared_not_excluded.get(cls, frozenset()), (
                "%s.%s should be recorded in compared_not_excluded so its "
                "absence from the exclusions cannot be read as an oversight"
                % (cls, field)
            )


# ===========================================================================
# FR-054..FR-068: the enumerated exclusions, per class
# ===========================================================================

class TestEnumeratedExclusions:

    def test_every_excluded_field_is_on_a_class_that_actually_has_it(self, roster):
        """FR-056 forbids exclusion by naming heuristic; the corollary is that
        exclusions are enumerated against MEASURED presence, so the roster must
        not exclude a field from a class that does not expose it."""
        for field, classes in CONTRACT_MEASURED_PRESENCE.items():
            actual = {c for c in roster.excluded if field in roster.excluded_for(c)}
            assert actual == classes, (
                "%s excluded on %s but measured present on %s"
                % (field, sorted(actual), sorted(classes))
            )

    def test_position_and_schema_id_excluded_on_every_class(self, roster):
        """FR-059 (OwnOrd) and FR-060 (OwningFlid) were measured present on all
        66 classes, so both must be excluded on all 66."""
        for field in ("OwnOrd", "OwningFlid"):
            n = sum(1 for c in roster.excluded if field in roster.excluded_for(c))
            assert n == CONTRACT_CLASS_COUNT, "%s excluded on %d/%d classes" % (
                field, n, CONTRACT_CLASS_COUNT)

    def test_no_exclusion_outside_the_contract_field_set(self, roster):
        """Every excluded field must trace to one of FR-055..FR-064. An exclusion
        with no FR behind it is exactly the silent scope creep FR-052 forbids."""
        seen = {f for c in roster.excluded for f in roster.excluded_for(c)}
        assert seen <= set(CONTRACT_EXCLUDED_FIELDS), (
            "excluded fields with no FR behind them: %s"
            % sorted(seen - set(CONTRACT_EXCLUDED_FIELDS))
        )

    def test_runtime_session_identifier_is_not_a_roster_entry(self, roster):
        """FR-054. ``Hvo`` is not an LCM model field at all, so a metadata-driven
        census cannot reach it and no per-class entry is constructible. The
        roster must say so structurally rather than carry 66 phantom entries."""
        for cls in roster.excluded:
            assert not roster.is_roster_excluded(cls, "Hvo")
        doc = json.loads(Path(census.DEFAULT_ROSTER_PATH).read_text(encoding="utf-8"))
        frs = {b.get("fr") for b in doc["structural_exclusions_not_expressible_per_class"]}
        assert {"FR-054", "FR-057", "FR-058", "FR-068"} <= frs


# ===========================================================================
# FR-063: the tool's own provenance tag is stripped, never reported
# ===========================================================================

class TestProvenanceTagStripping:

    def test_tag_line_removed_and_surrounding_prose_kept(self, roster):
        v = "real prose line\n%sGT|GT-20260819-000246|Ejagham Mini|2026-08-19" % (
            CONTRACT_TAG_MARKER,)
        assert census.strip_provenance_tag(v, roster) == "real prose line"

    def test_tag_only_value_becomes_empty_not_none(self, roster):
        v = "%sGT|GT-20260819-000246|Ejagham Mini|2026-08-19" % CONTRACT_TAG_MARKER
        assert census.strip_provenance_tag(v, roster) == ""

    def test_indented_tag_line_still_stripped(self, roster):
        v = "prose\n    %sGT|x|y|z" % CONTRACT_TAG_MARKER
        assert census.strip_provenance_tag(v, roster) == "prose"

    def test_marker_mentioned_mid_sentence_is_prose_and_kept(self, roster):
        """Only a marker-LED line is the tool's tag. A sentence that merely
        mentions the marker is user data and must survive untouched, or the
        comparator would silently delete content it was asked to check."""
        v = "the docs say %s is the marker" % CONTRACT_TAG_MARKER
        assert census.strip_provenance_tag(v, roster) == v

    def test_untagged_value_returned_unchanged_and_unstripped(self, roster):
        """A value with no tag must be returned byte-identical -- including its
        own leading/trailing whitespace, because FR-073 makes that whitespace a
        DISTORTED signal that this function must not launder away."""
        v = "  spaced content  "
        assert census.strip_provenance_tag(v, roster) is v

    @pytest.mark.parametrize("v", [None, 3, 4.5, True, {"en": "x"}, ["a"]])
    def test_non_strings_pass_through(self, roster, v):
        assert census.strip_provenance_tag(v, roster) is v


# ===========================================================================
# FR-051 / FR-052 / FR-066: the effective composition
# ===========================================================================

class TestClassFieldCoverage:

    def test_effective_exclusion_is_roster_union_engine_omitted(self, tmp_path):
        """FR-066: the complete roster for a class is this document's entries
        PLUS whatever the engine's syncable surface omits."""
        r = _roster(tmp_path, _minimal(entries=[
            {"class": "C", "field": "DateCreated", "rationale": "FR-055"}]))
        cov = census.class_field_coverage(
            "C", model_fields=["DateCreated", "Form", "Gloss", "Secret"],
            syncable_fields=["DateCreated", "Form", "Gloss"], roster=r)
        assert cov.engine_omitted == ("Secret",)
        assert cov.roster_excluded == ("DateCreated",)
        assert cov.compared == ("Form", "Gloss")

    def test_unenumerable_class_raises_rather_than_reporting_full_coverage(self, roster):
        """FR-051: an empty model enumeration is a broken measurement, not an
        empty class. Reporting coverage over nothing is the failure mode."""
        with pytest.raises(census.CensusContractError, match="no model fields"):
            census.class_field_coverage("C", [], [], roster)

    def test_syncable_field_absent_from_model_raises(self, roster):
        """If the two surfaces disagree, neither the omitted set nor the compared
        set is trustworthy, so no verdict may rest on them."""
        with pytest.raises(census.CensusContractError, match="disagree"):
            census.class_field_coverage("C", ["Form"], ["Form", "Ghost"], roster)

    def test_omitted_set_is_enumerated_on_the_artifact_block(self, tmp_path):
        """FR-052: the omitted set must be ENUMERATED in every artifact, not
        merely counted -- a count cannot tell a reader what stopped being
        measured."""
        r = _roster(tmp_path, _minimal())
        cov = census.class_field_coverage("C", ["A", "B", "C"], ["A"], roster=r)
        assert cov.as_dict()["engine_omitted"] == ["B", "C"]


# ===========================================================================
# The census walk
# ===========================================================================

class TestCensusFields:

    def test_records_only_compared_fields(self, tmp_path):
        r = _roster(tmp_path, _minimal(entries=[
            {"class": "LexEntry", "field": "DateCreated", "rationale": "FR-055"}]))

        def src(cls, guid):
            return (["DateCreated", "Form", "Hidden"],
                    {"DateCreated": "2020-01-01", "Form": "abc"})

        c = census.census_fields({"LexEntry": ["g1"]}, field_source=src, roster=r)
        assert c.values["LexEntry"]["g1"] == {"Form": "abc"}
        assert c.coverage["LexEntry"].engine_omitted == ("Hidden",)

    def test_carrier_b_tag_stripped_as_values_are_recorded(self, tmp_path):
        """FR-063: downstream comparison must never see the tool's own tag."""
        r = _roster(tmp_path, _minimal(tag_stripping={
            "carrier_b": {"fields": ["Description"], "line_marker": CONTRACT_TAG_MARKER}}))

        def src(cls, guid):
            return (["Description"],
                    {"Description": "prose\n%sGT|a|b|c" % CONTRACT_TAG_MARKER})

        c = census.census_fields({"Text": ["g1"]}, field_source=src, roster=r)
        assert c.values["Text"]["g1"]["Description"] == "prose"

    def test_inconsistent_syncable_surface_within_a_class_raises(self, tmp_path):
        """The syncable surface is a property of the CLASS. Two objects
        disagreeing means the omitted set is not well defined, so it must raise
        rather than average away the difference."""
        r = _roster(tmp_path, _minimal())
        surfaces = {"g1": {"A": 1}, "g2": {"A": 1, "B": 2}}

        def src(cls, guid):
            return (["A", "B"], surfaces[guid])

        with pytest.raises(census.CensusContractError, match="two different syncable"):
            census.census_fields({"C": ["g1", "g2"]}, field_source=src, roster=r)

    def test_non_mapping_props_raises(self, tmp_path):
        r = _roster(tmp_path, _minimal())
        with pytest.raises(census.CensusContractError, match="non-mapping"):
            census.census_fields({"C": ["g1"]},
                                 field_source=lambda c, g: (["A"], ["not", "a", "dict"]),
                                 roster=r)

    def test_class_with_no_objects_contributes_no_values(self, tmp_path):
        r = _roster(tmp_path, _minimal())

        def src(cls, guid):  # pragma: no cover -- must never be called
            raise AssertionError("field source called for an empty class")

        c = census.census_fields({"C": []}, field_source=src, roster=r)
        assert c.values == {} and c.coverage == {}


# ===========================================================================
# FR-052 / FR-066: growth of the omitted set is REDUCED COVERAGE
# ===========================================================================

class TestOmittedGrowth:

    def test_growth_is_reported_as_reduced_coverage(self):
        g = census.omitted_growth({"C": ["A"]}, {"C": ["A", "B"]})
        assert g["coverage_reduced"] is True
        assert g["grew"] == {"C": ["B"]}

    def test_no_change_is_not_reduced_coverage(self):
        g = census.omitted_growth({"C": ["A"]}, {"C": ["A"]})
        assert g["coverage_reduced"] is False and g["grew"] == {}

    def test_shrinkage_is_recorded_but_is_not_a_failure(self):
        """The engine started carrying something it used to skip. Not a failure,
        but recorded, so a reader need not diff two artifacts by hand."""
        g = census.omitted_growth({"C": ["A", "B"]}, {"C": ["A"]})
        assert g["coverage_reduced"] is False
        assert g["shrank"] == {"C": ["B"]}

    def test_newly_measured_class_is_not_growth(self):
        """A class never measured before has no baseline to regress against.
        Calling that reduced coverage would fire on every genuinely new class."""
        g = census.omitted_growth({}, {"C": ["A"]})
        assert g["coverage_reduced"] is False
        assert g["classes_new"] == ["C"]

    def test_class_that_vanished_is_reported_separately(self):
        g = census.omitted_growth({"C": ["A"]}, {})
        assert g["classes_absent_now"] == ["C"]
        assert g["coverage_reduced"] is False

    def test_growth_in_one_class_is_not_masked_by_shrinkage_in_another(self):
        g = census.omitted_growth({"A": ["x"], "B": ["y", "z"]},
                                  {"A": ["x", "w"], "B": ["y"]})
        assert g["coverage_reduced"] is True
        assert g["grew"] == {"A": ["w"]} and g["shrank"] == {"B": ["z"]}


# ===========================================================================
# Wave 2: not yet implemented, and this file says so out loud
# ===========================================================================

class TestWave2NotYetImplemented:
    """tasks.md T036 names FR-051..FR-092. Wave 1 delivered FR-051..FR-068.

    These assertions fail the moment a Wave-2 surface lands in ``compare.py``
    without its tests arriving in this file, so the gap cannot be forgotten. The
    task is not complete while any of them still pass.
    """

    WAVE_2_SURFACES = (
        ("classify_writing_system", "FR-069..FR-072", "T039"),
        ("classify_distortion", "FR-073..FR-078", "T040"),
        ("compare_order", "FR-079..FR-084", "T041"),
        ("classify_link", "FR-085..FR-090", "T042"),
        ("compare_structural_depth", "FR-189/SC-017", "T043"),
    )

    @pytest.mark.parametrize("name,frs,task", WAVE_2_SURFACES)
    def test_wave2_surface_absent_or_tested(self, name, frs, task):
        from debug.fullsweep import compare
        assert not hasattr(compare, name), (
            "compare.%s (%s) has landed via %s, so its classification tests are "
            "now REQUIRED in this file and this placeholder must be replaced"
            % (name, frs, task)
        )
