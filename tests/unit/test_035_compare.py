"""Feature 035 -- T036: the field-plane classification tests.

Source: spec.md Section E (FR-051..FR-092), contracts/rosters.md section 1,
contracts/expected-divergent.json.

NO FLEx project and NO LCM. ``census_fields`` takes an injected ``field_source``
exactly so this plane is testable offline; every fixture below is a plain dict.

SCOPE. Wave 1 (T037 census surface + T038 roster) covers FR-051..FR-068; wave 2
(T039-T043) covers FR-069..FR-092 plus FR-189/SC-017. Both are here:

  * FR-051..FR-068 -- the census surface, the EXPECTED_DIVERGENT roster's
    effective composition, tag-stripping, and the coverage-growth rule.
  * FR-069..FR-072 -- writing-system mapped legitimacy (T039).
  * FR-067, FR-073..FR-078 -- the distortion classes (T040).
  * FR-079..FR-084 -- order semantics (T041).
  * FR-085..FR-090 -- the five link verdicts (T042).
  * FR-189 / SC-017 -- structural depth and per-parent degree (T043).

FR-091/FR-092 are the object plane's composition rule and are asserted in
test_035_guards.py against ``reconcile_objects``, not here; ``TestPlaneSeparation``
below pins the FR-093 boundary between the two planes.

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
# WAVE 2 -- the five comparison rules (T039-T043)
# ===========================================================================

from debug.fullsweep import compare  # noqa: E402
from debug.fullsweep import identity as identity_mod  # noqa: E402

#: FR-161's residual list names "writing system absent in target" as a real
#: measured class, so these tests use tags seen live in batch 1.
LIVE_TAGS = ("eo", "fr", "mgz", "mgz-fonipa-x-etic", "swh")


class _FakeRoster:
    """Stands in for identity.NaturalKeyRoster: only ``admits`` is consulted."""

    def __init__(self, classes):
        self._classes = frozenset(classes)

    def admits(self, class_name):
        return class_name in self._classes


class _FakeRemap:
    def __init__(self, table):
        self._t = dict(table)

    def target_for(self, class_name, source_guid):
        return self._t.get((class_name, source_guid))


# ---------------------------------------------------------------------------
# T039 -- FR-069..FR-072
# ---------------------------------------------------------------------------

class TestWritingSystemMapping:

    def test_mapping_enumerates_every_source_writing_system(self):
        """FR-071: the narrower default this refuses is the
        single-default-vernacular map, which would make every other writing
        system's content invisible rather than compared."""
        m = compare.build_writing_system_mapping(LIVE_TAGS, ("eo", "fr"))
        assert set(m.mapped) == {"eo", "fr"}
        assert set(m.to_create) == {"mgz", "mgz-fonipa-x-etic", "swh"}
        # Every source tag is accounted for one way or the other.
        assert set(m.mapped) | set(m.to_create) == set(LIVE_TAGS)

    def test_empty_source_enumeration_is_a_measurement_defect(self):
        with pytest.raises(compare.FieldPlaneContractError, match="FR-071"):
            compare.build_writing_system_mapping([], ("eo",))

    def test_mapped_and_resolving_is_mapped(self):
        m = compare.build_writing_system_mapping(("eo",), ("eo",))
        assert compare.classify_writing_system(
            "eo", mapping=m, target_resolves=True, has_content=True
        ) == compare.WS_MAPPED

    def test_declared_but_not_resolving_is_LOST_not_expected_divergent(self):
        """FR-072: the mapping declared an intent to carry this content across
        and the intent was not honored. Classifying it EXPECTED_DIVERGENT would
        excuse the failure it is meant to surface."""
        m = compare.build_writing_system_mapping(("eo",), ("eo",))
        assert compare.classify_writing_system(
            "eo", mapping=m, target_resolves=False, has_content=True
        ) == compare.WS_LOST

    def test_to_create_is_also_declared_so_FR072_applies(self):
        """A writing system the run said it would CREATE is declared just as
        much as one it mapped, so a target that still does not have it is loss."""
        m = compare.build_writing_system_mapping(("mgz",), ("eo",))
        assert "mgz" in m.to_create
        assert compare.classify_writing_system(
            "mgz", mapping=m, target_resolves=False, has_content=True
        ) == compare.WS_LOST

    def test_unmapped_with_skip_record_is_out_of_scope_never_lost(self):
        """FR-070: MUST NEVER be classified LOST when a skip record exists."""
        m = compare.WritingSystemMapping(mapped={}, to_create=frozenset(),
                                         skip_records=frozenset({"fr"}))
        v = compare.classify_writing_system(
            "fr", mapping=m, target_resolves=False, has_content=True)
        assert v == compare.WS_OUT_OF_SCOPE
        assert v != compare.WS_LOST

    def test_unmapped_with_content_and_no_skip_record_is_its_own_process_defect(self):
        """FR-070: a process defect in the run's own mapping construction. It
        MUST NOT be folded into either LOST or EXPECTED_DIVERGENT -- both would
        blame the data for a harness bug."""
        m = compare.WritingSystemMapping(mapped={}, to_create=frozenset(),
                                         skip_records=frozenset())
        v = compare.classify_writing_system(
            "fr", mapping=m, target_resolves=False, has_content=True)
        assert v == compare.WS_PROCESS_DEFECT
        assert v not in (compare.WS_LOST, compare.WS_OUT_OF_SCOPE)

    def test_unmapped_without_content_is_out_of_scope(self):
        m = compare.WritingSystemMapping(mapped={}, to_create=frozenset(),
                                         skip_records=frozenset())
        assert compare.classify_writing_system(
            "fr", mapping=m, target_resolves=False, has_content=False
        ) == compare.WS_OUT_OF_SCOPE

    def test_untagged_alternative_refused(self):
        m = compare.build_writing_system_mapping(("eo",), ("eo",))
        with pytest.raises(compare.FieldPlaneContractError):
            compare.classify_writing_system("", mapping=m, target_resolves=True,
                                            has_content=True)

    def test_alternatives_compared_byte_identically_under_mapped_ws(self):
        """FR-069. Also: every source alternative yields a finding, including
        out-of-scope ones -- an alternative with no finding is indistinguishable
        from one that was never looked at."""
        m = compare.build_writing_system_mapping(("eo", "fr"), ("eo", "fr"))
        rows = compare.compare_ws_alternatives(
            {"eo": "saluto", "fr": "bonjour"},
            {"eo": "saluto", "fr": "Bonjour"}, mapping=m)
        assert len(rows) == 2
        by_ws = {r["writing_system"]: r for r in rows}
        assert by_ws["eo"]["verdict"] == compare.EQUAL
        assert by_ws["fr"]["verdict"] == compare.DISTORTED
        assert by_ws["fr"]["subtype"] == compare.SUB_CASING


