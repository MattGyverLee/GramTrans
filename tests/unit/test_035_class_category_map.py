"""Feature 035 -- T045e: the class -> GrammarCategory join, as a tracked contract.

NO FLEx project and NO LCM in this file. Everything here is the shipped
contract (``specs/035-fullsweep-fidelity/contracts/class-category-map.json``)
plus the pure-python reader in ``debug/fullsweep/coverage.py``.

The tests fall into four groups, and the second is the one that earns its keep:

1. THE SHIPPED CONTRACT LOADS AND AGREES WITH THE FLOOR. Same discipline as
   feature 038's ``derivation_check``: the class roster is PROVEN on every run
   rather than asserted once, and the TABLE 1 category column is re-parsed out
   of ``object-inventory.md`` so a later edit to the prose that is not carried
   into the JSON fails here instead of silently skewing every category-keyed
   number.

2. EVERY VALIDATION RAISES. Each malformed-contract test corresponds to a
   mistake whose SILENT outcome would be a confidently wrong category tally
   rather than an error -- an unexplained empty category list, an undefined
   reason token, a category that is neither carried nor declared empty, a
   duplicate join key. These are the tests that make the reader's paranoia
   real; without them the checks are decoration.

3. THE FR-109 BOUNDARY. ``project_comparisons_to_categories`` returns ``None``
   and never ``{}`` for an unmeasured run, because ``{}`` is the one value that
   would make ``guard_comparisons_performed`` report ``pass`` over nothing.
   Asserted against the real guard, not just the projector.

4. THE TWO TRAPS T045e NAMES, pinned so a later refactor cannot quietly
   reintroduce them: ``classify_coverage``'s class-keyed ``comparisons``
   parameter is NOT the guard's category-keyed ``ctx.comparisons``, and the
   projection REPLICATES multi-category classes rather than partitioning them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import coverage as C, guards as G  # noqa: E402

CONTRACTS = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
INVENTORY = _ROOT / "specs" / "035-fullsweep-fidelity" / "object-inventory.md"


@pytest.fixture(scope="module")
def cmap():
    return C.load_class_category_map()


@pytest.fixture(scope="module")
def floor():
    return C.load_coverage_floor()


def _write(tmp_path, doc) -> Path:
    p = tmp_path / C.CLASS_CATEGORY_MAP_NAME
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


@pytest.fixture
def base_doc(cmap):
    """The shipped contract, as mutable JSON, for the malformed-contract tests."""
    return json.loads((CONTRACTS / C.CLASS_CATEGORY_MAP_NAME).read_text(encoding="utf-8"))


# ===========================================================================
# 1. The shipped contract
# ===========================================================================


def test_shipped_map_loads(cmap):
    assert cmap.schema_version == C.SCHEMA_VERSION
    assert cmap.entries
    assert cmap.path is not None


def test_shipped_map_covers_the_floor_exactly(cmap, floor):
    """The join and the roster must name the same classes -- a class on one and
    not the other is a silent hole in whichever direction it points."""
    cmap.assert_covers_floor(floor)
    assert cmap.class_names == frozenset(floor.in_scope_classes)


def test_every_category_is_either_carried_or_declared_empty(cmap):
    """FR-137 in the category direction: no category may be merely unmentioned."""
    carried = {c for c in cmap.category_vocabulary if cmap.classes_for(c)}
    empty = cmap.categoryless
    assert carried | empty == set(cmap.category_vocabulary)
    assert not (carried & empty)


def test_category_vocabulary_matches_the_GrammarCategory_enum():
    """The contract's closed vocabulary must BE the enum, not a stale copy of it.

    A member added to ``GrammarCategory`` without a decision about which
    classes it creates would otherwise sit unnoticed, and a run could report it
    clean having never dispatched it.
    """
    models = _ROOT / "src" / "gramtrans" / "Lib" / "models.py"
    src = models.read_text(encoding="utf-8")
    block = re.search(r"class GrammarCategory\(enum\.Enum\):(.*?)\n\nclass ", src, re.S)
    assert block, "GrammarCategory enum block not found in models.py"
    enum_values = re.findall(r'^    [A-Z_0-9]+ = "([a-z_0-9]+)"', block.group(1), re.M)
    doc = json.loads((CONTRACTS / C.CLASS_CATEGORY_MAP_NAME).read_text(encoding="utf-8"))
    assert sorted(doc["category_vocabulary"]) == sorted(enum_values)


def test_class_roster_is_derivable_from_the_inventory_prose(cmap):
    """CP-1-style derivation check, the same shape 038's census uses.

    TABLE 1's class column is re-parsed here. Every class the inventory records
    as CREATED must be mapped; the map may additionally carry referenced-only
    classes (TABLE 2) that TABLE 1 never lists, which is why this is a subset
    assertion in one direction and an explicit reason check in the other.
    """
    lines = INVENTORY.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("## TABLE 1"))
    end = next(i for i, l in enumerate(lines) if l.startswith("## TABLE 2"))
    table1 = set()
    for line in lines[start:end]:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0].startswith("---") or cells[0] == "Object (class)":
            continue
        if not cells[0].startswith("("):
            table1.add(cells[0])

    unmapped_from_table1 = sorted(table1 - cmap.class_names)
    assert not unmapped_from_table1, (
        "object-inventory.md TABLE 1 creates %r, which class-category-map.json does "
        "not map" % unmapped_from_table1
    )

    # Classes on the map but NOT created per TABLE 1 must say so explicitly.
    for name in sorted(cmap.class_names - table1):
        reason = cmap.unmapped_reason_for(name)
        assert reason is not None, (
            "%r is mapped to a category but object-inventory.md TABLE 1 records no "
            "create site for it" % name
        )


def test_the_ten_unmapped_classes_are_exactly_the_recorded_ones(cmap):
    """Pinned deliberately. Moving a class into or out of the unmapped set is a
    coverage decision, so it has to be made by editing this list."""
    assert dict(cmap.unmapped_classes) == {
        "CmAnthroItem": "reference-create-arm-only",
        "CmPossibility": "reference-create-arm-only",
        "MoMorphType": "reference-create-arm-only",
        "LexReference": "post-pass-no-category",
        "ReversalIndex": "post-pass-no-category",
        "ReversalIndexEntry": "post-pass-no-category",
        "LexAppendix": "never-created-referenced-only",
        "LexRefType": "never-created-referenced-only",
        "PhBdryMarker": "never-created-referenced-only",
        "PunctuationForm": "never-created-referenced-only",
    }


def test_never_created_classes_agree_with_the_inventory(cmap):
    """object-inventory.md TABLE 2: 'only LexRefType, LexAppendix and
    PhBdryMarker are NEVER created by any path'. PunctuationForm is the fourth,
    adjudicated under T045e from Lib/wordforms.py:380 -- it is reachable only as
    an alignment token that ``_normalize_token_to_analysis`` maps to None."""
    never = {c for c, r in cmap.unmapped_classes if r == "never-created-referenced-only"}
    assert never == {"LexRefType", "LexAppendix", "PhBdryMarker", "PunctuationForm"}


def test_feature_system_split_classes_carry_the_038_join_key(cmap):
    """The two classes a FieldWorks project owns from BOTH feature systems are
    split on the same discriminator 038's census ``classRow`` uses, so the join
    stays single-valued. Summing the halves is what A1 exists to prevent."""
    for cls, ms, ph in (
        ("FsFeatStrucType", "feature_struct_types", "phon_feat_types"),
        ("FsClosedFeature", "inflection_features", "phonological_features"),
    ):
        rows = cmap.entries_for(cls)
        assert len(rows) == 2, cls
        systems = {r.owning_feature_system for r in rows}
        assert systems == {
            "LangProject.MsFeatureSystemOA",
            "LangProject.PhFeatureSystemOA",
        }, cls
        assert cmap.categories_for(cls, "LangProject.MsFeatureSystemOA") == (ms,)
        assert cmap.categories_for(cls, "LangProject.PhFeatureSystemOA") == (ph,)
        # Undiscriminated, the caller gets BOTH -- never one silently.
        assert set(cmap.categories_for(cls)) == {ms, ph}


def test_lex_entry_ref_is_stems_only_per_G3(cmap):
    """object-inventory.md TABLE 1 lists LexEntryRef as 'AFFIXES, STEMS'; G3
    measures that ``_run_entryref_create_pass`` is invoked ONLY from
    ``stems_execute_action``. Mapping it to affixes would let an affixes-only
    run report coverage of a class it cannot create."""
    assert cmap.categories_for("LexEntryRef") == ("stems",)


def test_excluding_stems_strands_exactly_lex_entry_ref(cmap):
    """G3's undocumented consequence, made machine-checkable. ``LexEntry`` stays
    reachable with STEMS off because AFFIXES also creates it; ``LexEntryRef``
    does not, because STEMS is its only creator."""
    stranded = C.categories_reachable_only_through_excluded(cmap, ["stems"])
    assert stranded == ("LexEntryRef",)
    assert "LexEntry" not in stranded


def test_unmapped_classes_are_not_reported_as_excluded_reach(cmap):
    """A permanent structural hole must not be attributed to a per-run
    exclusion. Excluding everything still leaves the ten unmapped classes out
    of the reachable-only-through-excluded bucket."""
    everything = list(cmap.category_vocabulary)
    stranded = set(C.categories_reachable_only_through_excluded(cmap, everything))
    assert not (stranded & {c for c, _ in cmap.unmapped_classes})


def test_categoryless_categories_are_the_recorded_eight(cmap):
    assert cmap.categoryless == {
        "custom_fields", "pos_inflectable_feats", "exception_features",
        "writing_systems_check", "entry", "sense", "msa", "allomorph",
    }
    for cat in cmap.categoryless:
        gap = cmap.gap_for(cat)
        assert gap is not None and gap.reason and gap.detail


def test_pos_is_a_dispatched_alias_of_gram_categories(cmap):
    """POS is NOT a dead Phase-0 surface category, though its four siblings are.

    transfer.py carries it in ``_LEAF_DISPATCH_CATEGORIES`` as "the pick-driven
    ALIAS of GRAM_CATEGORIES", and its bundle's ``execute_action`` IS
    ``gram_categories_execute_action`` -- the same create site under a different
    stamped category. Crediting only GRAM_CATEGORIES would leave a pick-driven
    run's POS work attributed to a category it never dispatched.

    This is pinned because the contract was first authored against a branch
    whose ``transfer.py`` predated the change, and
    ``test_phase0_categories_are_marked_as_not_dispatched`` is what caught it.
    """
    assert "pos" not in cmap.categoryless
    assert cmap.category_dispatch["pos"] == C.DISPATCH_LEAF
    assert cmap.classes_for("pos") == ("PartOfSpeech",)
    assert set(cmap.categories_for("PartOfSpeech")) == {"gram_categories", "pos"}


def test_phase0_categories_are_marked_as_not_dispatched(cmap):
    """The five Phase-0 surface categories are absent from
    transfer.py ``_LEAF_DISPATCH_CATEGORIES``; the contract records that, so a
    full run cannot report them measured."""
    transfer = (_ROOT / "src" / "gramtrans" / "Lib" / "transfer.py").read_text(encoding="utf-8")
    block = re.search(r"_LEAF_DISPATCH_CATEGORIES = \((.*?)\n    \)", transfer, re.S)
    assert block
    dispatched = set(re.findall(r"GrammarCategory\.([A-Z_0-9]+)", block.group(1)))
    for cat, kind in cmap.category_dispatch.items():
        if kind == C.DISPATCH_LEAF:
            assert cat.upper() in dispatched, cat
        elif kind == C.DISPATCH_PHASE0_UNUSED:
            assert cat.upper() not in dispatched, cat


# ===========================================================================
# 2. Every validation actually raises
# ===========================================================================


def test_missing_file_raises(tmp_path):
    with pytest.raises(C.ClassCategoryMapError, match="does not exist"):
        C.load_class_category_map(tmp_path / "nope.json")


def test_bad_json_raises(tmp_path):
    p = tmp_path / C.CLASS_CATEGORY_MAP_NAME
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(C.ClassCategoryMapError, match="not valid JSON"):
        C.load_class_category_map(p)


def test_wrong_schema_version_raises(tmp_path, base_doc):
    base_doc["schema_version"] = C.SCHEMA_VERSION + 1
    with pytest.raises(C.ClassCategoryMapError, match="schema_version"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_empty_categories_with_no_reason_raises(tmp_path, base_doc):
    """THE central check. An unexplained empty category list is the invisible
    default FR-135 forbids, and it is also the single easiest way to make a
    class disappear from every category tally without anything reporting it."""
    for row in base_doc["classes"]:
        if row["class"] == "PhPhoneme":
            row["categories"] = []
            row["unmapped_reason"] = None
    with pytest.raises(C.ClassCategoryMapError, match="Exactly one must be present"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_both_categories_and_reason_raises(tmp_path, base_doc):
    for row in base_doc["classes"]:
        if row["class"] == "PhPhoneme":
            row["unmapped_reason"] = "post-pass-no-category"
    with pytest.raises(C.ClassCategoryMapError, match="Exactly one must be present"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_undefined_unmapped_reason_token_raises(tmp_path, base_doc):
    for row in base_doc["classes"]:
        if row["class"] == "ReversalIndex":
            row["unmapped_reason"] = "because-i-said-so"
    with pytest.raises(C.ClassCategoryMapError, match="not defined in"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_category_outside_the_vocabulary_raises(tmp_path, base_doc):
    for row in base_doc["classes"]:
        if row["class"] == "PhPhoneme":
            row["categories"] = ["phonemes", "phonems"]  # typo
    with pytest.raises(C.ClassCategoryMapError, match="not in category_vocabulary"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_duplicate_join_key_raises(tmp_path, base_doc):
    """(class, owning_feature_system) is the key 038's census shares. A
    duplicate makes the join multi-valued and the attribution ambiguous."""
    row = next(r for r in base_doc["classes"] if r["class"] == "PhPhoneme")
    base_doc["classes"].append(dict(row))
    with pytest.raises(C.ClassCategoryMapError, match="more than once"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_category_neither_carried_nor_declared_empty_raises(tmp_path, base_doc):
    base_doc["category_vocabulary"].append("brand_new_category")
    base_doc["category_dispatch"]["brand_new_category"] = C.DISPATCH_LEAF
    with pytest.raises(C.ClassCategoryMapError, match="neither carrying a class nor"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_category_both_carried_and_declared_empty_raises(tmp_path, base_doc):
    base_doc["categories_without_in_scope_class"].append({
        "category": "phonemes",
        "reason": "no-lcm-object-created",
        "detail": "contradictory",
    })
    with pytest.raises(C.ClassCategoryMapError, match="both maps a class to"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_categoryless_entry_with_no_reason_raises(tmp_path, base_doc):
    base_doc["categories_without_in_scope_class"][0]["reason"] = ""
    with pytest.raises(C.ClassCategoryMapError, match="with NO reason"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_unknown_dispatch_value_raises(tmp_path, base_doc):
    base_doc["category_dispatch"]["phonemes"] = "sometimes"
    with pytest.raises(C.ClassCategoryMapError, match="category_dispatch value outside"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_missing_dispatch_entry_raises(tmp_path, base_doc):
    del base_doc["category_dispatch"]["phonemes"]
    with pytest.raises(C.ClassCategoryMapError, match="no category_dispatch"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_empty_vocabulary_raises(tmp_path, base_doc):
    base_doc["category_vocabulary"] = []
    with pytest.raises(C.ClassCategoryMapError, match="EMPTY category_vocabulary"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_unknown_class_lookup_raises_rather_than_returning_empty(cmap):
    """The distinction this whole module turns on: 'no category creates it' and
    'I have never heard of it' are different facts, and a caller that cannot
    tell them apart reports a gap as a clean."""
    with pytest.raises(C.ClassCategoryMapError, match="has no row in"):
        cmap.categories_for("NotAClass")
    with pytest.raises(C.ClassCategoryMapError, match="not a GrammarCategory"):
        cmap.classes_for("not_a_category")


def test_unmatched_feature_system_discriminator_raises(cmap):
    with pytest.raises(C.ClassCategoryMapError, match="owning_feature_system"):
        cmap.categories_for("FsFeatStrucType", "LangProject.NoSuchSystemOA")


def test_dropping_a_categorys_only_carrier_raises_at_load(tmp_path, base_doc):
    """``PhPhoneme`` is the sole class carrying ``phonemes``. Deleting its row
    leaves the category carried by nothing and declared empty by nothing, and
    the loader refuses before any lookup can return a cheerful zero for it."""
    base_doc["classes"] = [r for r in base_doc["classes"] if r["class"] != "PhPhoneme"]
    with pytest.raises(C.ClassCategoryMapError, match=r"neither carrying a class nor.*phonemes|"
                                                      r"'phonemes'\] neither carrying"):
        C.load_class_category_map(_write(tmp_path, base_doc))


def test_assert_covers_floor_names_the_offenders(floor, tmp_path, base_doc):
    """A class dropped from the map but still on the floor is named explicitly.

    ``PhMetathesisRule`` is one of nine classes carrying ``phonological_rules``,
    so removing it leaves the vocabulary fully accounted for and the failure
    lands where this test is aiming: the floor/map roster comparison.
    """
    base_doc["classes"] = [r for r in base_doc["classes"] if r["class"] != "PhMetathesisRule"]
    partial = C.load_class_category_map(_write(tmp_path, base_doc))
    with pytest.raises(C.ClassCategoryMapError, match="PhMetathesisRule"):
        partial.assert_covers_floor(floor)


# ===========================================================================
# 3. The FR-109 boundary
# ===========================================================================


def test_unmeasured_projection_is_None_never_empty_dict(cmap):
    """``{}`` is the one value that would make the guard report pass over
    nothing; ``None`` is what makes it report not-evaluated."""
    out = C.project_comparisons_to_categories(cmap, source_objects=None)
    assert out is None
    assert out is not {}  # noqa: F632 -- the point is that {} would be wrong


def test_guard_reports_not_evaluated_on_the_unmeasured_projection(cmap):
    proj = C.project_comparisons_to_categories(cmap, source_objects=None)
    ctx = G.RunContext(project="p", comparisons=proj)
    assert G.guard_comparisons_performed(ctx).result == "not-evaluated"


def test_guard_answers_on_a_measured_projection(cmap):
    """T045e's whole purpose: COMPARISONS-PERFORMED moves off not-evaluated."""
    proj = C.project_comparisons_to_categories(
        cmap,
        source_objects={"PhNCSegments": 5, "PhNCFeatures": 3},
        comparisons_performed={"PhNCSegments": 5, "PhNCFeatures": 3},
        objects_compared={"PhNCSegments": 5, "PhNCFeatures": 3},
    )
    ctx = G.RunContext(project="p", comparisons=proj["comparisons"])
    assert G.guard_comparisons_performed(ctx).result == "pass"


