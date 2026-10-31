"""Issue #108 -- struct-type `FeaturesRS` repair pass.

`IFsFeatStrucType.FeaturesRS` (FEATURE_STRUCT_TYPES and the phonological twin
PHON_FEAT_TYPES) was wired only at create; a type created before its member
feature defns existed stayed incomplete forever. These tests pin the fix:

- Preview gathers the source `FeaturesRS` of every in-scope struct-type -- in
  the target already or planned for create -- including on a run that plans
  no action for the type (the repair case) and for closure-pulled types.
- The Move pass brings target membership to source order by GUID (rebuild,
  not append), preserves AND reports target-only members, reports an
  unresolvable member as a `DroppedItemRecord`, and writes nothing once the
  sequence is complete.
- Preview's "Repair" rows equal Move's rewrites (one classifier).

Offline: duck-typed fakes only.
"""
from __future__ import annotations

from gramtrans.Lib import categories, preview, transfer
from gramtrans.Lib.models import (
    DroppedItemRecord,
    GrammarCategory,
    PlannedAction,
    RunContext,
    Selection,
    SkipReason,
)


# ============================================================================
# Fakes
# ============================================================================

class _Seq:
    """A .NET-IList-shaped reference sequence that counts its mutations."""

    def __init__(self, items=()) -> None:
        self.items = list(items)
        self.mutations = 0

    def __iter__(self):
        return iter(list(self.items))

    def Add(self, obj) -> None:
        self.items.append(obj)
        self.mutations += 1

    def Insert(self, i, obj) -> None:
        self.items.insert(i, obj)
        self.mutations += 1

    def RemoveAt(self, i) -> None:
        del self.items[i]
        self.mutations += 1


class _Name:
    def __init__(self, text) -> None:
        self.text = text


class _Defn:
    def __init__(self, guid: str, name: str = "") -> None:
        self.guid = guid
        self.ClassName = "FsClosedFeature"
        self.Name = None
        self.label = name


class _Type:
    def __init__(self, guid: str, members=()) -> None:
        self.guid = guid
        self.ClassName = "FsFeatStrucType"
        self.FeaturesRS = _Seq(members)
        self.Name = None


class _NS:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class _Proj:
    """`Cache.LangProject.{Ms,Ph}FeatureSystemOA.{FeaturesOC,TypesOC}`."""

    def __init__(self, ms_feats=(), ms_types=(), ph_feats=(), ph_types=()) -> None:
        self.ms = _NS(FeaturesOC=list(ms_feats), TypesOC=list(ms_types))
        self.ph = _NS(FeaturesOC=list(ph_feats), TypesOC=list(ph_types))
        self.Cache = _NS(LangProject=_NS(MsFeatureSystemOA=self.ms,
                                         PhFeatureSystemOA=self.ph))


def _ctx(source, target, refs=None) -> RunContext:
    ctx = RunContext(
        source_handle=source,
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20261030-020000",
        started_at="2026-10-30T02:00:00",
    )
    if refs is not None:
        object.__setattr__(ctx, "_struct_type_feature_refs", refs)
    object.__setattr__(ctx, "_dropped", [])
    return ctx


A, B, C, X = "a-guid", "b-guid", "c-guid", "x-guid"
T1, T2, P1 = "t1-guid", "t2-guid", "p1-guid"


def _ref(members, system="ms", label="T"):
    return {"system": system, "label": label,
            "members": tuple((m, m.upper()) for m in members)}


def _guids(seq):
    return [d.guid for d in seq]


def _action(cat, guid):
    return PlannedAction(category=cat, source_guid=guid,
                         intended_target_guid=guid, summary="x")


# ============================================================================
# Classifier / ordering policy
# ============================================================================

