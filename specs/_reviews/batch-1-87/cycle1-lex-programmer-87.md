# Cycle 1 -- issue #87 (residue tagger re-stamps present objects)
Branch fix-87-residue-idempotent, commit 6c06a0e (not merged, not pushed). Run with PYTHONPATH=src (bare import resolved to the main checkout).

## Repro before fix
tests/integration/test_issue45_untitled_texts_live.py with GT_SNAP_DIR: restored Target, 3 untitled Mbugwe texts, twice.
diff run1.fwdata run2.fwdata = 18 lines; each of the 3 Texts gained a 2nd "[GT-Tag]: GT|<run2 id>|Mbugwe Lizzie|<ts>" line.

## Root cause
texts.apply_texts called apply_residue(target_text) unconditionally after _resolve_or_create_text_ex, even when `_created` was False
(matched) and _apply_paragraphs returned "already reproduced". Every other tagger site stamps only a freshly created `new_*` object.

## Tag-consumer audit
| consumer | depends on re-stamp? | handling |
|---|---|---|
| conflict.py:459 parse -> decode_merge_log (prior merge decisions) | No. Parse uses rfind (LAST tag), so a spurious re-stamp HID the prior merge log/snap | none; fix protects it |
| report.py "untouched since last run" (reads latest tag as baseline) | No; re-stamp corrupted that baseline | none |
| api.py:1042 | Producer only (builds tag from context) | none |
| gramtrans.py docs "find this run's additions" | Wants only touched objects | fix matches intent |
| categories.py:3659 comment | Describes a freshly created type | none |
No consumer (undo, conflict, reports) needs matched objects stamped.

## Call-site audit
| site | bug? | fixed? |
|---|---|---|
| texts.py:817 Text container | YES (stamped on match) | yes: only if created or paragraphs created this run; moved after _apply_paragraphs |
| texts.py:1349 StTxtPara | no (created only; whole loop skipped when text already has paragraphs) | n/a |
| wordforms.py:1031 WfiWordform | no on re-run (stamp only after a NEW analysis is created; GUID/fingerprint dedup `continue`s first). But a found wordform got a duplicate line per extra new analysis in one run | yes via carrier_b same-run dedup |
| wordforms.py:1033 WfiAnalysis | no (created only) | n/a |
| categories.py ~37 apply_carrier_b/apply_residue sites (POS, features, types, rules, entries, senses, allomorphs, MSAs, LexReference Carrier A, slots, etc.) | no: all on `new_*` objects after factory Create; MSA "reuse" is under an entry created this run | n/a |
| owned.py:769,1414; references.py:1192; reversals.py:674,1032 | no (created only) | n/a |
| transfer.py create sites (1725..2625) | no | n/a |
| transfer.py overwrite sites (2251,3396,3579-4049) | no: explicit OVERWRITE/UPDATE actions that wrote fields; stamp carries snap= undo baseline | n/a |
| transfer.py:3660 slot overwrite | tag-only write, but only on an explicit OVERWRITE action, not a match | left; noted |

## Design
Gate at the call site on the create/update outcome (not a per-run GUID set): each site already knows create vs match, a GUID set
would add shared state across Preview/Move for no gain. Plus defense in depth in apply_carrier_b: skip when the Description already has a
tag line with this run_id ("first stamp wins" so an update's snap= baseline is never clobbered).
Append-vs-replace rule: an object actually created or updated by run N gets ONE line for run N; if it already carries a line from an
earlier run, the new line is APPENDED (history kept; parse reads the last). Same run never writes twice. Matched/no-op: no write.

## Results
- Live after fix: run1 stamps each of 3 Texts once (3 lines, one run id); diff run1 vs run2 = 0 lines; sha256 run2 == run1. Live test now asserts this.
- Unit tests added: tests/unit/test_issue87_residue_idempotent.py (2; both fail on pre-fix src, pass after).
- Tests (REQUIRE_LIVE=1): integration 30 failed / 767 passed / 75 skipped = baseline, delta 0 (same 30 census/known failures). Unit alone 5069 passed, 0 failed.
  Whole `tests` tree: 135 failed both before and after (identical failed set, cross-suite pollution, pre-existing); passed 5845 -> 5847 (+2 new).
- Target restored to baseline (sha 13c5a96f...) at end.
