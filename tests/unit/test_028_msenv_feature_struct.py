"""Unit tests for feature 028 (Affix-Allomorph Morphosyntax Fidelity):
reproduction of the `MoAffixAllomorph.MsEnvFeaturesOA` owned feature structure
(US3) — deep-copy of the owned `IFsFeatStruc` with its feature-value
specifications resolved against the target feature system (reusing feature
031's closed-feature machinery), reporting unresolvable/complex values.

See:
- specs/028-affix-allomorph-morphosyntax/spec.md (US3)
- specs/028-affix-allomorph-morphosyntax/research.md (R3)
- specs/028-affix-allomorph-morphosyntax/contracts/affix-msenv-reproduction.md

T010 (Phase 5) authors the RED-before-GREEN deep-copy tests below; T011
implements the `_reproduce_msenv_features_oa` / `_plan_msenv_features_oa` legs
that turn them green. Everything runs OFFLINE against duck-typed fakes.
"""

from gramtrans.Lib import owned
from gramtrans.Lib.models import ReferenceAction


def test_028_msenv_features_dispatch_present():
    """The MsEnvFeaturesOA leg is reproduced through the shared 028 dispatch
    seam. Import-smoke: the dispatch entry points exist."""
    assert callable(owned.reproduce_moaffix_msenv_data)
    assert callable(owned._plan_moaffix_msenv_decisions)


# ============================================================================
# Duck-typed fakes for the MsEnvFeaturesOA leg (US3).
#
# These model the minimal live surface the leg touches:
#   - a source `IFsFeatStruc` (`MsEnvFeaturesOA`) with `FeatureSpecsOC` of
#     `IFsClosedValue`, each carrying `FeatureRA` (-> IFsClosedFeature) and
#     `ValueRA` (-> IFsSymFeatVal);
#   - a target project whose feature system
#     (`Cache.LangProject.MsFeatureSystemOA.FeaturesOC`) holds the equivalent
#     `IFsClosedFeature`s (each with `.ValuesOC` of `IFsSymFeatVal`) resolvable
#     by GUID -- feature 031's closed-feature machinery;
#   - `GetService`-keyed `IFsFeatStrucFactory` / `IFsClosedValueFactory`
#     doubles (the owned.py `_get_owned_factory` string-key fallback), each
#     `Create(guid=None)` returning a fresh fake struct/closed-value.
# The allomorph carries `ClassName == "MoAffixAllomorph"` so
# `owned._is_moaffix_allomorph` gates it in.
# ============================================================================


class _FakeGuid:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeAddList(list):
    """List that also exposes the LCM-direct `.Add()` used to populate
    read-only-through-wrapper owned collections (FeatureSpecsOC/ValuesOC)."""

    def Add(self, item):
        self.append(item)


class _FakeSymFeatVal(_FakeGuid):
    ClassName = "FsSymFeatVal"


class _FakeClosedFeature(_FakeGuid):
    """A closed feature: exposes `.ValuesOC` (the marker the leg uses to tell a
    closed feature from a complex/open one)."""

    ClassName = "FsClosedFeature"

    def __init__(self, guid, values=()):
        super().__init__(guid)
        self.ValuesOC = _FakeAddList(values)


class _FakeComplexFeature(_FakeGuid):
    """A non-closed (complex/open) feature -- no `.ValuesOC`, so the leg treats
    it as out of scope (report, never reproduce)."""

    ClassName = "FsComplexFeature"


class _FakeClosedValue(_FakeGuid):
    ClassName = "FsClosedValue"

    def __init__(self, guid, feature=None, value=None):
        super().__init__(guid)
        self.FeatureRA = feature
        self.ValueRA = value


class _FakeFeatStruc(_FakeGuid):
    ClassName = "FsFeatStruc"

    def __init__(self, guid, specs=()):
        super().__init__(guid)
        self.FeatureSpecsOC = _FakeAddList(specs)


class _FakeFeatStrucFactory:
    def __init__(self):
        self.create_calls = []

    def Create(self, guid=None):
        self.create_calls.append(str(guid) if guid is not None else None)
        return _FakeFeatStruc(str(guid) if guid is not None else "new-fs")


class _FakeClosedValueFactory:
    def __init__(self):
        self.create_calls = []

    def Create(self, guid=None):
        self.create_calls.append(str(guid) if guid is not None else None)
        return _FakeClosedValue(str(guid) if guid is not None else "new-cv")


