"""Issue #132: complex-feature TypeRA tail must not swallow setattr failures."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory, RunContext, SkipReason


class _FakeType:
    def __init__(self, guid: str) -> None:
        self.guid = guid.lower()
        self.ClassName = "FsFeatStrucType"


class _FakeComplexFeat:
    def __init__(self, guid: str, type_ra=None) -> None:
        self.guid = guid.lower()
        self.ClassName = "FsComplexFeature"
        self.TypeRA = type_ra


class _RejectTypeRAFeat(_FakeComplexFeat):
    def __init__(self, guid: str, type_ra=None) -> None:
        object.__setattr__(self, "guid", guid.lower())
        object.__setattr__(self, "ClassName", "FsComplexFeature")
        object.__setattr__(self, "TypeRA", type_ra)

    def __setattr__(self, name, value):
        if name == "TypeRA":
            raise TypeError("TypeRA setattr binding failed")
        object.__setattr__(self, name, value)


class _NS:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class _FakeTarget:
    def __init__(self, features=(), types=()) -> None:
        self.fs = _NS(FeaturesOC=list(features), TypesOC=list(types))
        self.Cache = _NS(LangProject=_NS(MsFeatureSystemOA=self.fs))


F1, T1 = "f1-guid", "t1-guid"


def _ctx(target, refs, dropped=None) -> RunContext:
    ctx = RunContext(
        source_handle=object(),
        source_project_name="SrcProj",
        source_project_path="/src",
        target_handle=target,
        target_project_name="TgtProj",
        target_project_path="/tgt",
        run_id="GT-20261103-010000",
        started_at="2026-11-03T01:00:00",
    )
    object.__setattr__(ctx, "_complex_feature_type_refs", dict(refs))
    if dropped is not None:
        object.__setattr__(ctx, "_dropped", dropped)
    return ctx


def test_type_ra_setattr_failure_emits_skip_and_drop() -> None:
    t1 = _FakeType(T1)
    feat = _RejectTypeRAFeat(F1)
    target = _FakeTarget([feat], [t1])
    dropped: list = []
    ctx = _ctx(target, {F1: T1}, dropped=dropped)

    skips = categories._run_complex_feature_type_ra_pass(ctx, target)

    assert feat.TypeRA is None
    assert ctx._complex_type_ra_writes == 0
    assert len(skips) == 1
    assert skips[0].reason == SkipReason.NOT_REPRODUCIBLE
    assert skips[0].source_guid == F1
    assert "WRITE_FAILED" in skips[0].detail
    assert len(dropped) == 1
    assert dropped[0].field_name == "TypeRA"
    assert dropped[0].owner_guid == F1


def test_type_ra_no_op_readback_emits_skip() -> None:
    """Add succeeds but TypeRA stays null — must not count as a write."""

    class _NoOpSetattrFeat(_FakeComplexFeat):
        def __init__(self, guid: str, type_ra=None) -> None:
            object.__setattr__(self, "guid", guid.lower())
            object.__setattr__(self, "ClassName", "FsComplexFeature")
            object.__setattr__(self, "TypeRA", type_ra)

        def __setattr__(self, name, value):
            if name == "TypeRA":
                return
            object.__setattr__(self, name, value)

    t1 = _FakeType(T1)
    feat = _NoOpSetattrFeat(F1)
    target = _FakeTarget([feat], [t1])
    ctx = _ctx(target, {F1: T1})

    skips = categories._run_complex_feature_type_ra_pass(ctx, target)

    assert feat.TypeRA is None
    assert ctx._complex_type_ra_writes == 0
    assert len(skips) == 1
    assert "read-back" in skips[0].detail
