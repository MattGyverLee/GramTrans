# cycle1-lex-qc-114 (PR #124, HEAD bb06edb)

> Saved by the main session: lex-qc has no Write tool and returned this text verbatim.

Score 90/100. Verdict: APPROVE with P2s only. No P0 or P1. Reviewed statically, no live runs.

## Answers
1. **Summary WS mapping: correct.**
   - categories.py:12014-12026: the target handle comes from `tgt_handle_by_id[ws_map.get(src_ws, src_ws)]`, never the raw source handle.
   - `_merge_delta(..., ws_map)` compares against target alternatives keyed by the same translated id (conflict.py:641).
   - An unmapped WS has no target handle, so `_drop("Summary", ...)` fires at :12022-12026.
   - Read-back: `_tss_read_text(get_String(handle))` compared with `str(back) != text` (:12029-12036). That is a plain-text compare of what was written, and `_text_eq` is also exact, so the two agree. Run properties are lost, which the implementer already listed as a risk.
2. **existing_guids became the existing_refs dict: no other change.**
   - Both are local to `_run_entryref_create_pass` (:12159-12225), so there are no external callers.
   - The INV-1 arm still creates nothing and then `continue`s, as before (:12167-12174).
   - The C3 and C2 wiring was not touched; the C2 pass lives in `_run_post_pass_a`.
   - New side effect: refs that already exist now have their values written, so a re-run can change target data. That is intended, but Preview has no line for it. The implementer disclosed this.
3. **Census INT kind: safe.**
   - `_VALUE_KINDS = {"MU","INT"}` (fidelity_census.py:146). `prop` stays unsuffixed only for those two kinds (:181), so every other row still gets its suffix.
   - Unit and census counts were reported green (118 passed).
4. **Stale #32 note: P2, not blocking.** Lines 743-748 cite categories.py:4435, :5041 and :5014. These are stale line numbers, and the note is also odd now that more LexEntryRef fields are COPIED. Fix it in a follow-up.
5. **Pattern audit spot-check: CONFIRMED.** The CmSemanticDomain create path (categories.py:4284-4328) calls `factory.Create`, adds to the owner, then runs only `apply_carrier_b`. It copies no Name, Abbreviation or Description in that function. I did not check whether a caller fills them elsewhere, so treat it as HIGH but unverified at the caller level.

## Findings
- P2, categories.py:11989-11990 and :12000: `int(tgt_hide)` and `int(back)` will raise on a non-numeric fake or proxy. The `back` conversion sits inside the try's else branch, so it is not caught.
- P2, categories.py:12002-12003: the HideMinorEntry drop uses `item_name=str(src_hide)`. That is fine, but two drops for one ref/field are de-duplicated by `_append_dropped_once`.
- P2, impl-114.md section 6: a source value of 0 overwrites a target 1. This follows `_is_empty`. Confirm it is the product intent; the implementer flagged it.
- P2, fidelity_census.py:743-748: the stale note from question 4.
- Gates: pattern audit is in the PR body, with a spot-check on the first two rows. The live evidence is documented (live run, mutation test fails, hashes). I did not verify the artifact files.
