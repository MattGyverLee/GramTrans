# QC cycle 2: #128 (PR #140) and #129 (PR #149), at ee365b3

> Saved by the main session. The lex-qc agent had no Write tool and returned this as its final message.
> It reviewed the detached checkout GramTrans-qc-ee365b3 and the saved diffs. The review was read-only: no tests and no live runs.

**Scores:** #128 = 82/100, #129 = 80/100. No P0 on either PR.

## Answers to the six questions

1. **`_tss_remap_ws_runs` (categories.py ~12487) is correct.**
   - It remaps ktptWs and ktptBaseWs per run, in this order: source handle, then source id, then `ws_map`, then target handle.
   - The fallback is the alternative's own target handle, never a raw source handle.
   - It edits a `GetBldr()` copy, so the source ITsString is not mutated.
   - Run offsets are character-based and only int props change, so run boundaries stay stable.
   - **Missed props:** object-data string props (ktptObjData, link and ORC GUIDs) and ktptTags are copied verbatim, so they still point at source-project GUIDs. The risk is low in a Summary.

2. **`_ensure_entryref_passes` (transfer.py:328, called at 991) effectively never raises.**
   - Each runner is wrapped in try/except, and the latch setattr and the skips-extend are both guarded.
   - The one gap is the `from .categories import ...` at ~343, which sits outside any try.
   - **No double-run:** it reuses the `_did_entryref_create_pass` and `_did_post_pass_a` latches, setting them before the run as `_run_tail_once` does. It also covers the case where the STEMS action raised before its tail.
   - **AFFIXES-only runs honour the domain ruling:**
     - Bindings are stashed only by `affixes_plan_action` (categories.py:13400) and `stems_plan_action` (13935).
     - C1 (12729-12738) skips an owner that is absent from the target and never creates an entry.
     - C2 (12886-12891) touches only refs that have a per-ref record.
     - C2 resolves lexemes but never creates them (12908-12919).

3. **#129 `except Exception` (references.py:1262) does not newly swallow anything that should propagate.**
   - The engine owns the UOW, so a poisoned transaction would still fail later at `apply_residue` (1283), outside the `try`.
   - The failure is logged and recorded as a DroppedItemRecord.

4. **`_wrap_plain_text`** has a real correctness risk; see P1-2 below.

5. **The test_027 fake update is fair.**
   - The old `object()` worked only because the AttributeError was swallowed, and that swallow was deliberately removed.
   - The new test_issue129 tests cover the content copy. This does not hide a regression.

6. **The residue strip covers both branches.**
   - `_fingerprint_snapshot` feeds both the id-keyed branch and the positional branch.
   - A residue-only alternative is dropped, and real text is kept (a test asserts this).
   - **Anchor:** `residue._is_tag_line` (residue.py:338) matches any line that starts with `[GT-Tag]: ` and does not require `GT|<run>|`. A user line that starts with that marker would be swallowed and would hide a divergence. The risk is low, and the helper is shared and already shipped.

## Findings

**P0:** none.

**P1**
- **P1-1 (#128): no AFFIXES-only test.** The code appears to satisfy the domain ruling, but no test asserts it. The live test selects both STEMS and AFFIXES, and the unit tests use only 0-action plans.
- **P1-2 (#129): `_wrap_plain_text` can write text that was reported as dropped** (references.py:1243 resolver branch, and 1252).
  - The fallback runs when every source WS was dropped as "absent in target" (1227-1241). It still writes `_best_text` into the default analysis WS.
  - That contradicts the drop records, and it can put vernacular text under an analysis WS.
  - The "first target WS" fallback depends on dict order.
  - *Suggested fix:* use the plain-text fallback only when no drop was recorded for that field; otherwise leave the field empty.

**P2**
- **P2-1:** `_merge_delta` compares text only (categories.py ~12599). A formatting-only Summary edit never propagates. The result is still idempotent.
- **P2-2:** if `_tss_remap_ws_runs` raises, the whole alternative is dropped (~12610). Fall back to `mk(text, handle)` and record a warning instead.
- **P2-3:** AFFIXES-only runs now emit `DEPENDENCY_UNRESOLVED` skips, categorised as STEMS, for every affix ref whose component stem is not in the target (12912). Confirm these do not inflate the failure counts.
- **P2-4:** the #129 drop record has an empty `owner_guid` and `owner_label` (1273-1274).
- **P2-5:** `_ensure_entryref_passes` does not guard its import (transfer.py ~343).
- **P2-6:** the residue-strip marker anchoring described in question 6.

## Gates
- **Live:** both implementer reports cite runs with FLEXLIBS_REQUIRE_LIVE=1.
  - #128: GT-Src-128 to GT-Sandbox-128, with a negative control.
  - #129: GT-Src-42 to GT-Sandbox-129, 9 passed.
- **Not checked by the reviewer:** the evidence artifacts and `tests/live_status.json`, and whether the PR bodies contain a "Pattern audit" section.
