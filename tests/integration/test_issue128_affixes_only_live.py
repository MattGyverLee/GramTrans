"""Issue #128 follow-up (QC P1-1) live gate -- an AFFIXES-ONLY run.

#128 runs the LexEntryRef C1/C2 passes through `_ensure_entryref_passes` even
when AFFIXES is selected without STEMS. This selects AFFIXES alone and asserts
the domain ruling: C1 never creates an entry (an out-of-scope stem owner stays
absent), no stem LexEntry is created, component targets resolve only if they
already exist in the target, an in-scope affix's ref gets its Summary, and the
C1/C2 latches stop a double run. It also counts the STEMS-categorised
DEPENDENCY_UNRESOLVED skips (QC P2-3) and prints the number.

WRITE PATH: only GT-Src-128 (source) and GT-Sandbox-128 (target), both
restored from ``Target 2026-07-06 0218.fwbackup``. Same pair/helpers as
test_issue128_entryref_postpass_live.py.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue128_affixes_only_live.py -v -s
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_issue128_entryref_postpass_live import (  # noqa: E402
    SOURCE_NAME, TARGET_NAME, TARGET_PATH, _author_summary, _open, _ref,
    _ref_body, _restore, _values,
)

pytestmark = pytest.mark.integration


def _selection(picks):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    return Selection(categories={GC.AFFIXES: True},
                     include_closure=True,
                     leaf_item_picks={GC.AFFIXES: frozenset(picks)})


def _stems_selection(picks):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    return Selection(categories={GC.STEMS: True},
                     include_closure=True,
                     leaf_item_picks={GC.STEMS: frozenset(picks)})


def _move(selection):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=lambda _full: selection)


def _entry_state(name):
    """{guid: (lexeme_form, is_affix)} for every LexEntry in a project."""
    from SIL.LCModel import ILexEntry
    proj = _open(name)
    try:
        out = {}
        for e in proj.LexiconAllEntries():
            mt = e.LexemeFormOA.MorphTypeRA if e.LexemeFormOA else None
            out[str(e.Guid).lower()] = (
                str(e.LexemeFormOA.Form.BestVernacularAlternative.Text)
                if e.LexemeFormOA else None,
                bool(mt.IsAffixType) if mt is not None else False)
        return out
    finally:
        proj.CloseProject()


def _ref_components(name, ref_guid):
    proj = _open(name)
    try:
        ref = _ref(proj, ref_guid)
        return {str(c.Guid).lower() for c in ref.ComponentLexemesRS}
    finally:
        proj.CloseProject()


def test_affixes_only_run_honours_the_domain_ruling(monkeypatch):
    from gramtrans.Lib import categories
    from gramtrans.Lib.models import GrammarCategory as GC, SkipReason
    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)

    proj = _open(SOURCE_NAME, write=True)
    try:
        stem_a = proj.LexEntry.Create("gt128b stemA")      # pre-seeded in target
        stem_b = proj.LexEntry.Create("gt128b stemB")      # never transferred
        stem_owner = proj.LexEntry.Create("gt128b stemowner")  # out of scope
        aff_comp = proj.LexEntry.Create("gt128b", "suffix")
        aff_in = proj.LexEntry.Create("gt128b2", "suffix")
        for comp in (stem_a, stem_b, aff_comp):
            proj.LexEntry.AddComplexFormComponent(aff_in, comp)
        proj.LexEntry.AddComplexFormComponent(stem_owner, stem_a)
        ref = aff_in.EntryRefsOS[0]
        _author_summary(proj, ref, "Summary BOLD styled etu")
        g = {k: str(v.Guid).lower() for k, v in dict(
            stem_a=stem_a, stem_b=stem_b, stem_owner=stem_owner,
            aff_comp=aff_comp, aff_in=aff_in).items()}
        ref_guid = str(ref.Guid)
        owner_ref_guid = str(stem_owner.EntryRefsOS[0].Guid)
    finally:
        proj.CloseProject()
    src_vals = _values(SOURCE_NAME, ref_guid)
    assert not _entry_state(SOURCE_NAME)[g["aff_in"]][0] is None
    assert _entry_state(SOURCE_NAME)[g["aff_in"]][1], "affix not an affix"
    assert not _entry_state(SOURCE_NAME)[g["stem_a"]][1]

    # Seed the target with stemA ONLY (a STEMS-only move), so "a component
    # resolves only if it already exists" has both a present and an absent case.
    _move(_stems_selection({g["stem_a"]}))
    before = _entry_state(TARGET_NAME)
    assert g["stem_a"] in before and g["stem_b"] not in before
    assert g["stem_owner"] not in before

    calls = {"c1": 0, "c2": 0}
    real_c1 = categories._run_entryref_create_pass
    real_c2 = categories._run_post_pass_a

    def c1(*a, **k):
        calls["c1"] += 1
        return real_c1(*a, **k)

    def c2(*a, **k):
        calls["c2"] += 1
        return real_c2(*a, **k)

    monkeypatch.setattr(categories, "_run_entryref_create_pass", c1)
    monkeypatch.setattr(categories, "_run_post_pass_a", c2)

    # ---- the AFFIXES-ONLY move -------------------------------------------
    plan, report = _move(_selection({g["aff_in"], g["aff_comp"]}))
    after = _entry_state(TARGET_NAME)
    created = set(after) - set(before)
    cats = {a.category for a in plan.actions}
    print("[LIVE] plan categories:", sorted(c.name for c in cats))
    print("[LIVE] created entries:", sorted(after[x][0] for x in created))
    assert cats == {GC.AFFIXES}, cats

    # (b) no stem LexEntry created anywhere; (a) the out-of-scope owner and
    # the absent component were not invented.
    assert not [x for x in created if not after[x][1]], "a stem entry was created"
    assert g["stem_owner"] not in after and g["stem_b"] not in after
    assert {g["aff_in"], g["aff_comp"]} <= created

    # (c) components: only those already in the target are wired.
    comps = _ref_components(TARGET_NAME, ref_guid)
    print("[LIVE] target ref components:", sorted(comps))
    assert g["stem_b"] not in comps
    assert comps == {g["stem_a"], g["aff_comp"]}, comps

    # (d) the in-scope affix's ref has its Summary (runs preserved).
    tgt_vals = _values(TARGET_NAME, ref_guid)
    assert tgt_vals["main"] == src_vals["main"], (tgt_vals, src_vals)
    assert tgt_vals["second"] == src_vals["second"]

    # (e) each pass ran exactly once on this run's execute().
    assert calls == {"c1": 1, "c2": 1}, calls

    # P2-3: STEMS-categorised DEPENDENCY_UNRESOLVED skips on this run.
    stem_skips = [s for s in report.skips
                  if s.category == GC.STEMS
                  and s.reason == SkipReason.DEPENDENCY_UNRESOLVED]
    print("[LIVE] STEMS DEPENDENCY_UNRESOLVED skips: %d of %d total skips"
          % (len(stem_skips), len(report.skips)))
    for s in stem_skips:
        print("[LIVE]   skip:", s.source_guid, s.detail)
    print("[LIVE] failed counters:",
          {k: v for k, v in vars(report).items()
           if "fail" in k.lower() or "error" in k.lower()})

    # ---- idempotent: a second AFFIXES-only move writes nothing -----------
    body = _ref_body(ref_guid)
    assert body
    calls.update(c1=0, c2=0)
    plan2, _r2 = _move(_selection({g["aff_in"], g["aff_comp"]}))
    assert len(plan2.actions) == 0
    assert calls == {"c1": 1, "c2": 1}, calls   # once per execute, not twice
    assert _ref_body(ref_guid) == body, "second AFFIXES-only run rewrote the ref"
    assert set(_entry_state(TARGET_NAME)) == set(after)
