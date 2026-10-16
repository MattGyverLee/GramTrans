# Cycle 1 - programmer - issue #45 (untitled text collision)

Worktree note: `import gramtrans` resolved to the MAIN checkout by default; used PYTHONPATH=<worktree>/src (verified).

## Files changed
- src/gramtrans/Lib/texts.py: new UNTITLED_LABEL, `_untitled_create_name`, `_resolve_or_create_text_ex` (returns `(text, created)`); `_resolve_or_create_text` kept as wrapper; `_added` counting in the execute loop (~:778-790).
- tests/unit/_fakes_texts.py: FakeText.alt_names; FakeTextOps.Exists now reads best-analysis (falls back to alt_names), Find reads default-WS `name` only, so they diverge as in flexicon.
- tests/unit/test_texts_untitled_collision.py (new, 5 tests).
- selection.py:~3868 already reads "(untitled text)"; left unchanged, the placeholder now uses that same wording (no edit needed).

## Key-function decision
- Untitled ADD: no Exists/Find at all. Real `Texts.Create` requires a unique non-empty name, so the create name is `"(untitled text) <source-guid>"`: unique per text, passed only to Create, never a lookup key. GUID preserved via guid=.
- Titled: guard and write both use `Find(name)` (target DefaultAnalWs); `Exists` dropped from the guard. A name present only in a non-default WS now reaches Create, which raises inside try -> one "text create failed" DroppedItemRecord (never silent, no exception escapes).
- `_added` only when Create really ran; reuse-by-name/GUID counts as updated.

## Tests added
two untitled -> two texts under src-A/src-B, distinct names, added==2; no paragraph interleave; untitled never calls Exists/Find; titled reuse not counted created; non-default-WS name does not raise and is dropped-with-record.

## Suite
Full unit run on my commit alone: 5027 passed, 81 skipped, 14 xfailed, 0 failed. Latest rerun showed 19 failures, all in test_categories_*/test_selection_ui, caused by the other agent's uncommitted edits to categories.py/models.py/report.py/transfer.py (not my files). texts tests: all pass.

## SHAs
1f9053e (fix + tests), 005b2fa (test unpacking fix). Not pushed.

## Proposed live check (restored Target, no write done here)
Restore Target from backup, transfer Texts from `Tlachichilco Tepehua` (36/46 untitled) or `Mbugwe LizzieHC practice` (many untitled). Expect target text count == selected count, GUID set == source GUIDs, zero collapse. Then repeat Move: no new texts (GUID match via disposition). Caveat: untitled targets carry the "(untitled text) <guid>" name.
