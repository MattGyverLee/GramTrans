"""Issue #132: UPDATE scalar half failures must reach dropped_items."""
from __future__ import annotations

import types

from gramtrans.Lib import transfer
from gramtrans.Lib.models import DroppedItemRecord, GrammarCategory, PlannedOverwrite


def test_update_scalar_failure_records_drop_when_collector_wired():
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="phon-guid-1",
        target_guid="phon-guid-1",
        match_via="guid",
        write_mode="merge",
        summary="/a/",
    )
    dropped: list = []
    boom = RuntimeError("ApplySyncableProperties aborted")

    transfer._record_update_scalar_failure(ow, dropped, boom)

    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.owner_guid == "phon-guid-1"
    assert rec.field_name == "(scalar UPDATE)"
    assert "RuntimeError" in rec.reason
    assert "ApplySyncableProperties aborted" in rec.reason


def test_update_scalar_failure_no_collector_is_noop():
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="phon-guid-1",
        target_guid="phon-guid-1",
        summary="/a/",
    )
    transfer._record_update_scalar_failure(ow, None, ValueError("x"))


def test_execute_update_semantic_scalar_raise_appends_drop(
        monkeypatch,
):
    monkeypatch.setattr(transfer, "_phoneme_env_field_diff_enabled", lambda: True)
    monkeypatch.setattr(transfer, "apply_residue", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "restore_residue_history", lambda *a, **k: None)

    class _Obj:
        def __init__(self, guid):
            self.Guid = guid
            self.ClassName = "PhPhoneme"

    class _Ops:
        def GetAll(self):
            return [_Obj("src"), _Obj("tgt")]

        def GetSyncableProperties(self, obj):
            return {"Name": {"en": "a"}}

    def _boom(*_a, **_k):
        raise RuntimeError("scalar write failed")

    monkeypatch.setattr(transfer, "apply_update_semantic", _boom)

    source = types.SimpleNamespace(Phonemes=_Ops())
    target = types.SimpleNamespace(
        Phonemes=_Ops(),
        Cache=types.SimpleNamespace(DefaultAnalWs=1),
        WritingSystems=types.SimpleNamespace(GetAll=lambda: []),
    )
    sink = types.SimpleNamespace(
        info=lambda m: None,
        warnings=[],
        Warning=lambda m: sink.warnings.append(m),
    )
    tag = types.SimpleNamespace(with_snapshot=lambda p: tag, serialize=lambda: "t")
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="src",
        target_guid="tgt",
        summary="/a/",
        write_mode="merge",
    )
    dropped: list = []

    transfer._execute_update_semantic(
        ow, source, target, sink, tag, dropped=dropped)

    assert len(dropped) == 1
    assert dropped[0].field_name == "(scalar UPDATE)"
