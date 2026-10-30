# QC cycle2 -- issue #87 (commit 6c06a0e) -- static review only

**Score: 84/100.** No P0; fix is sound.

(Saved by the main session: lex-qc has Read/Grep/Glob only, so it could neither write this file nor run unit tests.)

## Findings

1. **Run-id match (residue.py:283).** Tests `"[GT-Tag]: GT|<run_id>|" in existing` -- anchored to the tag marker, the `GT|` prefix and trailing `|`. `_RUN_ID_PATTERN` (residue.py:25) forces fixed-width `GT-\d{8}-\d{6}`, so no id is a prefix of another. A false positive needs user text forging the full marker plus a real run id -- negligible. Substring, not line-start, check (P2).
2. **First stamp wins.** The Description carrier is reached on overwrite/update paths at transfer.py:3623 (template) and 4049 (environment), plus the categories.py update sites. A same-run first stamp can only come from a create stamp, whose baseline is "object absent"; undo deletes the object, so losing a later `snap=` is correct. Slot (transfer.py:3660) carries no snap. LiftResidue objects (entry, sense, MSA, allomorph) use Carrier A, which overwrites, so (b) does not affect them. **Not fully proven (P1):** conflict.py:459 `decode_merge_log` not traced; not proven that no site stamps a matched object without `snap=` before a later snap-bearing stamp in the same run.
3. **texts.py:824** `if _created or (plan.paragraphs and not already)`. A matched text gaining paragraphs on run 2 gets exactly one stamp; on run 3 `already` is True, so none. Matched with zero changes: no residue call at all. SetAbbreviation / SetIsTranslated / genres still written (not Description) -- acceptable.
4. **Sampled 8 sites** (stamp only freshly created objects): categories.py:1468, 7408 (LexReference), 8381, 8531, 9923, 10427 (MSA reuse; entry and sense are new, Carrier A overwrites), transfer.py:2412/2438/2539. All fine.
5. **Tests.** Carrier B same-run vs different-run test is good. Text re-run test correctly patches residue at call time. Live-test assertion change in test_issue45_untitled_texts_live.py not verified.

## P1

- Run unit tests and finish the decode_merge_log multi-line / same-run snap trace before approving.

## P2

- texts.py:824 stamps when `_apply_paragraphs` returns False because `para_ops`/`seg_ops` is None or every paragraph create failed -- nothing was written to the matched text, yet it is stamped. Use a created-paragraph count instead.
- No test for "matched empty text gains paragraphs, stamped once" or for the prefix/user-text case.
- residue.py:283: consider matching at line start.
