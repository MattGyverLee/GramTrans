"""Issue #176 -- references.py relocation hardening (follow-up to #129)."""
from __future__ import annotations

from gramtrans.Lib import references

from test_issue129_create_arm_multistring import _MS, _Ops, _Src, _run, _source


class _RaisingOwner:
    """`Name` raises a non-AttributeError; `getattr(default)` would not catch it."""
    Guid = "ABCDEF00-0000-0000-0000-000000000001"

    @property
    def Name(self):
        raise RuntimeError("boom")

    HeadWord = "hw"


def test_owner_ids_survives_non_attribute_error():
    guid, label = references._owner_ids(_RaisingOwner())
    assert guid == _RaisingOwner.Guid.lower()
    assert label == "hw"


def test_owner_ids_failure_is_logged(caplog):
    with caplog.at_level("WARNING", logger="gramtrans.Lib.references"):
        references._owner_ids(_RaisingOwner())
    assert any("_owner_ids" in r.getMessage() for r in caplog.records)


def test_unresolved_handle_is_unknown_and_skips_relocation(monkeypatch):
    # handle 99 is not in the source project's WS table -> unknown WS
    ops = _Ops()
    src = _Src("1" * 8 + "-aaaa-aaaa-aaaa-" + "b" * 12, Name={99: "Mystery"})
    dropped = _run(monkeypatch, src, ops, source=_source())
    assert "Name" not in ops.calls[0]
    assert not any(d.reason.startswith("relocated:") for d in dropped)


def test_best_alt_matches_best_text_choice():
    ms = _MS({2: "", 1: "Hallo", 3: "Other"})
    ws_id, text = references._best_alt(ms, {1: "de", 2: "qaa", 3: "fr"})
    assert text == references._best_text(ms) == "Hallo"
    assert ws_id == "de"


def test_best_alt_unresolved_handle_is_none():
    assert references._best_alt(_MS({5: "x"}), {1: "de"}) == (None, "x")
    assert references._best_alt(_MS({}), {1: "de"}) == (None, "")
