# impl-129 -- Possibility CREATE arm plain-string multistring (issue #129, P1)

- Branch: fix-129-create-arm-multistring (worktree D:/Github/_Projects/_LEX/GramTrans-fix-129), based on origin/main 23e5356
- Commit: d4b41e0 (closes #129); origin/main merged (already up to date), pushed
- PR: https://github.com/MattGyverLee/GramTrans/pull/149 (not merged)
- Verdict: READY FOR REVIEW. Unit suite green, live gate green (9 passed, strict xfail removed).

## Root-cause trace (live, GT-Src-42 -> GT-Sandbox-129, temporary [TRACE129] prints, since reverted)
The issue's hypothesis is WRONG. The TypeError does not cause the UPDATE; `apply_residue` does.
- Move 1 CREATE props: `{'Name': {'en': ...}, 'Abbreviation': {'en': ...}, 'Description': ''}`.
  `ApplySyncableProperties` raised `TypeError('property is read-only')` on the plain '' (swallowed). Name/Abbreviation were
  already applied; fingerprint right after apply: `Description ()` == source `()` (no divergence yet).
- After `apply_residue`: target `Description (('en', '\n[GT-Tag]: GT|GT-...|GT-Src-42|...'),)`.
- Move 2 `decide_reference`: `src_fp Description=()` vs `tgt_fp Description=(GT-Tag line)` -> not identical -> UPDATE
  (for C and D; once in preview, once in Move 2).
So two independent defects: (A) residue line in the fingerprint (drives UPDATE), (B) plain-string TypeError on the CREATE arm
(silent write failure, 4x "Apply syncable properties: exception TypeError" in Move 1). Fixing only B would leave the xfail failing.

## Fix (src/gramtrans/Lib/references.py only)
- A: new `_fingerprint_snapshot` strips `[GT-Tag]:` residue (`residue.strip_residue_text`) from Description alts in
  `divergence_fingerprint` (both resolver and positional branches); an alt holding only residue is dropped
  (same rule as `strip_residue_props`). Real user text in Description still counts as divergence.
- B: new `_wrap_plain_text(text, ops, target_ws_by_id)` -> `{target default-analysis WS id (else first target WS): text}`,
  `{}` for empty. CREATE arm now only adds a field to `create_props` when it is a non-empty dict (empty -> field skipped).
- B: `except (AttributeError, TypeError): pass` -> `except Exception`: log warning + `DroppedItemRecord(reason="created item's
  Name/Abbreviation/Description could not be copied: <repr>")`. Deliberate: the item already exists/is owned, so it is still
  residue-tagged, cached and linked; the failed content copy is recorded, not re-raised.

### Swept sites (`field_props if field_props else _best_text(...)` plain-string pattern)
1. CREATE arm, source-resolver branch (was ~1195): fixed (wrap/skip).
2. CREATE arm, no-resolver branch (was ~1203, `id_keyed if id_keyed else _best_text`): fixed (wrap/skip).
No other `_best_text` callers anywhere in src/ (grep). UPDATE arm builds dicts only (`src_props[field]` always dict) -- no change.

## Tests and unit delta
- New tests/unit/test_issue129_create_arm_multistring.py (5): empty plain Description skipped; non-empty plain wrapped as
  ws dict; `_wrap_plain_text` default WS/empty cases; raising `ApplySyncableProperties` -> drop record (not swallowed);
  fingerprint ignores residue but not real text.
- tests/unit/test_027_entry_type_resolve.py: its `_FakeTarget.PossibilityLists` was a bare `object()` whose missing
  `ApplySyncableProperties` the old swallow hid; replaced with a no-op fake (2 tests had started recording the new drop).
- `python -m pytest tests/unit -q`: 5389 passed / 80 skipped / 14 xfailed. Delta vs 5384/80/14: +5 passed, skipped/xfailed unchanged.

## Live proof (FLEXLIBS_REQUIRE_LIVE=1, GT42_TARGET_NAME=GT-Sandbox-129; wrote only GT-Src-42 and GT-Sandbox-129)
- tests/integration/test_issue42_appendix_thesaurus_live.py: 9 passed in 16s. Strict xfail marker removed from
  `test_items_created_by_move1_link_on_the_next_run`; it PASSES (asserts `{C: link, D: link}` for s3's ThesaurusItemsRC).
- Move 1 log: zero "Apply syncable properties: exception TypeError" lines (baseline had 4). Move 1: actions=1, drops=[AppendixesRC
  A-ABSENT only]. Move 2: actions=1, drops=[]; Move 3: actions=0 (idempotent). Move 2 decisions for C and D are LINK (asserted
  by that test; baseline trace showed UPDATE for both). Preview == Move decisions test also green.

## Env check
```
D:\Github\_Projects\_LEX\GramTrans-fix-129\src\gramtrans\__init__.py D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```

## Risks
- Fingerprint now ignores residue in Description for ALL reference decisions (not just thesaurus): a target item differing from
  source only by a GT-Tag line now LINKs instead of UPDATEs. Intended; matches `categories.py` / `conflict.py` precedent.
- Wrap fallback writes best-alt text to the target default WS when no source WS maps (a drop is already recorded for the
  unmapped WS); previously this path always failed.
- Any real apply failure on CREATE now surfaces as a drop record (info severity) -- may reveal other previously silent failures.
- #131 (categories.py) and #136 (owned.py) untouched; no overlap expected beyond references.py.

## Files touched
- src/gramtrans/Lib/references.py
- tests/unit/test_issue129_create_arm_multistring.py (new)
- tests/unit/test_027_entry_type_resolve.py
- tests/integration/test_issue42_appendix_thesaurus_live.py (xfail removed, comments)