def test_guard_fails_on_a_category_that_compared_nothing(cmap):
    proj = C.project_comparisons_to_categories(
        cmap,
        source_objects={"PhPhoneme": 30},
        comparisons_performed={"PhPhoneme": 0},
        objects_compared={"PhPhoneme": 0},
    )
    res = G.guard_comparisons_performed(G.RunContext(project="p", comparisons=proj["comparisons"]))
    assert res.result == "fail"
    assert res.evidence["vacuous_categories"][0]["category"] == "phonemes"


def test_unattributable_classes_are_surfaced_not_dropped(cmap):
    """A measured class no category creates must come back to the caller, not
    vanish. Dropping it would hide whatever it found."""
    proj = C.project_comparisons_to_categories(
        cmap,
        source_objects={"ReversalIndex": 7, "LexEntry": 2},
        comparisons_performed={"ReversalIndex": 0, "LexEntry": 2},
        objects_compared={"ReversalIndex": 0, "LexEntry": 2},
    )
    assert [u["class"] for u in proj["unattributable"]] == ["ReversalIndex"]
    assert proj["unattributable"][0]["reason"] == "post-pass-no-category"
    assert proj["unattributable"][0]["source_objects"] == 7
    # ...and it did NOT become a category.
    assert "reversal_index" not in proj["comparisons"]


