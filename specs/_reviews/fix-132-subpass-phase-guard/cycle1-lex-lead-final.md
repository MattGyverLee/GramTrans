# fix-132 sub-pass phase guard — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, acceptance lists open sites) — **`_wire_msa_infl_feats` / `_wire_prod_restrictions` unguarded at end of `_run_171_subpass`** plus the **Add-raises-but-read-back-present** gap from #111 (impl-111 §6 item 2, cited in #132 body).

A raise from either tail helper aborted the entire 17.1 sub-pass: slots wiring could finish while **InflFeats** and **ProdRestrict** never ran, with only a post-pass log on the safety-net path. Separately, when `SlotsRC.Add` raised but read-back still found every resolved slot, the MSA correctly stayed **LINKED** (#111) yet the Add exception was not logged and `AffixSlotLinkRecord.detail` stayed empty — a silent diagnostic gap FR-336 forbids.

## Resolution

- Add `_extend_171_subpass_skips` and wrap `_wire_msa_infl_feats` and `_wire_prod_restrictions` so each phase reports one `Skip(DEPENDENCY_UNRESOLVED)` on raise and the other phase still runs.
- When outcome is **LINKED** but `write_errors` is non-empty, log a `warning` and persist the errors on the slot-link record's `detail`.

## Verification

- `tests/unit/test_issue132_subpass_phase_guard.py` — **3 tests**

**Verdict: GO** — refs #132.
