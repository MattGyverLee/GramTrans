"""T007/T008/T016/T023 — build_phonology_inventory + collapse_phonology (spec 010)."""
from __future__ import annotations

from _fakes_phonology import (
    FakeEnv, FakeFeature, FakeNC, FakePhoneme, FakePhonSource, FakeRule,
    FakeStratum, make_rhs,
)

from gramtrans.Lib.models import GrammarCategory as GC
from gramtrans.Lib.selection import (
    build_phonology_inventory, collapse_phonology,
)


def _rich_source():
    f1 = FakeFeature("f1", "voiced")
    p1 = FakePhoneme("ph1", "p", feature_refs=[f1])
    p2 = FakePhoneme("ph2", "t")
    nc1 = FakeNC("nc1", "C", segments=[p1, p2])
    env1 = FakeEnv("env1", "_#")
    strat = FakeStratum("s1", "stratum")
    rule1 = FakeRule("r1", "devoicing", struc_refs=[nc1],
                     rhs=[make_rhs(left=p1)], stratum=strat)
    return FakePhonSource(
        features=[f1], phonemes=[p1, p2], ncs=[nc1], envs=[env1],
        rules=[rule1], strata=[strat],
    )


def test_five_groups_in_order_with_counts():
    inv = build_phonology_inventory(_rich_source())
    cats = [g.category for g in inv.groups]
    assert cats == [
        GC.PHONOLOGICAL_FEATURES, GC.PHONEMES, GC.NATURAL_CLASSES,
        GC.PH_ENVIRONMENT, GC.PHONOLOGICAL_RULES,
    ]
    counts = {g.category: g.count for g in inv.groups}
    assert counts[GC.PHONEMES] == 2
    assert counts[GC.NATURAL_CLASSES] == 1
    assert counts[GC.PHONOLOGICAL_RULES] == 1
    # No strata group is ever surfaced (FR-009 / FR-002).
    assert GC.STRATA not in cats


def test_all_rows_preselected():
    inv = build_phonology_inventory(_rich_source())
    assert all(r.preselected for g in inv.groups for r in g.rows)


def test_orphan_natural_classes_predeselected():
    """An orphan NC opens UNCHECKED; a referenced NC stays on.

    Orphan-hood is injected (the live builder derives it from LCM
    ReferringObjects; fakes can't, so tests pass the set explicitly). FLEx
    strands a "Created automatically for rule X" NC whenever a rule context is
    re-saved, so those dead classes should not ride along on a Move by default.
    """
    p1 = FakePhoneme("ph1", "p")
    used_nc = FakeNC("nc_used", "C", segments=[p1])
    orphan_nc = FakeNC("nc_orphan", "Created automatically for rule \"gone\"",
                       segments=[p1])
    src = FakePhonSource(phonemes=[p1], ncs=[used_nc, orphan_nc])

    inv = build_phonology_inventory(src, orphan_nc_guids=frozenset({"nc_orphan"}))
    nc_rows = {r.guid: r for r in inv.group_for(GC.NATURAL_CLASSES).rows}
    assert nc_rows["nc_used"].preselected is True
    assert nc_rows["nc_orphan"].preselected is False
    # non-NC rows are unaffected — phonemes still open preselected.
    assert all(r.preselected for r in inv.group_for(GC.PHONEMES).rows)


def test_no_orphans_means_all_preselected():
    """Empty orphan set (or the None default with no LCM) => every NC checked."""
    p1 = FakePhoneme("ph1", "p")
    nc1 = FakeNC("nc1", "C", segments=[p1])
    nc2 = FakeNC("nc2", "V", segments=[p1])
    src = FakePhonSource(phonemes=[p1], ncs=[nc1, nc2])
    # Explicit empty set and the None default (no LCM in tests) behave the same.
    for kwargs in ({"orphan_nc_guids": frozenset()}, {}):
        inv = build_phonology_inventory(src, **kwargs)
        assert all(r.preselected for r in inv.group_for(GC.NATURAL_CLASSES).rows)


def test_orphan_predeselect_collapses_to_leaf_pick_subset():
    """Opening with the orphan unchecked collapses to a trimmed NC subset."""
    p1 = FakePhoneme("ph1", "p")
    used_nc = FakeNC("nc_used", "C", segments=[p1])
    orphan_nc = FakeNC("nc_orphan", "junk", segments=[p1])
    src = FakePhonSource(phonemes=[p1], ncs=[used_nc, orphan_nc])

    inv = build_phonology_inventory(src, orphan_nc_guids=frozenset({"nc_orphan"}))
    # simulate the page's initial check state = each row's `preselected`.
    checked = {
        g.category: {r.guid for r in g.rows if r.preselected}
        for g in inv.groups
    }
    out = collapse_phonology(inv, checked)
    assert out["categories"][GC.NATURAL_CLASSES] is True
    assert out["leaf_item_picks"][GC.NATURAL_CLASSES] == frozenset({"nc_used"})


def test_empty_category_renders_not_errors():
    src = FakePhonSource(phonemes=[FakePhoneme("ph1", "p")])  # only phonemes
    inv = build_phonology_inventory(src)
    rules = inv.group_for(GC.PHONOLOGICAL_RULES)
    assert rules is not None and rules.count == 0  # empty, no error
    assert inv.has_rules is False