# ---------------------------------------------------------------------------
# T040 -- FR-067, FR-073..FR-078
# ---------------------------------------------------------------------------

class TestDistortionClasses:

    def test_identical_text_is_equal(self):
        r = compare.classify_distortion("abc", "abc")
        assert r.verdict == compare.EQUAL and r.subtype == ""

    @pytest.mark.parametrize("src,tgt", [
        (" abc", "abc"), ("abc ", "abc"), ("abc", "  abc  "), ("\tabc", "abc"),
    ])
    def test_leading_or_trailing_whitespace_is_distorted(self, src, tgt):
        """FR-073: MUST NEVER be treated as benign -- such whitespace can be
        linguistically significant."""
        r = compare.classify_distortion(src, tgt)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_WHITESPACE

    @pytest.mark.parametrize("src,tgt", [
        ("abc", "Abc"), ("ABC", "abc"), ("Ekpe", "ekpe"),
    ])
    def test_casing_is_always_distorted_with_no_exception(self, src, tgt):
        """FR-074: no exception, because casing distinguishes lexical identity
        for the orthographies this tool's users work in."""
        r = compare.classify_distortion(src, tgt)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_CASING

    def test_normalization_difference_is_its_own_subtype_not_generic_content(self):
        """FR-076: tagged as its own distinct subtype so a reviewer can triage a
        large, probably-benign cluster separately from genuine content bugs --
        and NOT silently treated as equal."""
        nfc = "é"          # e-acute, composed
        nfd = "é"          # e + combining acute, decomposed
        assert nfc != nfd
        r = compare.classify_distortion(nfc, nfd)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_NORMALIZATION
        assert r.subtype != compare.SUB_CONTENT

    def test_normalization_check_does_not_mask_whitespace(self):
        r = compare.classify_distortion("é ", "é")
        assert r.subtype == compare.SUB_WHITESPACE

    def test_unrelated_content_is_generic_mismatch(self):
        r = compare.classify_distortion("cat", "dog")
        assert r.subtype == compare.SUB_CONTENT

    def test_run_structure_loss_with_matching_plain_text_is_distorted(self):
        """FR-075: the comparator MUST compare the field's internal run
        structure, not merely its plain text, or it will not detect this class
        of loss at all."""
        src = [("hello ", "en", "bold"), ("world", "eo", None)]
        tgt = [("hello world", "en", None)]
        r = compare.classify_distortion(src, tgt, kind=compare.KIND_RUNS)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_RUN_STRUCTURE

    def test_per_run_writing_system_loss_is_distorted(self):
        src = [("a", "eo", None)]
        tgt = [("a", "en", None)]
        r = compare.classify_distortion(src, tgt, kind=compare.KIND_RUNS)
        assert r.subtype == compare.SUB_RUN_STRUCTURE

    def test_identical_runs_are_equal(self):
        runs = [("a", "eo", "bold"), ("b", "fr", None)]
        r = compare.classify_distortion(runs, list(runs), kind=compare.KIND_RUNS)
        assert r.verdict == compare.EQUAL

    def test_run_text_difference_still_reports_the_text_subtype(self):
        src = [("Abc", "en", None)]
        tgt = [("abc", "en", None)]
        r = compare.classify_distortion(src, tgt, kind=compare.KIND_RUNS)
        assert r.subtype == compare.SUB_CASING

    def test_date_precision_collapse_is_distorted(self):
        """FR-077: precision is itself asserted data, not formatting."""
        r = compare.classify_distortion((1998, "exact"), (1998, "approximate"),
                                        kind=compare.KIND_DATE)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_DATE_PRECISION

    def test_same_date_and_precision_is_equal(self):
        r = compare.classify_distortion((1998, "exact"), (1998, "exact"),
                                        kind=compare.KIND_DATE)
        assert r.verdict == compare.EQUAL

    def test_enum_equal_decoded_value_with_different_raw_int_is_equal(self):
        """FR-078: DISTORTED only when the DECODED semantic value differs, never
        merely because the raw stored integer differs."""
        decode = {0: "leftToRight", 1: "rightToLeft", 7: "leftToRight"}.get
        r = compare.classify_distortion(0, 7, kind=compare.KIND_ENUM, decode=decode)
        assert r.verdict == compare.EQUAL

    def test_enum_different_decoded_value_is_distorted(self):
        decode = {0: "leftToRight", 1: "rightToLeft"}.get
        r = compare.classify_distortion(0, 1, kind=compare.KIND_ENUM, decode=decode)
        assert r.verdict == compare.DISTORTED
        assert r.subtype == compare.SUB_ENUM_DECODED

    def test_enum_without_decoder_refuses(self):
        """Comparing raw ordinals is exactly what FR-078 forbids."""
        with pytest.raises(compare.FieldPlaneContractError, match="FR-078"):
            compare.classify_distortion(0, 1, kind=compare.KIND_ENUM)

    def test_undecodable_ordinal_raises_rather_than_comparing_raw(self):
        with pytest.raises(compare.FieldPlaneContractError, match="FR-078"):
            compare.classify_distortion(0, 99, kind=compare.KIND_ENUM,
                                        decode={0: "a"}.get)

    def test_phonological_rule_direction_is_compared_by_decoded_value(self):
        """FR-067: the field is excluded from the merge-preview UI's diff pane
        and MUST STILL be fidelity-checked, decoded on both sides defensively
        against cross-version ordinal drift."""
        decode = {0: "leftToRight", 1: "rightToLeft", 2: "simultaneous"}.get
        assert compare.classify_distortion(
            0, 1, kind=compare.KIND_ENUM, decode=decode).subtype == (
            compare.SUB_ENUM_DECODED)

    def test_unresolvable_kind_raises_rather_than_bucketing_to_empty(self):
        """S-09: a category that quietly becomes '' is indistinguishable
        downstream from a clean result."""
        with pytest.raises(compare.FieldPlaneContractError, match="S-09"):
            compare.classify_distortion("a", "b", kind="whatever")

    def test_text_kind_refuses_non_text_rather_than_coercing(self):
        with pytest.raises(compare.FieldPlaneContractError, match="S-09"):
            compare.classify_distortion(1, 2, kind=compare.KIND_TEXT)

    def test_every_subtype_is_distinct(self):
        assert len(set(compare.DISTORTION_SUBTYPES)) == len(
            compare.DISTORTION_SUBTYPES)


