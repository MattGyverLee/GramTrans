"""PR #73 follow-up: simultaneous/scoped .fwdictconfig rewrite, reversal
filename rename, reversal-index reason text, programming errors not becoming
drops. Host-free."""
from __future__ import annotations

import os

import pytest

from gramtrans.Lib import api as api_mod
from gramtrans.Lib import config_views
from gramtrans.Lib import reversals
from gramtrans.Lib.models import ConfigViewAction

import test_ws_path_fidelity as base


def _write(root, body, name="Lexeme.fwdictconfig", sub="Dictionary"):
    d = root / "ConfigurationSettings" / sub
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(body.encode("utf-8"))
    return str(p)


def _opts(*pairs):
    body = "".join(f'<Option id="{i}" isEnabled="{e}" />' for i, e in pairs)
    return ('<DictionaryConfiguration name="x">'
            f'<WritingSystemOptions>{body}</WritingSystemOptions>'
            '</DictionaryConfiguration>')


def test_swap_is_simultaneous(tmp_path):
    p = _write(tmp_path, _opts(("a", "true"), ("b", "false")))
    out = config_views._rewritten_bytes(p, {"a": "b", "b": "a"}).decode()
    assert out == _opts(("b", "true"), ("a", "false"))


def test_chain_is_not_cascaded(tmp_path):
    p = _write(tmp_path, _opts(("a", "true"), ("b", "true")))
    out = config_views._rewritten_bytes(p, {"a": "b", "b": "c"}).decode()
    # Each id is renamed once: old a -> b, old b -> c (never a -> b -> c).
    assert out == _opts(("b", "true"), ("c", "true"))


def test_option_outside_writing_system_options_untouched(tmp_path):
    body = ('<DictionaryConfiguration name="x">'
            '<ListOptions><Option id="a" isEnabled="true" /></ListOptions>'
            '<WritingSystemOptions><Option id="a" isEnabled="true" /></WritingSystemOptions>'
            '</DictionaryConfiguration>')
    p = _write(tmp_path, body)
    out = config_views._rewritten_bytes(p, {"a": "z"}).decode()
    assert '<ListOptions><Option id="a"' in out
    assert '<WritingSystemOptions><Option id="z"' in out


def test_single_quotes_gt_in_value_and_magic_tokens(tmp_path):
    body = ("<DictionaryConfiguration name='x>y' writingSystem='a'>"
            "<WritingSystemOptions>"
            "<Option label='1 > 0' id='a' isEnabled='true' />"
            "<Option id='vernacular' isEnabled='true' />"
            "</WritingSystemOptions></DictionaryConfiguration>")
    p = _write(tmp_path, body)
    out = config_views._rewritten_bytes(p, {"a": "b", "vernacular": "q"}).decode()
    assert "writingSystem='b'" in out
    assert "<Option label='1 > 0' id='b'" in out
    assert "id='vernacular'" in out  # magic token never rewritten


def test_duplicate_collision_is_deduped_and_noted(tmp_path):
    p = _write(tmp_path, _opts(("a", "false"), ("b", "true")))
    data, applied, notes = config_views._rewrite_config(p, {"a": "b"})
    out = data.decode()
    assert out.count("<Option") == 1
    assert 'id="b" isEnabled="true"' in out
    assert applied == {"a"}
    assert len(notes) == 1 and "'b'" in notes[0]

    # Enabled if EITHER was enabled, regardless of order.
    p2 = _write(tmp_path, _opts(("a", "true"), ("b", "false")), name="L2.fwdictconfig")
    out2 = config_views._rewritten_bytes(p2, {"a": "b"}).decode()
    assert out2.count("<Option") == 1 and 'isEnabled="true"' in out2


def test_collision_is_reported_through_plan(tmp_path):
    _write(tmp_path / "Src", _opts(("a", "true"), ("b", "false")))
    src = base._CVProject(tmp_path / "Src", ["a", "b"])
    tgt = base._CVProject(tmp_path / "Tgt", ["b"])
    recs = config_views.plan_config_views(src, tgt, ws_map={"a": "b"})
    assert any("merged" in r.reason for r in recs[0].missing_refs)