class _FakeFeatureSystem:
    def __init__(self, features=()):
        self.FeaturesOC = _FakeAddList(features)


class _FakeLangProject:
    def __init__(self, feature_system):
        self.MsFeatureSystemOA = feature_system


class _FakeCache:
    def __init__(self, feature_system):
        self.LangProject = _FakeLangProject(feature_system)
        self.DefaultAnalWs = 0


class _FakeTarget:
    def __init__(self, features=(), with_factories=True):
        self.Cache = _FakeCache(_FakeFeatureSystem(features))
        self._factories: dict = {}
        if with_factories:
            self._factories["IFsFeatStrucFactory"] = _FakeFeatStrucFactory()
            self._factories["IFsClosedValueFactory"] = _FakeClosedValueFactory()

    def GetService(self, name):
        key = name if isinstance(name, str) else getattr(name, "__name__", str(name))
        if key in self._factories:
            return self._factories[key]
        raise KeyError(key)


class _FakeSource:
    """Bare source handle -- the leg reads off the source allomorph object."""


class _FakeAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_features=None):
        super().__init__(guid)
        self.MsEnvFeaturesOA = msenv_features


class _FakeNewAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_features=None):
        super().__init__(guid)
        self.MsEnvFeaturesOA = msenv_features


class _FakeCtx:
    def __init__(self, target, source=None):
        self.source_handle = source or _FakeSource()
        self.target_handle = target


_TAG = "tag-028-msenv-feat"


def _target_with_closed(feat_guid, val_guid, with_factories=True):
    """Build a target whose feature system resolves (feat_guid, val_guid) as a
    closed feature/value. Returns `(target, tgt_feat, tgt_val)`."""
    tgt_val = _FakeSymFeatVal(val_guid)
    tgt_feat = _FakeClosedFeature(feat_guid, values=[tgt_val])
    target = _FakeTarget(features=[tgt_feat], with_factories=with_factories)
    return target, tgt_feat, tgt_val


def _src_spec(cv_guid, feat_guid, val_guid):
    """A source `IFsClosedValue`-shaped spec referencing feature/value by GUID
    (the GUIDs feature 031 preserved into the target)."""
    return _FakeClosedValue(
        cv_guid, feature=_FakeClosedFeature(feat_guid),
        value=_FakeSymFeatVal(val_guid))


# ============================================================================
# T010 (US3) -- MsEnvFeaturesOA deep-copy reproduction (owned IFsFeatStruc).
# ============================================================================


def test_msenv_features_deep_copy_resolvable_value():
    """Target feature system holds the equivalent feature+value by GUID -> the
    new allomorph owns a deep-copied `IFsFeatStruc` (a NEW object, not the
    source struct) whose spec references the RESOLVED target feature/value;
    nothing dropped (G1/G2)."""
    target, tgt_feat, tgt_val = _target_with_closed("feat-1", "val-1")
    src_fs = _FakeFeatStruc("fs-1", specs=[_src_spec("cv-1", "feat-1", "val-1")])
    src_allo = _FakeAffixAllomorph("allo-1", msenv_features=src_fs)
    new_allo = _FakeNewAffixAllomorph("allo-1")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    new_fs = new_allo.MsEnvFeaturesOA
    assert new_fs is not None
    assert new_fs is not src_fs  # deep copy, not the source object
    new_specs = list(new_fs.FeatureSpecsOC)
    assert len(new_specs) == 1
    assert new_specs[0].FeatureRA is tgt_feat
    assert new_specs[0].ValueRA is tgt_val
    assert dropped == []


def test_msenv_features_partial_fidelity_drops_unresolvable_value():
    """A structure with one resolvable spec and one whose value GUID is absent
    from the target feature system -> the resolvable spec is STILL reproduced
    AND a `DroppedItemRecord(field_name="MsEnvFeaturesOA")` is emitted for the
    unresolvable one (partial fidelity, never silent -- G1/INV-3)."""
    target, _tgt_feat, tgt_val = _target_with_closed("feat-ok", "val-ok")
    resolvable = _src_spec("cv-ok", "feat-ok", "val-ok")
    unresolvable = _src_spec("cv-bad", "feat-ok", "val-missing")
    src_fs = _FakeFeatStruc("fs-2", specs=[resolvable, unresolvable])
    src_allo = _FakeAffixAllomorph("allo-2", msenv_features=src_fs)
    new_allo = _FakeNewAffixAllomorph("allo-2")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    new_specs = list(new_allo.MsEnvFeaturesOA.FeatureSpecsOC)
    assert [s.ValueRA for s in new_specs] == [tgt_val]  # only resolvable
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "MsEnvFeaturesOA"
    assert rec.owner_kind == "MoAffixAllomorph"
    assert rec.owner_guid == "allo-2"
    assert rec.item_guid == "val-missing"