# ---------------------------------------------------------------------------
# T041 -- FR-079..FR-084
# ---------------------------------------------------------------------------

class TestOrderSemantics:

    @pytest.mark.parametrize("cls,fld", compare.ORDER_CRITICAL_OWNED
                             + compare.ORDER_CRITICAL_REFERENCE)
    def test_named_order_critical_fields_are_ordered(self, cls, fld):
        """FR-082/FR-083: these MUST fail the comparison if their order is
        scrambled."""
        assert compare.order_significance(cls, fld) == compare.ORDER_ASSERTED

    def test_scrambled_order_critical_sequence_fails_despite_equal_membership(self):
        r = compare.compare_order("LexEntry", "SensesOS", ["a", "b", "c"],
                                  ["c", "b", "a"])
        assert r.passed is False
        assert "scrambled" in r.reason

    def test_ordered_sequence_in_order_passes(self):
        r = compare.compare_order("LexEntry", "SensesOS", ["a", "b"], ["a", "b"])
        assert r.passed is True

    def test_competing_analyses_are_unordered_by_design(self):
        """FR-081: re-ordering a wordform's competing analyses across a transfer
        MUST be treated as expected and benign, not as a defect."""
        assert compare.order_significance("WfiWordform", "AnalysesOC") == (
            compare.ORDER_NOT_ASSERTED)
        r = compare.compare_order("WfiWordform", "AnalysesOC", ["a", "b"],
                                  ["b", "a"])
        assert r.passed is True

    def test_unordered_collection_still_fails_on_missing_membership(self):
        """FR-080 exempts POSITION, not presence."""
        r = compare.compare_order("WfiWordform", "AnalysesOC", ["a", "b"], ["b"])
        assert r.passed is False
        assert r.missing == ("a",)

    def test_cross_entry_iteration_order_is_not_asserted_at_all(self):
        """FR-084: the host exposes entries through a surface with no
        author-assigned cross-entry order, so neither order nor membership is
        asserted here."""
        assert compare.order_significance("LexDb", "Entries") == (
            compare.ORDER_EXCLUDED)
        r = compare.compare_order("LexDb", "Entries", ["a", "b"], ["b"])
        assert r.passed is True

    def test_significance_derives_from_the_accessor_suffix_not_per_class(self):
        """FR-079: derived from the tool's own existing ordered/unordered
        classification -- the OS/RS vs OC/RC accessor convention -- and NOT
        re-derived per class. A class never named in any roster still resolves."""
        assert compare.order_significance("NeverHeardOf", "ThingsOS") == (
            compare.ORDER_ASSERTED)
        assert compare.order_significance("NeverHeardOf", "ThingsRS") == (
            compare.ORDER_ASSERTED)
        assert compare.order_significance("NeverHeardOf", "ThingsOC") == (
            compare.ORDER_NOT_ASSERTED)
        assert compare.order_significance("NeverHeardOf", "ThingsRC") == (
            compare.ORDER_NOT_ASSERTED)

    def test_unclassifiable_field_refuses_rather_than_guessing_unordered(self):
        """Guessing 'unordered' would silently stop asserting order, which is the
        failure mode FR-079 exists to prevent."""
        with pytest.raises(compare.FieldPlaneContractError, match="FR-079"):
            compare.order_significance("LexEntry", "SomeScalar")

    def test_extra_member_in_target_is_reported(self):
        r = compare.compare_order("LexEntry", "SensesOS", ["a"], ["a", "b"])
        assert r.passed is False and r.extra == ("b",)