def test_categoryless_categories_are_omitted_not_zeroed(cmap):
    """A fabricated zero for a category that creates nothing is a measurement
    claim about something never measurable."""
    proj = C.project_comparisons_to_categories(cmap, source_objects={"LexEntry": 1})
    for cat in cmap.categoryless:
        assert cat not in proj["comparisons"]
    assert proj["categoryless_categories"] == sorted(cmap.categoryless)


def test_measured_class_absent_from_the_map_raises(cmap):
    with pytest.raises(C.ClassCategoryMapError, match="does not map"):
        C.project_comparisons_to_categories(cmap, source_objects={"MadeUpClass": 3})


# ===========================================================================
# 4. The two traps T045e names
# ===========================================================================


def test_classify_coverage_comparisons_is_class_keyed_not_category_keyed(cmap, floor):
    """TRAP 1. ``classify_coverage(comparisons=...)`` is ``{class_name: int}``;
    the guard's ``ctx.comparisons`` is ``{category: {...}}``. Feeding the
    category-keyed shape to the class-keyed parameter does not raise -- it
    quietly demotes every class to never-attempted -- which is exactly why this
    is pinned rather than left to reviewer memory."""
    survey = {c: 1 for c in floor.in_scope_classes}
    proj = C.project_comparisons_to_categories(
        cmap, source_objects={"PhPhoneme": 4}, comparisons_performed={"PhPhoneme": 4},
        objects_compared={"PhPhoneme": 4},
    )

    # The CORRECT class-keyed call.
    right = C.classify_coverage(
        floor, survey=survey, comparisons={c: 1 for c in floor.in_scope_classes},
        project="right",
    )
    assert right.status_for("PhPhoneme") == C.STATUS_CLEAN

    # The WRONG wiring: category-keyed dict into the class-keyed parameter.
    wrong = C.classify_coverage(
        floor, survey=survey, comparisons=proj["comparisons"], project="wrong",
    )
    assert wrong.status_for("PhPhoneme") == C.STATUS_NOT_EVALUATED
    assert not wrong.reports_clean


