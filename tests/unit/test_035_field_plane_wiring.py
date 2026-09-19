"""T045a(c) -- plane 2 is wired: the value-shape dispatcher, the payload
comparator ``reconcile_objects`` calls, and the measurements it deposits.

Feature 035, Phase 5 / US2 wave 3b.

WHAT THESE TESTS DEFEND. Before this task the sweep computed plane 2's rules
(T039-T043), built their artifact home (T045f), built the live field reader
(T045d) and the class -> category join (T045e), and then called NONE of them:
``run_one_project`` passed ``payload_never_compared`` to the reconciliation,
so every matched object was reported "present-under-matching-identity-but-
never-compared" and both ``comparisons`` and ``measured_categories`` stayed
``None``. Two guards could therefore only ever answer ``not-evaluated``.

The tests are organised around the three things that are easy to get subtly
wrong here, and silent when they are:

1. **The rule is chosen from the value's measured shape.** A dict is only a
   multistring when its keys name writing systems OF ITS OWN PROJECT, and a
   handle-keyed multistring must be normalized to language tags before any
   cross-project comparison -- handles are per-project.
2. **A comparison that could not be made is never a pass.** An undeclared
   integer (FR-078), an unresolvable handle (FR-068) and a roster class with
   no remap record (FR-085) are each REFUSED, counted, and given a reason.
3. **The counters reach the guards.** The class plane and the category plane
   are both written from one measurement, and the two guards that were stuck
   on ``not-evaluated`` answer pass/fail when fed it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "debug", _REPO / "src", _REPO / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fullsweep import artifact as A                    # noqa: E402
from fullsweep import compare                          # noqa: E402
from fullsweep import coverage as C                    # noqa: E402
from fullsweep import fieldplane as FP                 # noqa: E402
from fullsweep import guards                           # noqa: E402
from fullsweep.census import FieldCensus, load_expected_divergent  # noqa: E402
from fullsweep.moves import HarnessError               # noqa: E402

GUID_A = "0889c48c-716a-4533-87dd-1a9d17868cd6"
GUID_B = "26813520-5cb6-4b1c-bef0-a33195ac1586"
GUID_C = "4f7a69a7-67fc-4b63-a85a-828ca8835bd2"

#: The two projects' writing-system keys, as measured live on 2026-09-19:
#: tags plus the handle strings that ``PossibilityItemOperations`` emits.
SRC_WS_KEYS = frozenset({"en", "etu", "999000001", "999000003"})
TGT_WS_KEYS = frozenset({"en", "etu", "999000002", "999000007"})
SRC_HANDLES = {"999000001": "en", "999000003": "etu"}
#: DELIBERATELY different numbers for the same tags. A handle is per-project;
#: full_run.py records the measured case of 999000002 being `en` in one
#: project and `ngq` in another.
TGT_HANDLES = {"999000002": "en", "999000007": "etu"}


def _divergent_roster():
    """The TRACKED roster, not a hand-built one: the census applies its
    Carrier-B tag stripping from it, and a stub roster would test a
    comparison the sweep never makes."""
    return load_expected_divergent(
        _REPO / "specs" / "035-fullsweep-fidelity" / "contracts"
        / "expected-divergent.json")


def _ws_mapping(skip=()):
    return compare.build_writing_system_mapping(
        ["en", "etu"], ["en", "etu"], skip_records=skip)


def _compare(cls, field, src, tgt, **kw):
    kw.setdefault("ws_mapping", _ws_mapping())
    kw.setdefault("source_ws_keys", SRC_WS_KEYS)
    kw.setdefault("target_ws_keys", TGT_WS_KEYS)
    kw.setdefault("source_handle_to_tag", SRC_HANDLES)
    kw.setdefault("target_handle_to_tag", TGT_HANDLES)
    kw.setdefault("target_ws_tags", ("en", "etu"))
    return FP.compare_field(cls, field, src, tgt, **kw)


# ===========================================================================
# 1. THE VALUE-SHAPE VOCABULARY, against the shapes measured live
# ===========================================================================

@pytest.mark.parametrize("value,expected", [
    (None, FP.KIND_NULL),
    (False, FP.KIND_SCALAR),
    (0, FP.KIND_SCALAR),
    ("Ejagham", FP.KIND_TEXT_VALUE),
    (GUID_A, FP.KIND_REFERENCE),
    ({"en": "Event"}, FP.KIND_MULTISTRING),
    ({"999000001": "Event"}, FP.KIND_MULTISTRING),
    ({}, FP.KIND_MULTISTRING),
    ({"TypeGuid": GUID_A, "specs": []}, FP.KIND_STRUCTURE),
    ([GUID_A, GUID_B], FP.KIND_REFERENCE_SEQUENCE),
    ([], FP.KIND_REFERENCE_SEQUENCE),
    (frozenset(), FP.KIND_SCALAR_SET),
    ([{"Translation": {"en": "x"}}], FP.KIND_STRUCTURE_SEQUENCE),
    (object(), FP.KIND_UNKNOWN),
])
def test_every_live_measured_shape_has_a_kind(value, expected):
    """The shapes are not hypothetical: each row was observed coming out of
    ``GetSyncableProperties`` on ``Ejagham Mini`` (read-only, 2026-09-19)."""
    assert FP.classify_value_kind(value, ws_keys=SRC_WS_KEYS) == expected


def test_a_structured_dict_is_not_mistaken_for_a_multistring():
    """``MoStemMsa.MsFeatures`` is ``{'TypeGuid': ..., 'specs': [...]}``.
    Classifying it as a multistring would compare a feature structure as if
    ``specs`` were a language tag."""
    value = {"TypeGuid": GUID_A, "specs": [{"Name": {"en": "1"}}]}
    assert FP.classify_value_kind(value, ws_keys=SRC_WS_KEYS) == FP.KIND_STRUCTURE
    result = _compare("MoStemMsa", "MsFeatures", value, value)
    assert result.rule == FP.RULE_STRUCTURE
    assert result.verdict == compare.EQUAL


def test_kind_vocabulary_is_closed_and_all_reachable():
    assert len(set(FP.VALUE_KINDS)) == len(FP.VALUE_KINDS)
    assert len(set(FP.RULES)) == len(FP.RULES)


# ===========================================================================
# 2. WRITING SYSTEMS: handles are per-project, and never compared as-is
# ===========================================================================

def test_handle_keyed_multistrings_are_compared_by_TAG_not_by_handle():
    """The same content under the same TAG, stored under DIFFERENT handles in
    the two projects, is equal. Comparing the raw dicts would report a total
    loss of both alternatives and a fabricated pair of extras."""
    src = {"999000001": "Event", "999000003": "Njangi"}
    tgt = {"999000002": "Event", "999000007": "Njangi"}
    result = _compare("CmPossibility", "Name", src, tgt)
    assert result.rule == FP.RULE_WS
    assert result.verdict == compare.EQUAL, result.detail


def test_same_handle_number_meaning_different_tags_is_not_a_match():
    """999000001 is ``en`` in the source. If the target's 999000001 were
    ``etu``, a handle-keyed comparison would call two different writing
    systems equal."""
    src = {"999000001": "Event"}
    tgt = {"999000001": "Event"}
    result = _compare("CmPossibility", "Name", src, tgt,
                      target_ws_keys=frozenset({"en", "etu", "999000001"}),
                      target_handle_to_tag={"999000001": "etu"})
    assert result.verdict == compare.DISTORTED
    rows = {r["writing_system"]: r for r in result.detail["alternatives"]}
    assert rows["en"]["verdict"] == compare.DISTORTED


def test_an_unresolvable_handle_refuses_the_comparison_with_a_reason():
    result = _compare("CmPossibility", "Name", {"999000099": "Event"}, {"en": "Event"})
    assert result.performed is False
    assert result.verdict == ""
    assert "FR-068" in result.reason
    assert result.detail["source_unresolved_handles"] == ["999000099"]


def test_a_mapped_alternative_that_lost_its_text_is_a_finding():
    result = _compare("PartOfSpeech", "Name", {"en": "Noun"}, {"en": "noun"})
    assert result.verdict == compare.DISTORTED
    assert result.subtype == compare.SUB_CASING


def test_an_undeclared_writing_system_with_content_is_a_process_defect():
    """FR-070: under a default-vernacular mapping, an analysis alternative the
    run never declared and never skipped is a defect in the RUN's own mapping
    construction -- not expected divergence, and not ordinary loss."""
    narrow = FP.build_ws_mapping_for_mode(
        FP.WS_MODE_DEFAULT_VERNACULAR, source_tags=("etu", "en"),
        target_tags=("etu", "en"), source_default_vernacular="etu",
        target_default_vernacular="etu")
    result = _compare("PartOfSpeech", "Name", {"en": "Noun"}, {"en": "Noun"},
                      ws_mapping=narrow)
    assert result.verdict == compare.DISTORTED
    assert result.subtype == compare.WS_PROCESS_DEFECT


def test_the_same_alternative_is_clean_under_the_full_mapping():
    """And the point of recording the mode on the artifact: the SAME data is
    a process defect under one mapping and clean under the other, so a
    comparison is only interpretable against the mapping it was made under."""
    full = FP.build_ws_mapping_for_mode(
        FP.WS_MODE_FULL, source_tags=("etu", "en"), target_tags=("etu", "en"))
    result = _compare("PartOfSpeech", "Name", {"en": "Noun"}, {"en": "Noun"},
                      ws_mapping=full)
    assert result.verdict == compare.EQUAL


def test_a_skipped_writing_system_is_out_of_scope_not_loss():
    narrow = FP.build_ws_mapping_for_mode(
        FP.WS_MODE_DEFAULT_VERNACULAR, source_tags=("etu", "en"),
        target_tags=("etu", "en"), source_default_vernacular="etu",
        target_default_vernacular="etu", skip_records=("en",))
    result = _compare("PartOfSpeech", "Name", {"en": "Noun"}, {}, ws_mapping=narrow)
    assert result.verdict == compare.EQUAL


def test_default_vernacular_mode_refuses_to_build_without_both_defaults():
    with pytest.raises(HarnessError) as exc:
        FP.build_ws_mapping_for_mode(
            FP.WS_MODE_DEFAULT_VERNACULAR, source_tags=("etu",),
            target_tags=("etu",), source_default_vernacular="",
            target_default_vernacular="etu")
    assert "FR-071" in str(exc.value)


def test_an_unknown_mapping_mode_raises_rather_than_defaulting():
    with pytest.raises(HarnessError):
        FP.build_ws_mapping_for_mode("whatever-mode", source_tags=("etu",),
                                     target_tags=("etu",))


# ===========================================================================
# 3. WHAT IS REFUSED RATHER THAN GUESSED
# ===========================================================================

def test_an_undeclared_integer_is_refused_not_compared():
    """FR-078: the stored ordinal may be renumbered by the host. Comparing it
    as a number is the exact thing that rule forbids."""
    result = _compare("LexEntryRef", "RefType", 0, 0)
    assert result.performed is False
    assert "FR-078" in result.reason


def test_a_declared_numeric_integer_is_compared():
    equal = _compare("LexEntry", "HomographNumber", 2, 2)
    differs = _compare("LexEntry", "HomographNumber", 2, 3)
    assert equal.performed and equal.verdict == compare.EQUAL
    assert differs.verdict == compare.DISTORTED


def test_a_boolean_is_compared_without_a_decoder():
    """A boolean has no ordinal to drift: True is True in every host version."""
    assert _compare("MoStemAllomorph", "IsAbstract", True, True).verdict == compare.EQUAL
    assert _compare("MoStemAllomorph", "IsAbstract", True, False).verdict == compare.DISTORTED


def test_a_roster_class_link_without_a_remap_record_is_refused():
    class _Roster:
        def admits(self, cls):
            return cls == "WfiWordform"

    result = _compare("WfiWordform", "CategoryRA", GUID_A, GUID_B,
                      natural_key_roster=_Roster(), remap_record=None)
    assert result.performed is False
    assert "FR-085" in result.reason


def test_an_unknown_shape_is_a_finding_never_a_pass():
    sentinel = object()
    result = _compare("LexEntry", "Mystery", sentinel, sentinel)
    assert result.rule == FP.RULE_UNCLASSIFIED
    assert result.verdict == FP.VERDICT_UNCLASSIFIED
    assert result.is_finding is True


# ===========================================================================
# 4. LINKS, ORDER AND STRUCTURE
# ===========================================================================

def test_a_matching_referent_resolves():
    result = _compare("LexSense", "MorphoSyntaxAnalysisRA", GUID_A, GUID_A)
    assert result.rule == FP.RULE_LINK
    assert result.verdict == compare.LINK_RESOLVED
    assert result.is_finding is False


def test_a_different_referent_dangles():
    result = _compare("LexSense", "MorphoSyntaxAnalysisRA", GUID_A, GUID_B)
    assert result.verdict == compare.LINK_DANGLING
    assert result.is_finding is True


def test_a_null_target_with_a_record_is_milder_than_one_without():
    with_record = _compare("LexSense", "SenseTypeRA", GUID_A, None,
                           has_accounting_record=True)
    without = _compare("LexSense", "SenseTypeRA", GUID_A, None,
                       has_accounting_record=False)
    assert with_record.verdict == compare.LINK_LOST_BUT_ACCOUNTED
    assert without.verdict == compare.LINK_SILENTLY_UNSET


def test_both_sides_null_is_equal_not_a_finding():
    result = _compare("LexSense", "SenseTypeRA", None, None)
    assert result.is_finding is False


def test_a_target_only_value_is_recorded_but_is_not_loss():
    result = _compare("LexSense", "Source", None, "added in target")
    assert result.verdict == FP.VERDICT_TARGET_ONLY
    assert result.is_finding is False


def test_a_shape_mismatch_is_always_a_finding():
    result = _compare("LexSense", "Gloss", {"en": "dog"}, GUID_A)
    assert result.verdict == FP.VERDICT_SHAPE_MISMATCH
    assert result.is_finding is True


def test_an_empty_container_is_not_reported_as_a_shape_mismatch():
    """An empty dict cannot tell a multistring from a structure; calling that
    a difference would report something the data does not contain."""
    result = _compare("MoStemMsa", "MsFeatures", {}, {"TypeGuid": GUID_A})
    assert result.rule == FP.RULE_STRUCTURE
    assert result.verdict in (compare.DISTORTED, FP.VERDICT_TARGET_ONLY)


def test_a_reference_sequence_losing_a_member_fails():
    """``LexEntry.SensesOS`` is suffix-classified, so the order rule can run."""
    result = _compare("LexEntry", "SensesOS", [GUID_A, GUID_B], [GUID_A])
    assert result.rule == FP.RULE_ORDER
    assert result.verdict == compare.DISTORTED
    assert result.detail["missing"] == [GUID_B]


def test_a_field_whose_order_significance_is_undetermined_is_refused():
    """MEASURED: flexicon's syncable surface renames ``SegmentsRC`` to
    ``PhonemeGuids``, which no suffix rule can read, and
    ``compare.order_significance`` refuses to guess rather than silently stop
    asserting order (FR-079). That refusal must cost the FIELD, not the run."""
    result = _compare("PhNCSegments", "PhonemeGuids", [GUID_A, GUID_B], [GUID_A])
    assert result.performed is False
    assert result.rule == FP.RULE_UNCLASSIFIED
    assert "FR-079" in result.reason


def test_a_refused_rule_does_not_stop_the_object_being_measured():
    comp = _comparator(
        {"PhNCSegments": {GUID_A: {"PhonemeGuids": [GUID_B],
                                   "Name": {"en": "Vowels"}}}},
        {"PhNCSegments": {GUID_A: {"PhonemeGuids": [],
                                   "Name": {"en": "Vowels"}}}},
    )
    assert comp.payload_equal("PhNCSegments", GUID_A, GUID_A) is True
    counters = comp.comparisons_block()["per_class"]["PhNCSegments"]
    assert counters["comparisons_performed"] == 1   # Name
    assert counters["comparisons_refused"] == 1     # PhonemeGuids


def test_a_set_valued_field_is_compared_on_membership_only():
    """A Python ``frozenset`` carries no order, so asserting order over it
    would assert something the measurement cannot see (FR-080/FR-081)."""
    result = _compare("LexEntry", "DoNotPublishInRC",
                      frozenset({GUID_A, GUID_B}), frozenset({GUID_B, GUID_A}))
    assert result.verdict == compare.EQUAL
    assert result.detail["significance"] == compare.ORDER_NOT_ASSERTED


def test_identity_bearing_structure_rows_survive_reordering():
    src = [{"Guid": GUID_A, "Name": {"en": "1"}}, {"Guid": GUID_B, "Name": {"en": "2"}}]
    tgt = list(reversed(src))
    result = _compare("FsClosedFeature", "Values", src, tgt)
    assert result.verdict == compare.EQUAL
    assert result.detail["rows_compared"] == 2


def test_a_missing_structure_row_is_named():
    src = [{"Guid": GUID_A, "Name": {"en": "1"}}, {"Guid": GUID_B, "Name": {"en": "2"}}]
    result = _compare("FsClosedFeature", "Values", src, src[:1])
    assert result.verdict == compare.DISTORTED
    assert result.detail["missing_rows"] == [GUID_B]


def test_a_handle_nested_inside_a_structure_is_normalized_too():
    src = [{"Guid": GUID_A, "Name": {"999000001": "1"}}]
    tgt = [{"Guid": GUID_A, "Name": {"999000002": "1"}}]
    assert _compare("FsClosedFeature", "Values", src, tgt).verdict == compare.EQUAL


# ===========================================================================
# 5. THE COMPARATOR'S THREE-VALUED CONTRACT
# ===========================================================================

def _census(values):
    coverage = {cls: None for cls in values}
    return FieldCensus(values=values, coverage=coverage)


def _comparator(source_values, target_values, **kw):
    kw.setdefault("ws_mapping", _ws_mapping())
    kw.setdefault("source_ws_keys", SRC_WS_KEYS)
    kw.setdefault("target_ws_keys", TGT_WS_KEYS)
    kw.setdefault("source_handle_to_tag", SRC_HANDLES)
    kw.setdefault("target_handle_to_tag", TGT_HANDLES)
    kw.setdefault("target_ws_tags", ("en", "etu"))
    return FP.FieldPlaneComparator(
        source_census=_census(source_values),
        target_census=_census(target_values), **kw)


def test_a_pair_with_no_census_on_one_side_returns_None():
    """FR-097 turns None into "present-under-matching-identity-but-never-
    compared", which FAILS. That is the correct answer for an object nobody
    read -- and the reason the ten classes whose flexicon accessor raises are
    not quietly passed."""
    comp = _comparator({"LexEntry": {GUID_A: {"ImportResidue": "x"}}}, {})
    assert comp.payload_equal("LexEntry", GUID_A, GUID_A) is None
    assert comp.comparisons_block()["per_class"]["LexEntry"]["objects_not_read"] == 1


def test_an_object_whose_every_field_was_refused_returns_None():
    """Refusals are not comparisons. Returning True here would report an
    object as verified on the strength of zero measurements."""
    comp = _comparator({"LexEntryRef": {GUID_A: {"RefType": 0}}},
                       {"LexEntryRef": {GUID_A: {"RefType": 0}}})
    assert comp.payload_equal("LexEntryRef", GUID_A, GUID_A) is None
    counters = comp.comparisons_block()["per_class"]["LexEntryRef"]
    assert counters["comparisons_performed"] == 0
    assert counters["comparisons_refused"] == 1
    assert any("FR-078" in r for r in counters["refusal_reasons"])


def test_a_clean_object_returns_True_and_a_diverged_one_False():
    comp = _comparator(
        {"LexSense": {GUID_A: {"Gloss": {"en": "dog"}},
                      GUID_B: {"Gloss": {"en": "cat"}}}},
        {"LexSense": {GUID_A: {"Gloss": {"en": "dog"}},
                      GUID_B: {"Gloss": {"en": "Cat"}}}},
    )
    assert comp.payload_equal("LexSense", GUID_A, GUID_A) is True
    assert comp.payload_equal("LexSense", GUID_B, GUID_B) is False
    counters = comp.comparisons_block()["per_class"]["LexSense"]
    assert counters["objects_compared"] == 2
    assert counters["objects_with_findings"] == 1
    assert counters["findings"] == 1


def test_every_classified_link_is_recorded_not_only_the_failing_ones():
    """"No dangling links" over an unknown denominator is not evidence."""
    comp = _comparator(
        {"LexSense": {GUID_A: {"MorphoSyntaxAnalysisRA": GUID_C}}},
        {"LexSense": {GUID_A: {"MorphoSyntaxAnalysisRA": GUID_C}}},
    )
    comp.payload_equal("LexSense", GUID_A, GUID_A)
    assert [r["verdict"] for r in comp.link_findings()] == [compare.LINK_RESOLVED]


def test_the_drop_channel_is_consulted_for_a_null_referent():
    drop = compare.DropRecord(owner=GUID_A, field_name="SenseTypeRA",
                              item=GUID_C, reason="engine skip")
    comp = _comparator(
        {"LexSense": {GUID_A: {"SenseTypeRA": GUID_C}}},
        {"LexSense": {GUID_A: {"SenseTypeRA": None}}},
        drops=(drop,),
    )
    comp.payload_equal("LexSense", GUID_A, GUID_A)
    assert [r["verdict"] for r in comp.link_findings()] == [
        compare.LINK_LOST_BUT_ACCOUNTED]


def test_value_findings_carry_the_artifact_finding_shape():
    comp = _comparator(
        {"LexSense": {GUID_A: {"Gloss": {"en": "dog"}}}},
        {"LexSense": {GUID_A: {"Gloss": {"en": "Dog"}}}},
        category_for=lambda cls: ("senses",),
    )
    comp.payload_equal("LexSense", GUID_A, GUID_A)
    row = comp.value_findings()[0]
    for key in ("phase", "class", "category", "field", "source_value",
                "target_value", "verdict", "kind", "guid"):
        assert key in row
    assert row["category"] == "senses"
    assert row["guid"] == GUID_A


def test_the_block_separates_class_names_from_meta_keys():
    comp = _comparator({"LexSense": {GUID_A: {"Gloss": {"en": "d"}}}},
                       {"LexSense": {GUID_A: {"Gloss": {"en": "d"}}}})
    comp.payload_equal("LexSense", GUID_A, GUID_A)
    block = comp.comparisons_block()
    assert set(block["per_class"]) == {"LexSense"}
    assert block["totals"]["comparisons_performed"] == 1
    assert block["totals"]["pairs_seen"] == 1


def test_the_block_survives_the_artifact_serializability_check():
    comp = _comparator({"LexSense": {GUID_A: {"Gloss": {"en": "d"},
                                              "DoNotPublishInRC": frozenset({GUID_B})}}},
                       {"LexSense": {GUID_A: {"Gloss": {"en": "d"},
                                              "DoNotPublishInRC": frozenset({GUID_B})}}})
    comp.payload_equal("LexSense", GUID_A, GUID_A)
    A.assert_artifact_json_serializable("comparisons", comp.comparisons_block())
    A.assert_artifact_json_serializable("findings", comp.value_findings())


# ===========================================================================
# 6. THE COUNTERS REACH THE GUARDS (the point of the whole task)
# ===========================================================================

def _class_category_map():
    return C.load_class_category_map(
        _REPO / "specs" / "035-fullsweep-fidelity" / "contracts"
        / C.CLASS_CATEGORY_MAP_NAME)


def test_comparisons_performed_answers_instead_of_not_evaluated():
    """Fed the projection, ``COMPARISONS-PERFORMED`` returns pass or fail --
    the thing it could not do before this wiring existed."""
    cmap = _class_category_map()
    comp = _comparator(
        {"PartOfSpeech": {GUID_A: {"Name": {"en": "Noun"}}}},
        {"PartOfSpeech": {GUID_A: {"Name": {"en": "Noun"}}}},
        class_category_map=cmap,
    )
    comp.payload_equal("PartOfSpeech", GUID_A, GUID_A)
    performed, objects = comp.class_counters()
    projection = C.project_comparisons_to_categories(
        cmap, source_objects={"PartOfSpeech": 1},
        comparisons_performed=performed, objects_compared=objects)
    ctx = guards.RunContext(project="p", comparisons=projection["comparisons"])
    result = guards.guard_comparisons_performed(ctx)
    assert result.result == "pass", result.message


def test_a_class_with_source_objects_and_no_comparisons_fails_that_guard():
    cmap = _class_category_map()
    projection = C.project_comparisons_to_categories(
        cmap, source_objects={"PartOfSpeech": 5},
        comparisons_performed={"PartOfSpeech": 0},
        objects_compared={"PartOfSpeech": 0})
    ctx = guards.RunContext(project="p", comparisons=projection["comparisons"])
    assert guards.guard_comparisons_performed(ctx).result == "fail"


def test_an_absent_measurement_still_reports_not_evaluated():
    """The invariant this feature is built on: absent input is never a pass,
    and this wiring must not have turned it into an empty container."""
    ctx = guards.RunContext(project="p")
    assert guards.guard_comparisons_performed(ctx).result == "not-evaluated"
    assert guards.guard_category_coverage(ctx).result == "not-evaluated"


# ===========================================================================
# 7. DEPTH: three dispositions, kept apart
# ===========================================================================

def _side(nesting, **kw):
    side = FP.FieldPlaneSide(project=kw.pop("project", "p"), nesting=nesting)
    for k, v in kw.items():
        setattr(side, k, v)
    return side


def test_a_class_the_corpus_never_nests_is_not_evaluated_not_clean():
    flat = {"LexSense": {"children_of": {}, "roots": [GUID_A, GUID_B]}}
    results = FP.depth_results(_side(flat), _side(flat), classes=("LexSense",))
    block = A.depth_block(results)
    assert block["not_evaluated_classes"] == ["LexSense"]
    assert block["vacuous_classes"] == []


def test_a_target_that_lost_a_level_is_vacuous_for_that_class():
    src = {"LexSense": {"children_of": {GUID_A: [GUID_B]}, "roots": [GUID_A]}}
    tgt = {"LexSense": {"children_of": {}, "roots": [GUID_A]}}
    block = A.depth_block(FP.depth_results(_side(src), _side(tgt),
                                           classes=("LexSense",)))
    assert block["vacuous_classes"] == ["LexSense"]
    assert block["not_evaluated_classes"] == []


def test_a_per_parent_degree_disagreement_is_reported():
    src = {"LexSense": {"children_of": {GUID_A: [GUID_B, GUID_C]}, "roots": [GUID_A]}}
    tgt = {"LexSense": {"children_of": {GUID_A: [GUID_B]}, "roots": [GUID_A]}}
    block = A.depth_block(FP.depth_results(_side(src), _side(tgt),
                                           classes=("LexSense",)))
    assert block["per_parent_degree_findings"]
    assert block["per_parent_degree_findings"][0]["source_children"] == 2


# ===========================================================================
# 8. THE LIVE GATHER'S FAILURE DISCIPLINE (with an injected project)
# ===========================================================================

class _FakeWs:
    def __init__(self, tag, handle):
        self.Id = tag
        self.Handle = handle


class _FakeWritingSystems:
    def __init__(self, pairs):
        self._pairs = pairs

    def GetAll(self):
        return [_FakeWs(t, h) for t, h in self._pairs]


class _FakeProject:
    """Just enough surface for ``gather_field_plane_side`` -- the live pieces
    (``_enumerate_objects``, ``build_field_source``) are monkeypatched, so
    this stands in for the FLExProject handle only."""

    def __init__(self):
        self.WritingSystems = _FakeWritingSystems([("en", 999000001),
                                                   ("etu", 999000003)])
        self.closed = False

    def GetDefaultVernacularWS(self):
        return ("etu", "Ejagham")

    def GetDefaultAnalysisWS(self):
        return ("en", "English")


def _install_fake_gather(monkeypatch, objects, raising_classes=()):
    proj = _FakeProject()

    def _open(_name):
        def _close():
            proj.closed = True
        return proj, _close

    monkeypatch.setattr(FP, "_enumerate_objects",
                        lambda _p, _n: (objects, {}))

    def _field_source(cls, guid):
        if cls in raising_classes:
            raise RuntimeError("'FLExProject' object has no attribute "
                               "'GetMultiStringDict'")
        return (["Name"], {"Name": {"en": "x"}})

    monkeypatch.setattr("fullsweep.field_dispatch.build_field_source",
                        lambda _p: _field_source)
    monkeypatch.setattr("fullsweep.field_dispatch.partition_dispatchable",
                        lambda classes: (tuple(classes), {}))
    return proj, _open


def test_a_class_whose_accessor_raises_costs_that_class_not_the_run(monkeypatch):
    """Ten classes' accessors raise live (field_dispatch's "OTHER LIVE
    DEFECTS"). Aborting the sweep for one of them would trade a partial
    measurement for none; skipping it silently would report a hole as clean."""
    objects = {"PartOfSpeech": [GUID_A], "WfiWordform": [GUID_B]}
    proj, opener = _install_fake_gather(monkeypatch, objects,
                                        raising_classes={"WfiWordform"})
    side = FP.gather_field_plane_side(
        "Ejagham Mini", roster=_divergent_roster(), open_project=opener)
    assert "WfiWordform" in side.unreadable_classes
    assert "GetMultiStringDict" in side.unreadable_classes["WfiWordform"]
    assert "PartOfSpeech" in side.census.values
    assert side.cost["classes_measured"] == 1
    assert side.cost["classes_unreadable"] == 1
    assert proj.closed is True


def test_the_gather_records_the_handle_map_it_will_be_compared_through(monkeypatch):
    _proj, opener = _install_fake_gather(monkeypatch, {"PartOfSpeech": [GUID_A]})
    side = FP.gather_field_plane_side(
        "Ejagham Mini", roster=_divergent_roster(), open_project=opener)
    assert side.handle_to_tag == {"999000001": "en", "999000003": "etu"}
    assert side.ws_keys == {"en", "etu", "999000001", "999000003"}
    assert side.default_vernacular == "etu"


def test_a_cap_is_recorded_because_a_cap_is_an_exclusion(monkeypatch):
    _proj, opener = _install_fake_gather(
        monkeypatch, {"PartOfSpeech": [GUID_A, GUID_B, GUID_C]})
    side = FP.gather_field_plane_side(
        "Ejagham Mini", roster=_divergent_roster(),
        max_objects_per_class=1, open_project=opener)
    assert side.cost["max_objects_per_class"] == 1
    assert side.cost["field_reads"] == 1