class TestClassifier:

    def test_complete_when_source_order_already_present(self) -> None:
        a, b = _Defn(A), _Defn(B)
        tgt = _Proj(ms_feats=[a, b], ms_types=[_Type(T1, [a, b])])
        out = categories._classify_struct_type_features_rs(
            tgt, "ms", T1, _ref([A, B])["members"])
        assert out[0] == categories.FEATURES_RS_COMPLETE

    def test_target_only_member_anywhere_is_still_complete(self) -> None:
        a, b, x = _Defn(A), _Defn(B), _Defn(X)
        tgt = _Proj(ms_feats=[a, b, x], ms_types=[_Type(T1, [a, x, b])])
        outcome, _t, _d, unresolved, target_only = (
            categories._classify_struct_type_features_rs(
                tgt, "ms", T1, _ref([A, B])["members"]))
        assert outcome == categories.FEATURES_RS_COMPLETE
        assert target_only == (X,) and unresolved == ()

    def test_missing_member_is_repair_with_target_only_last(self) -> None:
        a, b, x = _Defn(A), _Defn(B), _Defn(X)
        tgt = _Proj(ms_feats=[a, b, x], ms_types=[_Type(T1, [x])])
        outcome, _t, desired, _u, target_only = (
            categories._classify_struct_type_features_rs(
                tgt, "ms", T1, _ref([A, B])["members"]))
        assert outcome == categories.FEATURES_RS_REPAIR
        assert desired == (A, B, X) and target_only == (X,)

    def test_out_of_order_is_repair(self) -> None:
        a, b = _Defn(A), _Defn(B)
        tgt = _Proj(ms_feats=[a, b], ms_types=[_Type(T1, [b, a])])
        outcome, _t, desired, _u, _o = categories._classify_struct_type_features_rs(
            tgt, "ms", T1, _ref([A, B])["members"])
        assert outcome == categories.FEATURES_RS_REPAIR and desired == (A, B)

    def test_unresolved_member_reported_not_repair_when_rest_ordered(self) -> None:
        b = _Defn(B)
        tgt = _Proj(ms_feats=[b], ms_types=[_Type(T1, [b])])
        outcome, _t, _d, unresolved, _o = (
            categories._classify_struct_type_features_rs(
                tgt, "ms", T1, _ref([A, B])["members"]))
        assert outcome == categories.FEATURES_RS_COMPLETE
        assert unresolved == ((A, "A-GUID"),)

    def test_planned_features_count_as_present_in_preview(self) -> None:
        tgt = _Proj(ms_types=[_Type(T1)])
        outcome, _t, desired, unresolved, _o = (
            categories._classify_struct_type_features_rs(
                tgt, "ms", T1, _ref([A, B])["members"],
                planned_feat_guids=frozenset({A, B})))
        assert outcome == categories.FEATURES_RS_REPAIR
        assert desired == (A, B) and unresolved == ()

    def test_absent_type_is_out_of_scope_unless_planned(self) -> None:
        tgt = _Proj()
        assert categories._classify_struct_type_features_rs(
            tgt, "ms", T1, _ref([A])["members"])[0] == \
            categories.FEATURES_RS_TYPE_ABSENT
        assert categories._classify_struct_type_features_rs(
            tgt, "ms", T1, _ref([A])["members"],
            planned_type_guids=frozenset({T1}))[0] == \
            categories.FEATURES_RS_CREATE_WIRED

    def test_phon_system_is_read_from_ph_feature_system(self) -> None:
        a = _Defn(A)
        tgt = _Proj(ph_feats=[a], ph_types=[_Type(P1)],
                    ms_feats=[a], ms_types=[_Type(P1, [a])])
        outcome, _t, desired, _u, _o = categories._classify_struct_type_features_rs(
            tgt, "ph", P1, _ref([A], "ph")["members"])
        assert outcome == categories.FEATURES_RS_REPAIR and desired == (A,)


# ============================================================================
# Move pass
# ============================================================================

