"""Issue #129 -- the possibility CREATE arm must never hand a plain string to
`ApplySyncableProperties` (it `setattr`s it onto a read-only multistring and
raises `TypeError: property is read-only`), must not swallow a failing apply,
and the divergence fingerprint must ignore GramTrans import residue (the real
cause of Move 2 deciding UPDATE for items Move 1 created)."""
from __future__ import annotations

import types

from gramtrans.Lib import references
from gramtrans.Lib.models import (
    ReferenceAction, ReferenceCardinality, ReferenceDecision, ReferenceFieldSpec,
)

from test_reference_create_paths import (
    _FakeFactory, _FakeTypedTargetList, _install_fake_lcm,
)


class _MS:
    """Duck-typed multistring: `{handle: text}`."""

    def __init__(self, data):
        self._data = dict(data)


class _Src:
    def __init__(self, guid, **fields):
        self.Guid = guid
        self.guid = guid
        self.Name = _MS(fields.get("Name", {1: "N"}))
        self.Abbreviation = _MS(fields.get("Abbreviation", {}))
        self.Description = _MS(fields.get("Description", {}))


class _WS:
    def __init__(self, ws_id, handle):
        self.Id, self.Handle = ws_id, handle


class _Ops:
    def __init__(self, raises=None):
        self.calls = []
        self.raises = raises
        self.project = types.SimpleNamespace(
            WritingSystems=types.SimpleNamespace(
                GetAll=lambda: [_WS("fr", 5), _WS("en", 7)]),
            GetDefaultAnalysisWSHandle=lambda: 7,
        )

    def ApplySyncableProperties(self, item, props, ws_map=None):
        self.calls.append(props)
        if self.raises:
            raise self.raises


class _Target:
    def __init__(self, ops):
        self.PossibilityLists = ops
        self.Cache = types.SimpleNamespace(DefaultAnalWs=7)

    def GetFactory(self, key):
        return _FakeFactory()


def _run(monkeypatch, src, ops):
    _install_fake_lcm(monkeypatch)
    from gramtrans.Lib import residue as residue_mod
    monkeypatch.setattr(residue_mod, "apply_residue", lambda *a, **k: None)
    spec = ReferenceFieldSpec(
        owner_class="LexSense", field_name="ThesaurusItemsRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda t: _FakeTypedTargetList(7), hierarchical=True)
    decision = ReferenceDecision(
        action=ReferenceAction.CREATE, ancestors_to_create=(src,), source_item=src)
    dropped = []
    references.apply_reference(decision, _Target(ops), None, spec, {}, tag=None,
                               dropped=dropped)
    return dropped


def _no_plain_strings(props):
    return all(isinstance(v, dict) for v in props.values())


def test_empty_plain_description_is_skipped_never_passed_as_str(monkeypatch):
    ops = _Ops()
    dropped = _run(monkeypatch, _Src("a" * 8 + "-1111-1111-1111-" + "1" * 12,
                                     Name={7: "x"}), ops)
    props = ops.calls[0]
    assert "Description" not in props and _no_plain_strings(props)
    assert dropped == []


def test_nonempty_plain_string_is_wrapped_as_ws_dict(monkeypatch):
    """No source WS resolves in the target -> the best-alt text falls back to
    a `{target default WS id: text}` dict, never a bare str."""
    ops = _Ops()
    src = _Src("b" * 8 + "-2222-2222-2222-" + "2" * 12, Name={99: "Plain"})
    _run(monkeypatch, src, ops)
    props = ops.calls[0]
    assert _no_plain_strings(props)
    assert "Plain" in props["Name"].values()
    assert set(props["Name"]) <= {"en", "fr"}


def test_wrap_plain_text_uses_default_analysis_ws():
    ops = _Ops()
    assert references._wrap_plain_text("t", ops, {"fr": 5, "en": 7}) == {"en": "t"}
    assert references._wrap_plain_text("", ops, {"en": 7}) == {}
    assert references._wrap_plain_text("t", ops, {}) == {}


def test_raising_apply_is_recorded_not_swallowed(monkeypatch):
    ops = _Ops(raises=TypeError("property is read-only"))
    src = _Src("c" * 8 + "-3333-3333-3333-" + "3" * 12, Name={7: "Boom"})
    dropped = _run(monkeypatch, src, ops)
    assert len(dropped) == 1
    assert "property is read-only" in dropped[0].reason
    assert dropped[0].field_name == "ThesaurusItemsRC"


def test_fingerprint_ignores_import_residue_in_description():
    tag = "\n[GT-Tag]: GT|GT-20261031-015844|GT-Src-42|2026-10-31T01:58:44"
    src = _Src("d" * 8 + "-4444-4444-4444-" + "4" * 12, Name={1: "n"})
    tgt = _Src("d" * 8 + "-4444-4444-4444-" + "4" * 12, Name={1: "n"},
               Description={1: tag})
    assert references.divergence_fingerprint(src) == references.divergence_fingerprint(tgt)
    real = _Src("e" * 8 + "-5555-5555-5555-" + "5" * 12, Name={1: "n"},
                Description={1: "real text" + "\n" + tag})
    assert references.divergence_fingerprint(src) != references.divergence_fingerprint(real)
