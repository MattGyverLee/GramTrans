# impl-131 -- CmSemanticDomain create copies no Name/Abbreviation/Description

Issue #131 (P2). Branch `fix-131-semdomain-create-text` (worktree GramTrans-fix-131), PR #151 (not merged).

## 1. Audit answer: NOTHING else populates the text for a new domain

- `semantic_domains_plan_action` -> `_plan_gold_reserved_edit`: an absent GUID gets a bare create `PlannedAction`; the `write_mode="merge"` overwrite (fills empty WS slots) is planned ONLY for a GUID already present in the target. A domain created in this run therefore has no merge pass.
- `transfer._execute_gold_reserved_merge` writes only existing objects. SEMANTIC_DOMAINS is also absent from `_OPS_ACCESSOR_FOR_CATEGORY` (no ops UPDATE writer).
- `apply_carrier_b` writes only the `[GT-Tag]` line to Description. No residue/carrier/references pass touches Name/Abbreviation.
- Unit trace: `test_trace_create_alone_writes_no_text_so_the_copy_is_the_only_writer` (copy neutralised -> Name/Abbreviation empty, no source Description).
- Live trace on UNFIXED code (src stashed): target after move#1 = `Name {}`, `Abbreviation {}`, `Description {'en': '\n[GT-Tag]: GT|...'}`; the live test failed at the Name assertion.
- Caveat noted, not changed: on a LATER run in UPDATE mode a nameless domain, now present by GUID, could be gap-filled by the merge pass. That is incidental, not a writer for the create path, and no second writer was added.

## 2. Fix

`src/gramtrans/Lib/categories.py`: new `_SEMANTIC_DOMAIN_MULTISTRINGS = ("Name","Abbreviation","Description")`. `semantic_domains_execute_action` calls `_copy_multistrings_ws_mapped(src_obj, new_sd, ..., source, target, ws_map=ws_mapping)` in BOTH create branches (nested/top-level and the T123 demoted-parent branch), BEFORE `apply_carrier_b` so the tag line stays last in Description. Same shape as the #114/T127 entry-type fix. No ApplySyncableProperties used, so no dependency on #129. `factory.Create(Guid)` and owner placement are untouched.

## 3. Tests

Unit `tests/unit/test_issue131_semdomain_create_text.py` (8): audit trace; all three fields across en/fr/es; ws_mapping (fr->de); WS with no target counterpart skipped; empty source alternative never blanks; nested domain; demoted top-level branch; GUID-preserving create unchanged. 6 of 8 fail on the unfixed code.

Full suite: `python -m pytest tests/unit -q` -> **5392 passed, 80 skipped, 14 xfailed** (baseline 5384/80/14: +8 passed, no other change).

Env check (PYTHONPATH=GramTrans-fix-131/src):
```
D:\Github\_Projects\_LEX\GramTrans-fix-131\src\gramtrans\__init__.py D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py
```

## 4. Live proof (FLEXLIBS_REQUIRE_LIVE=1)

`tests/integration/test_issue131_semdomain_create_live.py`; names pinned (`assert name in (GT-Src-131, GT-Sandbox-131)` before every restore/write). Both projects restored from `Target 2026-07-06 0218.fwbackup` via `restore_target`, restored again at teardown. Only those two were written.

- Authored in GT-Src-131: new domain 5cc5f246-... (child of 63403699-...), Name/Abbreviation/Description in `en` and `etu`.
- Move 1 (SEMANTIC_DOMAINS only): 1 create action; target has the domain by GUID, class CmSemanticDomain, same parent, count 1792 -> 1793, Name and Abbreviation exact per WS, Description = source text per WS + exactly one `[GT-Tag]` line (en).
- Move 2: 0 actions, 1793 skips; domain read-back identical (idempotent).
- Result: 1 passed (125 s). On unfixed code: 1 failed (see section 1).

## 5. Census

`tests/verification/fidelity_census.py` tracks only reference/owned FieldSpecs (RA/RC/OS/OA); it has no CmSemanticDomain row and no multistring rows for any class. No rows added; census not run.

## 6. Sweep of sibling create paths

Scanned all 26 `apply_carrier_b` call sites in categories.py for a preceding text copy (copy helper / ApplySyncableProperties / set_String within 60 lines). Variant types and complex-form types were fixed earlier (T127). Others show a copy or ApplySyncableProperties. Three sites showed no hit inside the 60-line window and were NOT verified: adhoc_compound_rules (~5411), natural_classes (~15490), phonological_rules structural update (~17986). They are a different shape (ApplySyncableProperties/_create_with_guid earlier in the function, probably) so nothing was changed. Follow-up: confirm those three copy Name/Description.

## 7. Git

Commit "fix(semantic_domains): ... (closes #131)" with Co-Authored-By Claude Opus 5.5; `git merge origin/main` was already up to date; pushed; PR #151 opened against main with "Closes #131". Not merged. Report not committed on main.