class TestMovePass:

    def _run(self, tgt, refs):
        ctx = _ctx(_Proj(), tgt, refs)
        skips = categories._run_struct_type_features_rs_pass(ctx, tgt)
        return ctx, skips

    def test_repairs_empty_sequence_in_source_order(self) -> None:
        a, b, c = _Defn(A), _Defn(B), _Defn(C)
        t1 = _Type(T1)
        tgt = _Proj(ms_feats=[c, b, a], ms_types=[t1])
        ctx, skips = self._run(tgt, {T1: _ref([A, B, C])})
        assert _guids(t1.FeaturesRS) == [A, B, C]
        assert ctx._struct_type_features_rs_writes == 1
        assert skips == [] and ctx._dropped == []

    def test_rebuild_not_append_fixes_partial_create(self) -> None:
        # Create-time target held only B; A arrived later. Append would give
        # [B, A]; the policy gives source order.
        a, b = _Defn(A), _Defn(B)
        t1 = _Type(T1, [b])
        tgt = _Proj(ms_feats=[a, b], ms_types=[t1])
        self._run(tgt, {T1: _ref([A, B])})
        assert _guids(t1.FeaturesRS) == [A, B]

    def test_target_only_member_preserved_and_reported(self) -> None:
        a, b, x = _Defn(A), _Defn(B), _Defn(X)
        t1 = _Type(T1, [x])
        tgt = _Proj(ms_feats=[a, b, x], ms_types=[t1])
        ctx, skips = self._run(tgt, {T1: _ref([A, B])})
        assert _guids(t1.FeaturesRS) == [A, B, X]
        assert len(skips) == 1
        assert skips[0].reason == SkipReason.NEEDS_MANUAL
        assert skips[0].category == GrammarCategory.FEATURE_STRUCT_TYPES
        assert skips[0].source_guid == T1 and X in skips[0].detail

    def test_second_run_writes_nothing_but_still_reports_target_only(self) -> None:
        a, b, x = _Defn(A), _Defn(B), _Defn(X)
        t1 = _Type(T1, [x])
        tgt = _Proj(ms_feats=[a, b, x], ms_types=[t1])
        self._run(tgt, {T1: _ref([A, B])})
        before = t1.FeaturesRS.mutations
        ctx2, skips2 = self._run(tgt, {T1: _ref([A, B])})
        assert t1.FeaturesRS.mutations == before
        assert ctx2._struct_type_features_rs_writes == 0
        assert [s.reason for s in skips2] == [SkipReason.NEEDS_MANUAL]

    def test_unresolved_member_is_a_drop_record(self) -> None:
        b = _Defn(B)
        t1 = _Type(T1)
        tgt = _Proj(ms_feats=[b], ms_types=[t1])
        ctx, skips = self._run(tgt, {T1: _ref([A, B], label="Noun agr")})
        assert _guids(t1.FeaturesRS) == [B]
        assert len(ctx._dropped) == 1
        d = ctx._dropped[0]
        assert isinstance(d, DroppedItemRecord)
        assert (d.owner_kind, d.owner_guid, d.owner_label, d.field_name,
                d.item_guid, d.item_name) == (
            "FsFeatStrucType", T1, "Noun agr", "FeaturesRS", A, "A-GUID")
        assert "inflection_features" in d.reason

    def test_phon_target_only_skip_uses_phon_category(self) -> None:
        a, x = _Defn(A), _Defn(X)
        p1 = _Type(P1, [x])
        tgt = _Proj(ph_feats=[a, x], ph_types=[p1])
        ctx, skips = self._run(tgt, {P1: _ref([A], "ph")})
        assert _guids(p1.FeaturesRS) == [A, X]
        assert skips[0].category == GrammarCategory.PHON_FEAT_TYPES

    def test_absent_type_is_ignored(self) -> None:
        ctx, skips = self._run(_Proj(), {T1: _ref([A])})
        assert skips == [] and ctx._dropped == []
        assert ctx._struct_type_features_rs_writes == 0

    def test_ensure_runs_with_zero_actions_latches_and_folds_skips(self) -> None:
        a, x = _Defn(A), _Defn(X)
        t1 = _Type(T1, [x])
        tgt = _Proj(ms_feats=[a, x], ms_types=[t1])
        ctx = _ctx(_Proj(), tgt)
        plan = _NS(struct_type_feature_refs={T1: _ref([A])}, actions=())
        object.__setattr__(ctx, "_run_plan", plan)
        out: list = []
        transfer._ensure_struct_type_features_rs(ctx, tgt, out)
        assert _guids(t1.FeaturesRS) == [A, X]
        assert [s.reason for s in out] == [SkipReason.NEEDS_MANUAL]
        transfer._ensure_struct_type_features_rs(ctx, tgt, out)  # latched
        assert len(out) == 1


# ============================================================================
# Preview gather + render (Principle III)
# ============================================================================