# ---------------------------------------------------------------------------
# T042 -- FR-085..FR-090
# ---------------------------------------------------------------------------

class TestLinkClassification:

    def test_exactly_five_verdicts(self):
        assert len(compare.LINK_VERDICTS) == 5
        assert len(set(compare.LINK_VERDICTS)) == 5

    def test_equal_identifiers_resolve(self):
        r = compare.classify_link(class_name="LexSense", field_name="MSA",
                                  source_referent="g1", target_referent="g1")
        assert r.verdict == compare.LINK_RESOLVED

    def test_repointed_link_to_a_seed_entry_still_resolves(self):
        """FR-089: a catalog or seed entry that a freshly created target ships
        with, at a fixed well-known identifier equal to the source referent's,
        is RESOLVED -- not a special verdict. FR-085 forbids assuming the
        referent must be something THIS run created."""
        r = compare.classify_link(class_name="MoMorphType",
                                  field_name="MorphTypeRA",
                                  source_referent="seed-guid",
                                  target_referent="seed-guid")
        assert r.verdict == compare.LINK_RESOLVED

    def test_mismatched_identifier_is_dangling_and_is_a_hard_failure(self):
        r = compare.classify_link(class_name="LexSense", field_name="MSA",
                                  source_referent="g1", target_referent="g2")
        assert r.verdict == compare.LINK_DANGLING

    def test_null_target_with_source_referent_and_no_record_is_silently_unset(self):
        """FR-087: higher severity than an accounted-for gap."""
        r = compare.classify_link(class_name="LexSense", field_name="MSA",
                                  source_referent="g1", target_referent=None,
                                  has_accounting_record=False)
        assert r.verdict == compare.LINK_SILENTLY_UNSET

    def test_null_target_with_a_matching_record_is_the_milder_verdict(self):
        """FR-088: a distinct, MILDER verdict, never conflated with
        SILENTLY_UNSET or with a clean pass."""
        r = compare.classify_link(class_name="LexSense", field_name="MSA",
                                  source_referent="g1", target_referent=None,
                                  has_accounting_record=True)
        assert r.verdict == compare.LINK_LOST_BUT_ACCOUNTED
        assert r.verdict != compare.LINK_SILENTLY_UNSET
        assert r.verdict != compare.LINK_RESOLVED

    def test_null_on_both_sides_is_vacuously_resolved(self):
        r = compare.classify_link(class_name="LexSense", field_name="MSA",
                                  source_referent=None, target_referent=None)
        assert r.verdict == compare.LINK_RESOLVED

    def test_roster_class_resolves_through_the_remap_record(self):
        """FR-085 as amended: for a class on the natural-key identity roster the
        determination proceeds THROUGH the recorded identity-remap record and
        MUST NEVER be made by direct identifier comparison."""
        r = compare.classify_link(
            class_name="WfiWordform", field_name="AnalysesOC",
            source_referent="src-guid", target_referent="tgt-guid",
            natural_key_roster=_FakeRoster({"WfiWordform"}),
            remap_record=_FakeRemap({("WfiWordform", "src-guid"): "tgt-guid"}))
        assert r.verdict == compare.LINK_RESOLVED
        assert "identity-remap record" in r.basis

    def test_roster_class_identifier_mismatch_alone_is_not_dangling(self):
        """FR-086 as amended: DANGLING for such a class is reserved for a
        resolution matching NEITHER RESOLVED, RESOLVED-BY-EQUIVALENCE, nor the
        recorded remap record."""
        r = compare.classify_link(
            class_name="WfiWordform", field_name="AnalysesOC",
            source_referent="src", target_referent="mapped-to",
            natural_key_roster=_FakeRoster({"WfiWordform"}),
            remap_record=_FakeRemap({("WfiWordform", "src"): "mapped-to"}))
        assert r.verdict != compare.LINK_DANGLING

    def test_roster_class_matching_neither_is_dangling(self):
        r = compare.classify_link(
            class_name="WfiWordform", field_name="AnalysesOC",
            source_referent="src", target_referent="someone-else",
            natural_key_roster=_FakeRoster({"WfiWordform"}),
            remap_record=_FakeRemap({("WfiWordform", "src"): "expected"}))
        assert r.verdict == compare.LINK_DANGLING

    def test_roster_class_identity_still_authoritative(self):
        """FR-186: identity is authoritative and the natural key is the fallback,
        never the reverse -- so an identifier match still resolves."""
        r = compare.classify_link(
            class_name="WfiWordform", field_name="AnalysesOC",
            source_referent="same", target_referent="same",
            natural_key_roster=_FakeRoster({"WfiWordform"}),
            remap_record=_FakeRemap({}))
        assert r.verdict == compare.LINK_RESOLVED

    def test_roster_class_without_a_remap_record_refuses_to_fall_back(self):
        """Falling back to identifier comparison for a roster class is
        explicitly forbidden, so the absence of the record must raise rather
        than silently take the ordinary path."""
        with pytest.raises(compare.FieldPlaneContractError, match="FR-085"):
            compare.classify_link(
                class_name="WfiWordform", field_name="AnalysesOC",
                source_referent="a", target_referent="b",
                natural_key_roster=_FakeRoster({"WfiWordform"}),
                remap_record=None)

    def test_resolved_by_equivalence_only_for_a_class_with_no_stable_id(self):
        """FR-090: admissible ONLY for a class carrying no stable per-instance
        identifier, using the same owner-and-name equivalence the engine's own
        de-duplication already uses."""
        cls = sorted(compare.NO_STABLE_IDENTIFIER_CLASSES)[0]
        r = compare.classify_link(class_name=cls, field_name="Owner",
                                  source_referent="a", target_referent="b",
                                  equivalence_match=True)
        assert r.verdict == compare.LINK_RESOLVED_BY_EQUIVALENCE

    def test_equivalence_firing_off_roster_is_a_harness_error_naming_the_class(self):
        """FR-090: MUST NOT be used as a fallback for any class that normally
        carries a stable identifier; if it fires, fail and NAME the class."""
        with pytest.raises(compare.FieldPlaneContractError) as exc:
            compare.classify_link(class_name="LexEntry", field_name="MSA",
                                  source_referent="a", target_referent="b",
                                  equivalence_match=True)
        assert "LexEntry" in str(exc.value)
        assert "FR-090" in str(exc.value)

    def test_equivalence_basis_is_not_the_natural_key_basis(self):
        """FR-090's last sentence: this basis is distinct from FR-185's and MUST
        NOT be conflated with or used to widen it. A class on the natural-key
        roster must NOT thereby become eligible for RESOLVED-BY-EQUIVALENCE."""
        with pytest.raises(compare.FieldPlaneContractError, match="FR-090"):
            compare.classify_link(
                class_name="WfiWordform", field_name="X",
                source_referent="a", target_referent="b",
                natural_key_roster=_FakeRoster(set()),
                equivalence_match=True)

    def test_the_real_roster_admits_only_its_enumerated_classes(self):
        """Wire the shipped roster in, not just the fake, so the admission
        surface this rule depends on is exercised as delivered."""
        roster = identity_mod.NaturalKeyRoster.load()
        assert roster.classes
        assert not roster.admits("LexEntry")


