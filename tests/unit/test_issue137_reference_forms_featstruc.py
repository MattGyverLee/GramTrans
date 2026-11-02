"""Issue #137 -- a `ReferenceFormsOC` `IFsFeatStruc` is copied WITH its type and
feature specifications (target-side GUID remapping), not created as an empty
shell. Hermetic: reuses the fakes of `test_038_enrichment_executor.py`."""
from __future__ import annotations

from types import SimpleNamespace

import test_038_enrichment_executor as base
from test_038_enrichment_executor import (  # noqa: F401 -- autouse fixtures
    _offline_tsstrings,
    _patch_guid,
)

from gramtrans.Lib import transfer


class _Obj:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid


class _Spec(_Obj):
    def __init__(self, guid, feat, val):
        super().__init__(guid)
        self.FeatureRA = feat
        self.ValueRA = val


class _Struc(base._FakeChild):
    def __init__(self, guid, type_obj=None, specs=()):
        super().__init__(guid)
        self.TypeRA = type_obj
        self.FeatureSpecsOC = base._FakeOwningCollection(specs)


class _StrucFactory(base._FakeFactory):
    """Registers each struc it makes in `registry`, the fake target's
    guid -> object map, so the completion pass can resolve it by GUID."""

    def __init__(self, name, registry):
        super().__init__(name)
        self.registry = registry

    def Create(self, *args):
        self.created_guids.append(args[0] if args else None)
        made = _Struc(str(args[0]) if args else "minted")
        self.registry[made.guid] = made
        return made


def _src_pos(struc):
    return base._FakePOS("pos-1", ReferenceFormsOC=[struc])


def _source_struc():
    return _Struc("fs-1", _Obj("type-1"), [
        _Spec("sp-1", _Obj("feat-1"), _Obj("val-1")),
        _Spec("sp-2", _Obj("feat-2"), _Obj("val-2")),
    ])


def _target_objects(*guids):
    # The target's feature/type objects are DISTINCT instances from the
    # source's: the copy must point at these, not at the source objects.
    return {g: _Obj(g) for g in guids}


def _run(src_pos, tgt_pos, objects, sink=None, dropped=None):
    """Enrichment (creates the empty shell) then the #137 completion pass."""
    factories = base._all_factories()
    made: dict = {}
    factories["IFsFeatStrucFactory"] = _StrucFactory("IFsFeatStrucFactory", made)
    dropped = [] if dropped is None else dropped
    measured, sink, source, target = base._run(
        src_pos, tgt_pos, [("ReferenceFormsOC", 1)], factories=factories,
        objects_by_guid=objects, sink=sink, dropped=dropped)
    target._objects.update(made)        # the fake target "sees" what was created
    plan = SimpleNamespace(
        actions=[], overwrites=[base._overwrite(src_pos.guid, [])])
    transfer._complete_reference_form_structs(
        plan, source, target, sink, dropped)
    return measured, sink, source, target


def test_the_struc_is_copied_with_type_and_specs_remapped_to_the_target():
    objects = _target_objects("type-1", "feat-1", "val-1", "feat-2", "val-2")
    tgt = base._FakePOS("pos-1")
    measured, sink, _s, _t = _run(_src_pos(_source_struc()), tgt, objects)

    (created,) = list(tgt.ReferenceFormsOC)
    assert created.guid == "fs-1"
    assert created.TypeRA is objects["type-1"]
    specs = list(created.FeatureSpecsOC)
    assert [(s.FeatureRA, s.ValueRA) for s in specs] == [
        (objects["feat-1"], objects["val-1"]),
        (objects["feat-2"], objects["val-2"])]
    assert [s.guid for s in specs] == ["sp-1", "sp-2"]
    assert not sink.warning
    assert measured.collections[0].dropped == 0


def test_an_unresolved_endpoint_is_reported_and_leaves_no_half_struc():
    objects = _target_objects("type-1", "feat-1", "val-1", "feat-2")  # no val-2
    tgt = base._FakePOS("pos-1")
    dropped: list = []
    _m, sink, _s, _t = _run(_src_pos(_source_struc()), tgt, objects,
                            dropped=dropped)

    (created,) = list(tgt.ReferenceFormsOC)
    assert list(created.FeatureSpecsOC) == []           # all-or-nothing
    assert any(d.field_name == "ReferenceFormsOC.FeatureSpecsOC"
               and "val-2" in d.reason for d in dropped)
    assert sink.warning


def test_an_empty_source_struc_is_not_a_failure():
    tgt = base._FakePOS("pos-1")
    dropped: list = []
    _m, sink, _s, _t = _run(_src_pos(_Struc("fs-1")), tgt, {}, dropped=dropped)
    assert [c.guid for c in tgt.ReferenceFormsOC] == ["fs-1"]
    assert not dropped and not sink.warning


def test_a_matched_empty_shell_is_completed_and_a_populated_one_is_untouched():
    objects = _target_objects("type-1", "feat-1", "val-1", "feat-2", "val-2")
    shell = _Struc("fs-1")
    objects["fs-1"] = shell
    tgt = base._FakePOS("pos-1", ReferenceFormsOC=[shell])
    _run(_src_pos(_source_struc()), tgt, objects)
    assert shell.TypeRA is objects["type-1"]
    assert len(list(shell.FeatureSpecsOC)) == 2

    # Second run: now populated -> nothing is added, nothing duplicated.
    _run(_src_pos(_source_struc()), tgt, objects)
    assert len(list(shell.FeatureSpecsOC)) == 2
    assert len(list(tgt.ReferenceFormsOC)) == 1

    kept = _Struc("fs-1", None, [_Spec("mine", _Obj("feat-9"), _Obj("val-9"))])
    objects["fs-1"] = kept
    tgt2 = base._FakePOS("pos-1", ReferenceFormsOC=[kept])
    _run(_src_pos(_source_struc()), tgt2, objects)
    assert [s.guid for s in kept.FeatureSpecsOC] == ["mine"]
    assert kept.TypeRA is None


def test_a_run_that_touches_no_pos_category_writes_nothing():
    objects = _target_objects("type-1", "feat-1", "val-1", "feat-2", "val-2")
    shell = _Struc("fs-1")
    objects["fs-1"] = shell
    tgt = base._FakePOS("pos-1", ReferenceFormsOC=[shell])
    source = base._FakeProject([_src_pos(_source_struc())])
    target = base._FakeProject([tgt], objects_by_guid=objects)
    plan = SimpleNamespace(actions=[], overwrites=[])
    transfer._complete_reference_form_structs(plan, source, target, base._Sink())
    assert list(shell.FeatureSpecsOC) == [] and shell.TypeRA is None