class TestPreview:

    def test_gather_records_present_and_planned_types_only(self) -> None:
        a, b = _Defn(A), _Defn(B)
        src = _Proj(ms_feats=[a, b], ms_types=[_Type(T1, [a, b]),
                                               _Type(T2, [b])])
        tgt = _Proj(ms_types=[_Type(T1)])
        sel = Selection(categories={GrammarCategory.INFLECTION_FEATURES: True})
        refs = categories.gather_struct_type_feature_refs(
            _ctx(src, tgt), sel, ())
        assert set(refs) == {T1}  # T2 neither present nor planned
        assert refs[T1]["system"] == "ms"
        assert [m for m, _ in refs[T1]["members"]] == [A, B]

    def test_gather_includes_closure_pulled_type_with_category_off(self) -> None:
        a = _Defn(A)
        src = _Proj(ms_feats=[a], ms_types=[_Type(T1, [a])])
        sel = Selection(categories={GrammarCategory.AFFIXES: True})
        refs = categories.gather_struct_type_feature_refs(
            _ctx(src, _Proj()), sel,
            [_action(GrammarCategory.FEATURE_STRUCT_TYPES, T1)])
        assert set(refs) == {T1}

    def test_gather_out_of_scope_system_records_nothing(self) -> None:
        a = _Defn(A)
        src = _Proj(ms_feats=[a], ms_types=[_Type(T1, [a])],
                    ph_feats=[a], ph_types=[_Type(P1, [a])])
        tgt = _Proj(ms_types=[_Type(T1)], ph_types=[_Type(P1)])
        sel = Selection(categories={GrammarCategory.PHON_FEAT_TYPES: True})
        refs = categories.gather_struct_type_feature_refs(_ctx(src, tgt), sel, ())
        assert set(refs) == {P1}

    def test_preview_repair_rows_equal_move_writes(self) -> None:
        a, b, x = _Defn(A), _Defn(B), _Defn(X)
        t1, t2 = _Type(T1, [x]), _Type(T2, [a])
        tgt = _Proj(ms_feats=[a, b, x], ms_types=[t1, t2])
        refs = {T1: _ref([A, B]), T2: _ref([A]), "t3-guid": _ref([C])}
        ctx = _ctx(_Proj(), tgt, refs)
        plan = _NS(struct_type_feature_refs=refs, actions=(),
                   context=_NS(target_handle=tgt), reversal_decisions=(),
                   config_view_records=(), feature_category_links={},
                   complex_feature_type_refs={})
        rows = preview.render_struct_type_features_rs(plan)
        extra = preview.render_preview_extra_lines(plan)
        repair_rows = [r for r in rows if r.strip().startswith("Repair")]
        categories._run_struct_type_features_rs_pass(ctx, tgt)
        assert len(repair_rows) == ctx._struct_type_features_rs_writes == 1
        assert any("SKIP (already complete)" in r and T2 in r for r in rows)
        assert any("target-only member kept" in r and X in r for r in rows)
        assert not any("t3-guid" in r for r in rows)  # absent -> silent
        assert tuple(extra[-len(rows):]) == tuple(rows)

    def test_planned_create_is_wire_at_create_not_repair(self) -> None:
        tgt = _Proj()
        refs = {T1: _ref([A, B])}
        plan = _NS(struct_type_feature_refs=refs, context=_NS(target_handle=tgt),
                   actions=(_action(GrammarCategory.INFLECTION_FEATURES, A),
                            _action(GrammarCategory.FEATURE_STRUCT_TYPES, T1)))
        rows = preview.render_struct_type_features_rs(plan)
        assert any(r.strip().startswith("Wire at create") for r in rows)
        assert any("member feature unavailable" in r and B in r for r in rows)
        assert not any(r.strip().startswith("Repair") for r in rows)

    def test_preview_drops_match_move_drops(self) -> None:
        t1 = _Type(T1)
        tgt = _Proj(ms_types=[t1])
        refs = {T1: _ref([A, B])}
        preview_dropped: list = []
        categories.plan_struct_type_features_rs_drops(
            refs, tgt, [_action(GrammarCategory.INFLECTION_FEATURES, A)],
            preview_dropped)
        assert [d.item_guid for d in preview_dropped] == [B]
        # Move: A was created by the run, B still missing.
        tgt.ms.FeaturesOC.append(_Defn(A))
        ctx = _ctx(_Proj(), tgt, refs)
        categories._run_struct_type_features_rs_pass(ctx, tgt)
        assert [d.item_guid for d in ctx._dropped] == [B]

    def test_empty_refs_render_nothing(self) -> None:
        plan = _NS(struct_type_feature_refs={}, actions=(),
                   context=_NS(target_handle=_Proj()))
        assert preview.render_struct_type_features_rs(plan) == ()