# ---------------------------------------------------------------------------
# T043 -- FR-189 / SC-017
# ---------------------------------------------------------------------------

class TestStructuralDepth:

    def test_depth_is_measured_recursively_not_to_a_fixed_depth(self):
        """FR-189: enumerate children recursively at every node until no further
        children exist there. A five-deep chain must measure 5, not a capped 2
        or 3."""
        kids = {"a": ["b"], "b": ["c"], "c": ["d"], "d": ["e"]}
        assert compare.measure_max_depth(kids, ["a"]) == 5

    def test_flat_roots_are_depth_one_and_no_roots_is_zero(self):
        assert compare.measure_max_depth({}, ["a", "b"]) == 1
        assert compare.measure_max_depth({}, []) == 0

    def test_deepest_branch_wins(self):
        kids = {"a": ["b", "c"], "c": ["d"]}
        assert compare.measure_max_depth(kids, ["a"]) == 3

    def test_ownership_cycle_raises_rather_than_truncating_the_walk(self):
        """Truncating would report a shallower depth than the data has -- the
        exact self-hiding failure FR-189 exists to catch."""
        with pytest.raises(compare.FieldPlaneContractError, match="FR-189"):
            compare.measure_max_depth({"a": ["b"], "b": ["a"]}, ["a"])

    def test_shallower_target_depth_is_vacuous_for_that_class(self):
        """FR-189: a class whose recorded target-side maximum depth is lower
        than its source-side maximum MUST be a VACUOUS result -- because every
        object the walk did visit compared perfectly."""
        r = compare.compare_structural_depth(
            "LexSense",
            source_children={"a": ["b"], "b": ["c"]}, source_roots=["a"],
            target_children={"a": ["b"]}, target_roots=["a"])
        assert r.verdict == "VACUOUS"
        assert r.clean is False
        assert r.source_max_depth == 3 and r.target_max_depth == 2

    def test_per_parent_degree_mismatch_fails_even_when_children_compare_clean(self):
        """FR-189: a per-parent child-count disagreement MUST fail the run even
        when every child actually visited compared clean."""
        r = compare.compare_structural_depth(
            "LexSense",
            source_children={"a": ["b", "x"], "b": ["c"]}, source_roots=["a"],
            target_children={"a": ["b"], "b": ["c"]}, target_roots=["a"])
        assert r.verdict == compare.DISTORTED
        assert r.clean is False
        assert r.degree_mismatches == (("a", 2, 1),)

    def test_matching_depth_and_degree_is_clean(self):
        tree = {"a": ["b"], "b": ["c"]}
        r = compare.compare_structural_depth(
            "LexSense", source_children=tree, source_roots=["a"],
            target_children=dict(tree), target_roots=["a"])
        assert r.verdict == compare.EQUAL and r.clean is True

    def test_class_with_no_nesting_in_the_corpus_is_not_evaluated_never_clean(self):
        """FR-189's closing clause: where no available project exhibits
        same-class nesting deeper than one level, that class's depth behavior
        MUST be reported NOT-EVALUATED rather than clean."""
        r = compare.compare_structural_depth(
            "CmPossibility", source_children={}, source_roots=["a"],
            target_children={}, target_roots=["a"])
        assert r.verdict == compare.DEPTH_NOT_EVALUATED
        assert r.evaluated is False
        assert r.clean is False

    def test_explicit_corpus_absence_flag_forces_not_evaluated(self):
        r = compare.compare_structural_depth(
            "LexSense", source_children={"a": ["b"], "b": ["c"]},
            source_roots=["a"], target_children={"a": ["b"], "b": ["c"]},
            target_roots=["a"], nesting_available_in_corpus=False)
        assert r.verdict == compare.DEPTH_NOT_EVALUATED
        assert r.clean is False

    def test_artifact_block_records_both_sides_depth_and_degree(self):
        """SC-017: every artifact carries a recorded per-side maximum depth AND
        per-parent child-count comparison outcomes."""
        r = compare.compare_structural_depth(
            "LexSense", source_children={"a": ["b", "x"], "b": ["c"]},
            source_roots=["a"], target_children={"a": ["b"], "b": ["c"]},
            target_roots=["a"])
        d = r.as_dict()
        assert d["source_max_depth"] == 3 and d["target_max_depth"] == 3
        assert d["degree_mismatches"] == [
            {"parent": "a", "source_children": 2, "target_children": 1}]
        assert d["class"] == "LexSense"

    def test_same_class_nesting_roster_names_the_documented_cases(self):
        """FR-189 names sub-senses, reversal sub-entries, and possibility
        sub-items explicitly."""
        for cls in ("LexSense", "ReversalIndexEntry", "CmPossibility"):
            assert cls in compare.SAME_CLASS_NESTING_CLASSES


# ---------------------------------------------------------------------------
# FR-093 -- the two planes stay structurally separate
# ---------------------------------------------------------------------------

class TestPlaneSeparation:

    def test_field_plane_keys_are_refused_in_an_object_plane_block(self):
        with pytest.raises(Exception, match="FR-093"):
            compare.assert_object_plane_only({"findings": []})

    def test_a_clean_object_plane_block_passes(self):
        compare.assert_object_plane_only({"transferred_equal_payload": []})
