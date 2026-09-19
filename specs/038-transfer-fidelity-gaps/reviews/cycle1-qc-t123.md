# QC Cycle 1 -- T123 LexRefType key/create diff

Worktree `GramTrans-038-transfer-fidelity-gaps` @ 009642e, uncommitted
`src/gramtrans/Lib/categories.py` (+364/-18).

## Verdict: SAFE TO COMMIT AS-IS (P1/P2 items are polish, not blockers)

The diff is **not** cut off. Every new helper (`_lex_ref_type_mapping_type`,
`_lex_ref_type_key_name`, `_lex_ref_type_natural_key`, `ILexRefTypeFactory_ref`,
`_target_lex_ref_list`, `_target_lex_ref_types`, `_create_target_lex_ref_type`)
is defined and consumed; `_resolve_target_lex_ref_type`'s 4-leg body and
`_evaluate_lexical_relation`'s `plan_time` threading terminate cleanly, both
call sites (`reproduce_lexical_relation` line ~7163, `plan_lexical_relation_decision`
line ~7247) pass consistent arguments, and the two-positional-arg backward-compat
claim holds (verified by test and by reading the `source_type is None: return None`
guard). No half-renamed function, no orphaned call, no duplicate definition.

1. `python -m py_compile src/gramtrans/Lib/categories.py` -- **COMPILE_OK**.
2. `pytest tests/unit/ -q` -- **3877 passed, 79 skipped, 14 xfailed, 0 failed**
   (skips are pre-existing pythonnet/host-gated tests elsewhere, not this diff).
3. `pytest tests/unit/test_038_t123_lexreftype_key_and_create.py -v` -- **19/19
   passed**, no skips. Doubles are proxy-shaped (`_ProxyRefType` hides
   `MappingType`/`MembersOC` behind `__getattr__`, exactly like a pythonnet
   base-typed proxy), so the tests actually exercise the cast defect this
   feature keeps finding rather than a concrete-shaped double that can't.
4. Untracked `tests/integration/_snapshots/{census,recensus}-038-t123b-ngoreme.json`
   are **live evidence, not test fixtures** (destination `GT038 T124 Ngoreme`,
   `source_probe`/`destination_probe` paths present) -- `t123_lex_references`
   shows the fix working end to end: source and destination both read 5
   relations, same 3 owning types, same per-reference target counts
   (`Specific x3`->2/2/2, `Synonyms x1`->2, `Calendar x1`->13). Corroborates the
   unit-test result on a real project.
5. `census.natural_key_of`'s docstring reading (exact string, no strip/
   casefold/normalize, empty=no-key-never-matches-empty) is followed correctly
   by `_lex_ref_type_key_name`/`_lex_ref_type_natural_key`.
6. `DroppedItemRecord` field names used (`owner_kind`, `owner_guid`,
   `owner_label`, `field_name`, `item_name`, `item_guid`, `reason`) match
   `Lib/models.py:3432`. `except Exception` sites are all narrowly scoped and
   `# noqa: BLE001`-annotated per this codebase's established convention
   (report-not-raise on a leaf create).

## P1

- **`categories.py:6566`** `_LEX_REF_TYPE_KEY_FIELDS = ("Name", "MappingType")`
  is documented as "the one place its shape is written down" but is **never
  referenced** anywhere else in the module or repo (`grep` confirms zero other
  hits). `_lex_ref_type_natural_key` hardcodes the name+mapping_type read
  directly rather than iterating this tuple. A future maintainer editing the
  constant expecting it to change behavior will find nothing happens --
  misleading given the docstring's authority claim. Either wire the key
  functions through it or drop the constant.

## P2

- **`categories.py:6970` area (ambiguity branch inside `_resolve_target_lex_ref_type`)
  and `_create_target_lex_ref_type`'s failure branch**: both do
  `dropped if dropped is not None else []`, building a throwaway list when the
  caller passes no `dropped`. Currently harmless -- the sole production caller
  (`_evaluate_lexical_relation`) always passes a real list -- but a latent trap
  for any future direct call with `allow_create=True`/ambiguity reachable and
  no `dropped` kwarg: the record silently vanishes instead of erroring.
- Reporting granularity is asymmetric by design but undocumented as such: the
  "ambiguous key" `DroppedItemRecord` dedups to one record per **type**
  (`item_guid=""`), while the "type not found" record (in
  `_evaluate_lexical_relation`) is one per **relation** (`item_guid=rel_guid`).
  Not a data-loss bug -- every dropped relation still gets its own
  "type not found" record regardless -- but worth a one-line comment so a
  future reader doesn't "fix" the asymmetry into a regression.
- The two untracked snapshot JSONs (evidence above) aren't referenced by any
  test or tasks.md entry yet; fine as supporting evidence, but they should
  land in the same commit as the tasks.md update that cites them, or they'll
  look like stray artifacts in `git status` to the next session.