def test_msenv_features_complex_feature_reported_no_empty_struct():
    """The referenced feature is complex/open (non-closed) in the target ->
    the value is REPORT_DROPPED (out of scope); with no resolvable spec
    remaining, NO structure is created (never an empty structure -- INV-2)."""
    complex_feat = _FakeComplexFeature("feat-complex")
    target = _FakeTarget(features=[complex_feat])
    src_fs = _FakeFeatStruc(
        "fs-cx", specs=[_src_spec("cv-cx", "feat-complex", "val-cx")])
    src_allo = _FakeAffixAllomorph("allo-cx", msenv_features=src_fs)
    new_allo = _FakeNewAffixAllomorph("allo-cx")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert new_allo.MsEnvFeaturesOA is None  # never an empty structure
    assert len(dropped) == 1
    assert dropped[0].field_name == "MsEnvFeaturesOA"
    assert dropped[0].item_guid == "val-cx"


def test_msenv_features_empty_source_noop_does_not_blank_target():
    """Source `MsEnvFeaturesOA is None` -> no structure created; a populated
    target field is NOT blanked; nothing dropped (FR-005/G2/INV-2)."""
    target, _f, _v = _target_with_closed("f", "v")
    existing = _FakeFeatStruc("fs-existing")
    src_allo = _FakeAffixAllomorph("allo-3", msenv_features=None)
    new_allo = _FakeNewAffixAllomorph("allo-3", msenv_features=existing)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert new_allo.MsEnvFeaturesOA is existing  # not blanked
    assert dropped == []


def test_msenv_features_empty_specs_source_noop():
    """Source struct present but with NO feature specs -> no-op: never create
    an empty structure on the target, nothing dropped (INV-2)."""
    target = _FakeTarget(features=[])
    src_allo = _FakeAffixAllomorph(
        "allo-4", msenv_features=_FakeFeatStruc("fs-empty", specs=[]))
    new_allo = _FakeNewAffixAllomorph("allo-4")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert new_allo.MsEnvFeaturesOA is None
    assert dropped == []


def test_msenv_features_preview_move_parity():
    """Preview twin's decisions/drops match the Move outcome for the same
    inputs (G6/INV-6): resolvable -> a LINK decision for MsEnvFeaturesOA;
    unresolvable -> a drop record (no decision); empty source -> neither."""
    # Resolvable -> LINK decision, nothing dropped.
    target, _f, _v = _target_with_closed("pf", "pv")
    src_fs = _FakeFeatStruc("pfs", specs=[_src_spec("pcv", "pf", "pv")])
    dropped: list = []
    recs = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("pa", msenv_features=src_fs),
        _FakeCtx(target), {}, dropped)
    feat_recs = [r for r in recs if r.field_name == "MsEnvFeaturesOA"]
    assert len(feat_recs) == 1
    assert feat_recs[0].action == ReferenceAction.LINK
    assert not [r for r in dropped if r.field_name == "MsEnvFeaturesOA"]

    # Unresolvable -> a drop, no decision.
    target2 = _FakeTarget(features=[])
    src_fs2 = _FakeFeatStruc("pfs2", specs=[_src_spec("pcv2", "pf2", "pv2")])
    dropped2: list = []
    recs2 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("pb", msenv_features=src_fs2),
        _FakeCtx(target2), {}, dropped2)
    assert not [r for r in recs2 if r.field_name == "MsEnvFeaturesOA"]
    assert any(r.field_name == "MsEnvFeaturesOA" for r in dropped2)

    # Empty source -> no decision, no drop.
    target3 = _FakeTarget(features=[])
    dropped3: list = []
    recs3 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("pc", msenv_features=None),
        _FakeCtx(target3), {}, dropped3)
    assert not [r for r in recs3 if r.field_name == "MsEnvFeaturesOA"]
    assert dropped3 == []
