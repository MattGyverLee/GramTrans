# Cycle 3 -- Programmer: carried-forward QC polish

Worktree: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
Branch: `038-transfer-fidelity-gaps`
Commit: `5cf155c` -- "fix(038): carried-forward QC polish -- key constant
wired, silent-discard trap closed, dedup asymmetry documented, T124
supplements basename tagged"

## What changed, per item

1. **P1, `categories.py:6566` (`_LEX_REF_TYPE_KEY_FIELDS`).** Chose **wire
   through**, not delete. Added `_LEX_REF_TYPE_KEY_READERS`, a
   `{field: (reader_fn, is_invalid_fn)}` map, and rewrote
   `_lex_ref_type_natural_key` to iterate `_LEX_REF_TYPE_KEY_FIELDS` and
   build the key from that map instead of hardcoding `Name`/`MappingType`
   reads inline. Rationale: this was achievable with **zero change to the
   key's value or ordering for any input**, which was the stated
   precondition for preferring wiring over deletion. The tricky part
   preserved exactly: `Name`'s invalidity rule is "empty string", but
   `MappingType`'s is "`is None`", *not* falsy -- `MappingType == 0`
   (`Synonyms`) is a valid key half, and a naive generic "falsy is invalid"
   loop would have silently broken every `Synonyms` resolution. The map
   keeps each field's own rule.

2. **P2, silent-discard trap.** Closed both named sites in
   `_resolve_target_lex_ref_type`: the ambiguity branch and the create-leg
   call into `_create_target_lex_ref_type`. Both now `raise ValueError` if
   `dropped is None` when that branch actually fires, instead of building a
   throwaway `[]`. Verified the sole production caller
   (`_evaluate_lexical_relation`, itself required-positional on `dropped`)
   always passes a real list, and every existing unit test that reaches
   either branch already passes `dropped=[]` explicitly -- confirmed by
   grep across `test_038_t123_lexreftype_key_and_create.py` before editing.
   Left the third occurrence of the same textual pattern
   (`_iter_relations_touching_copy_set`, line ~7366) untouched -- out of
   the two named sites' scope, and its production caller is also
   required-positional, so it isn't a live trap either.

3. **P2, dedup-granularity asymmetry.** Comment-only, at both sites: the
   ambiguous-key record (`item_guid=""`, dedups per TYPE) and the
   type-not-found record (`item_guid=rel_guid`, dedups per RELATION), each
   now says so and points at the other as the intentional mirror image.

4. **Cosmetic, `debug/run038_t124_recensus.py`.** Basename changed from
   literal `"t124-supplements-%s.json"` to `"%s-supplements-%s.json" %
   (RUN_TAG, ...)`. Default (`--tag t124`) output is byte-identical to
   before. Did not touch `_PROBE_OUT`/`GT038_PROBE_OUT` per instruction.

## Tests

`tests/unit/test_038_t123_lexreftype_key_and_create.py` +
`tests/unit/test_038_t123_lexrel_base_typed_proxy.py` +
`tests/integration/test_object_census.py -m "not integration"`:

- **Before** (stashed, clean HEAD 1edb442): 521 passed, 2 failed, 31
  deselected.
- **After** (my 4 edits applied): 521 passed, 2 failed, 31 deselected --
  identical counts, same two failures (`TestT101...test_every_committed_
  null_row_is_advisory` and `TestT078ThePost037Baseline...[ngoreme]`, both
  pre-existing census-artifact/digest-drift assertions unrelated to
  `categories.py`'s LexRefType path).
- The 24 tests in the two LexRefType/lexrel-specific files, run alone: all
  green (`24 passed`).

No behaviour change beyond what each item describes; nothing forced.
