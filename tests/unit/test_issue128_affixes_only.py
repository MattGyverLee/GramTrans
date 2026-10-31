"""Issue #128 follow-up (QC P1-1): an AFFIXES-only plan (no STEMS action).

`transfer._ensure_entryref_passes` must run the LexEntryRef C1/C2 passes on a
plan whose only actions are AFFIXES, and must honour the domain ruling: C1
skips an owner absent from the target and never creates an entry, C2 wires
only components that already exist, in-scope refs get their Summary, and the
latches stop a second run from re-executing either pass.

Host-free (same fakes as test_issue128_entryref_postpass.py).
"""
from __future__ import annotations

import types

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.models import GrammarCategory, SkipReason

from _fakes_entryref import FakeLexeme, ctx_create_and_wire, ref_record
from test_issue114_entryref_value_fields import (  # noqa: F401 -- fixture + fakes
    _Entry, _MultiString, _Ref, _Target, _stub_lcm,
)


def _affixes_only_ctx(bindings, wire):
    ctx = ctx_create_and_wire(bindings, lexentry_ref_bindings=wire)
    object.__setattr__(ctx, "_ws_map", None)
    object.__setattr__(ctx, "_exec_skips", [])
    ctx._run_plan.actions = [types.SimpleNamespace(category=GrammarCategory.AFFIXES)]
    return ctx


def _world():
    existing_ref = _Ref("ref-in", hide=0, summary=_MultiString({10: "old"}))
    affix_in = _Entry("affix-in", refs=[existing_ref])
    stem_present = FakeLexeme("stem-present")
    # "affix-gone" and "stem-absent" are deliberately NOT in the target.
    target = _Target({"affix-in": affix_in, "stem-present": stem_present})
    recs = {
        "affix-in": [ref_record("ref-in", ref_type=1, hide_minor_entry=1,
                                summary={"en": "new summary"},
                                components=["stem-present", "stem-absent"])],
        "affix-gone": [ref_record("ref-gone", ref_type=1,
                                  components=["stem-present"])],
    }
    wire = {"affix-in": {"ComponentLexemesRS": ["stem-present", "stem-absent"]},
            "affix-gone": {"ComponentLexemesRS": ["stem-present"]}}
    return target, existing_ref, affix_in, recs, wire


def test_affixes_only_runs_c1_c2_without_creating_or_inventing(_stub_lcm):
    target, ref, affix_in, recs, wire = _world()
    ctx = _affixes_only_ctx(recs, wire)
    transfer._ensure_entryref_passes(ctx, target, None, ctx._exec_skips)

    # (d) in-scope affix's ref gets its value fields
    assert ref.HideMinorEntry == 1
    assert ref.Summary.get_String(10).Text == "new summary"
    # (a)/(b) nothing created anywhere; absent owner skipped
    assert target.factory.created == []
    assert len(affix_in.EntryRefsOS) == 1
    assert target.get_object_by_guid("affix-gone") is None
    gone = [s for s in ctx._exec_skips if s.source_guid == "affix-gone"]
    assert gone and all(s.reason == SkipReason.DEPENDENCY_UNRESOLVED for s in gone)
    # (c) components resolve only if they already exist
    assert [x.guid for x in ref.ComponentLexemesRS] == ["stem-present"]
    assert target.get_object_by_guid("stem-absent") is None
    assert any("stem-absent" in s.detail for s in ctx._exec_skips)


def test_affixes_only_latches_stop_a_double_run(_stub_lcm, monkeypatch):
    target, _ref, _e, recs, wire = _world()
    ctx = _affixes_only_ctx(recs, wire)
    calls = {"c1": 0, "c2": 0}
    real_c1, real_c2 = categories._run_entryref_create_pass, categories._run_post_pass_a

    def c1(*a, **k):
        calls["c1"] += 1
        return real_c1(*a, **k)

    def c2(*a, **k):
        calls["c2"] += 1
        return real_c2(*a, **k)

    monkeypatch.setattr(categories, "_run_entryref_create_pass", c1)
    monkeypatch.setattr(categories, "_run_post_pass_a", c2)
    transfer._ensure_entryref_passes(ctx, target, None, ctx._exec_skips)
    n_skips = len(ctx._exec_skips)
    transfer._ensure_entryref_passes(ctx, target, None, ctx._exec_skips)

    assert calls == {"c1": 1, "c2": 1}
    assert len(ctx._exec_skips) == n_skips