def test_unapplied_rename_is_a_warning_not_success(tmp_path, monkeypatch):
    _write(tmp_path / "Src", _opts(("a", "true")))
    src = base._CVProject(tmp_path / "Src", ["a"])
    tgt = base._CVProject(tmp_path / "Tgt", ["b"])
    # Simulate a pass that changed nothing it should have.
    def _noop(path, renames):
        with open(path, "rb") as fh:
            return fh.read(), set(), []
    monkeypatch.setattr(config_views, "_rewrite_config", _noop)
    recs = config_views.plan_config_views(src, tgt, ws_map={"a": "b"})
    assert any("could not be applied" in r.reason for r in recs[0].missing_refs)


def test_reversal_config_filename_follows_root_ws(tmp_path):
    body = ('<DictionaryConfiguration name="Reversal" writingSystem="swh">'
            '<WritingSystemOptions><Option id="swh" isEnabled="true" /></WritingSystemOptions>'
            '</DictionaryConfiguration>')
    _write(tmp_path / "Src", body, name="swh.fwdictconfig", sub="ReversalIndex")
    # A pre-existing target file under the NEW name keeps the .gtbak behaviour.
    _write(tmp_path / "Tgt", "<old/>", name="sw.fwdictconfig", sub="ReversalIndex")
    src = base._CVProject(tmp_path / "Src", ["swh"])
    tgt = base._CVProject(tmp_path / "Tgt", ["sw"])
    recs = config_views.plan_config_views(src, tgt, ws_map={"swh": "sw"})
    assert os.path.basename(recs[0].tgt_path) == "sw.fwdictconfig"
    assert recs[0].action is ConfigViewAction.OVERWRITE
    config_views.apply_config_views(recs, [])
    assert os.path.exists(recs[0].tgt_path + ".gtbak")
    with open(recs[0].tgt_path, encoding="utf-8") as fh:
        assert 'writingSystem="sw"' in fh.read()
    assert not os.path.exists(
        os.path.join(os.path.dirname(recs[0].tgt_path), "swh.fwdictconfig"))


def test_reversal_index_absent_reason_text(monkeypatch):
    monkeypatch.setattr(reversals, "_gather_in_scope_entries", lambda i, c: [object()])
    monkeypatch.setattr(reversals, "_target_ws_ids", lambda t: {"en"})

    class _Idx:
        WritingSystem = "koh"

    class _Indexes:
        @staticmethod
        def GetAll():  # noqa: N802
            return [_Idx()]

    class _Proj:
        ReversalIndexes = _Indexes

    class _Ctx:
        _ws_map = {"koh": "gez"}

    dropped = []
    reversals.plan_reversals({"s"}, _Proj, object(), _Ctx(), {}, dropped)
    assert [d.reason for d in dropped] == ["writing system 'gez' absent in target"]


@pytest.mark.parametrize("exc", [AttributeError, TypeError, NameError])
def test_programming_error_in_create_propagates(base_store_ops, monkeypatch, exc):
    class _Ops(base._StoreVsActiveWSOps):
        def Create(self, tag, name, is_vernacular=True):  # noqa: N802
            raise exc("bug")

    monkeypatch.setattr("flexicon.WritingSystemOperations", _Ops, raising=False)
    target = {"store": ["etu"], "active": ["etu"], "created": []}
    _, plan = base._ctx_plan(target, ["fr"])
    failures = []
    with pytest.raises(exc):
        api_mod._ensure_writing_systems(target, None, plan, failures)
    assert failures == []


@pytest.fixture()
def base_store_ops(monkeypatch):
    monkeypatch.setattr("flexicon.WritingSystemOperations",
                        base._StoreVsActiveWSOps, raising=False)
    monkeypatch.setattr(api_mod, "_persist_without_close", lambda proj, what: None)


def test_genuine_lcm_failure_is_still_a_drop(base_store_ops):
    target = {"store": ["etu"], "active": ["etu"], "created": [], "refuse": ["fr"]}
    _, plan = base._ctx_plan(target, ["fr"])
    failures = []
    api_mod._ensure_writing_systems(target, None, plan, failures)
    assert [f.item_name for f in failures] == ["fr"]