def test_projection_replicates_multi_category_classes_and_says_so(cmap):
    """TRAP 2. ``LexEntry`` is created under both AFFIXES and STEMS, so both are
    credited with it. Right for 'did this category compare anything?', wrong for
    any total -- so the provenance names every replicated class."""
    proj = C.project_comparisons_to_categories(
        cmap,
        source_objects={"LexEntry": 40},
        comparisons_performed={"LexEntry": 40},
        objects_compared={"LexEntry": 40},
    )
    assert proj["comparisons"]["affixes"]["source_objects"] == 40
    assert proj["comparisons"]["stems"]["source_objects"] == 40
    assert {r["class"] for r in proj["replicated_classes"]} == {"LexEntry"}

    # The sum double-counts: 80 over a source of 40. That is the documented
    # consequence, pinned so nobody "fixes" the guard by totalling it.
    total = sum(r["source_objects"] for r in proj["comparisons"].values())
    assert total == 80
    assert total != 40


def test_every_category_record_names_its_contributing_classes(cmap):
    """The projection carries the class list per category, so a category tally
    can always be traced back to the class-keyed measurement it came from."""
    proj = C.project_comparisons_to_categories(
        cmap, source_objects={"PhNCSegments": 1, "PhNCFeatures": 2},
    )
    assert proj["comparisons"]["natural_classes"]["classes"] == [
        "PhNCFeatures", "PhNCSegments",
    ]


def test_map_as_dict_is_json_serializable(cmap):
    """``flush_artifact`` is ``asdict``/``json.dumps``; a block that cannot
    serialize takes the whole artifact down with it."""
    json.dumps(cmap.as_dict())
