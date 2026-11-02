# Tasks: 041 LINK stale-reference re-point (issue #15) -- P1 slice

(Spec artifact; normally committed to `main`. Carried on the implementation
branch's diff for convenience -- move/cherry-pick to `main` as preferred.)

Slice decisions (conservative picks for spec section 4 open questions):

* Q1: opt-in boolean `Selection.repoint_stale_refs` (default OFF); NOT a new
  `ConflictMode`. Runs only when AFFIXES is on and its mode is LINK.
* Q2: no constitution amendment needed -- the write is a distinct opt-in
  Move pass (precedent: #108, #134), not a change to LINK's default semantics.
* Q3: allow-list for P1 = single-valued `IMoAffixAllomorph.MsEnvPartOfSpeechRA`
  only (allomorph -> category). Not touched by any #134 pass, so evidence is
  unambiguous. Collections, affix->slot, allomorph->environment (already
  add-only repaired by #111/#134) are deferred. NB the spec's "slot->template"
  direction is backwards (templates own slot sequences).
* Q4: residue baseline not consulted; staleness is the structural predicate
  only (null, or different class than the source referent).
* Q5: repaired rows show as Preview "Re-point"; non-repaired as
  `SKIP (reason)` and as `Skip(NEEDS_MANUAL)` in the run report.

- [x] T1 pure predicate `categories.classify_ref_repoint` (stale / not-stale /
      unresolved / noop)
- [x] T2 shared `categories.compute_ref_repoints` (Preview + Move)
- [x] T3 Move pass `_run_ref_repoint_pass`, hooked via
      `transfer._ensure_ref_repoint` (own latch, never raises)
- [x] T4 Preview rows `preview.render_ref_repoints` / `count_ref_repoints`
- [x] T5 unit tests `tests/unit/test_issue15_ref_repoint.py`
- [x] T6 live gate `tests/integration/test_issue15_link_repoint_live.py`
      (sandbox GT-Sandbox-15; source fixture GT-Sandbox-15-Src)
- [ ] Deferred: collection refs; other allow-list fields; wizard checkbox and
      saved-selection persistence of the flag; open Q2 constitution review.