def test_reference_maps_populated():
    inv = build_phonology_inventory(_rich_source())
    assert inv.nc_referenced_phoneme_guids["nc1"] == frozenset({"ph1", "ph2"})
    assert inv.phoneme_referenced_feature_guids["ph1"] == frozenset({"f1"})
    assert inv.rule_referenced_nc_guids["r1"] == frozenset({"nc1"})
    assert inv.rule_referenced_phoneme_guids["r1"] == frozenset({"ph1"})


def test_target_status_new_and_in_target():
    src = _rich_source()
    # target has the same phonemes -> in_target; fresh categories -> new
    tgt = FakePhonSource(phonemes=[FakePhoneme("ph1", "p"), FakePhoneme("ph2", "t")])
    inv = build_phonology_inventory(src, target=tgt)
    ph = {r.guid: r.status for r in inv.group_for(GC.PHONEMES).rows}
    assert ph == {"ph1": "in_target", "ph2": "in_target"}
    nc = inv.group_for(GC.NATURAL_CLASSES).rows[0]
    assert nc.status == "new"


def test_target_none_status_blank():
    inv = build_phonology_inventory(_rich_source(), target=None)
    assert all(r.status is None for g in inv.groups for r in g.rows)


def test_target_status_by_guid_similar_and_new():
    """T023 (US4/SC-005): in_target by GUID, similar by label, else new."""
    src = FakePhonSource(phonemes=[
        FakePhoneme("ph1", "p"),   # same GUID in target -> in_target
        FakePhoneme("ph2", "t"),   # same label 't' but different GUID -> similar
        FakePhoneme("ph3", "k"),   # absent -> new
    ])
    tgt = FakePhonSource(phonemes=[
        FakePhoneme("ph1", "p"),
        FakePhoneme("ph9", "t"),   # different GUID, same label as source ph2
    ])
    inv = build_phonology_inventory(src, target=tgt)
    status = {r.guid: r.status for r in inv.group_for(GC.PHONEMES).rows}
    assert status == {"ph1": "in_target", "ph2": "similar", "ph3": "new"}


# ---- collapse_phonology --------------------------------------------------

def _all_checked(inv):
    return {g.category: {r.guid for r in g.rows} for g in inv.groups}


def test_collapse_all_checked_no_leaf_keys():
    inv = build_phonology_inventory(_rich_source())
    out = collapse_phonology(inv, _all_checked(inv))
    # every populated category on
    assert out["categories"][GC.PHONEMES] is True
    assert out["categories"][GC.PHONOLOGICAL_RULES] is True
    # all-checked => transfer-all => NO leaf_item_picks keys
    assert out["leaf_item_picks"] == {}
    # rule kept => strata on (FR-009)
    assert out["categories"].get(GC.STRATA) is True


def test_collapse_trim_records_subset():
    inv = build_phonology_inventory(_rich_source())
    checked = _all_checked(inv)
    checked[GC.PHONEMES] = {"ph1"}  # trim one of two
    out = collapse_phonology(inv, checked)
    assert out["leaf_item_picks"][GC.PHONEMES] == frozenset({"ph1"})


def test_collapse_whole_block_off():
    inv = build_phonology_inventory(_rich_source())
    out = collapse_phonology(inv, {c: set() for c in
                                   (GC.PHONEMES, GC.NATURAL_CLASSES,
                                    GC.PHONOLOGICAL_RULES)})
    assert out["categories"] == {}
    assert out["leaf_item_picks"] == {}


# ---- T016 (US1): preselect-all => 5 cats on, no picks; no conflict control --

def test_us1_preselect_all_five_categories_on_no_picks():
    """SC-001/SC-002: the page opens ALL preselected; collapsing that state
    turns every one of the five populated categories on with no trim keys."""
    inv = build_phonology_inventory(_rich_source())
    out = collapse_phonology(inv, _all_checked(inv))
    for cat in (GC.PHONOLOGICAL_FEATURES, GC.PHONEMES, GC.NATURAL_CLASSES,
                GC.PH_ENVIRONMENT, GC.PHONOLOGICAL_RULES):
        assert out["categories"][cat] is True, cat
    assert out["leaf_item_picks"] == {}  # transfer-all, no GUID lists


def test_us1_no_conflict_mode_control_on_phonology_page():
    """SC-008 / FR-012 (analyze finding G1): _PagePhonology must render NO
    ADD_NEW/MERGE/OVERWRITE conflict-mode control. Verified by source scan
    (instantiating the QWizardPage pollutes sip state across the suite)."""
    import ast
    import inspect
    import textwrap

    from gramtrans.Lib.ui import selection_wizard as _sw

    # Feature 039 T024: read the CLASS, not the module file. `inspect.getsource`
    # follows the object, so this scan survives `_PagePhonology` moving to
    # `wizard_pages_blocks.py` -- and any future move -- without naming a path.
    # The previous form read `Path(_sw.__file__).read_text()` and located the
    # class with `next(...)`, which raises StopIteration the moment the class is
    # not in that file: loud, but for the wrong reason, and only by luck rather
    # than by design.
    src = textwrap.dedent(inspect.getsource(_sw._PagePhonology))
    page_cls = ast.parse(src).body[0]
    assert isinstance(page_cls, ast.ClassDef) and page_cls.name == "_PagePhonology"
    # Collect referenced identifiers (Name ids + Attribute attrs) — ignores
    # docstrings/comments, which legitimately spell out FR-012 by name.
    identifiers = set()
    for node in ast.walk(page_cls):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
    for banned in ("ConflictMode", "_CONFLICT_LABELS", "_allowed_modes",
                   "OVERWRITE", "ADD_NEW", "MERGE"):
        assert banned not in identifiers, (
            f"phonology page must not reference {banned}"
        )
