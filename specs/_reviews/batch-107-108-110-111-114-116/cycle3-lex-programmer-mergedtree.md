# Cycle 3 merged-tree report (worktree GramTrans-review-batch-107-116, branch review/batch-107-116)

Final HEAD: d719a5d (local, not pushed). Reset to origin/main 7bfd571 from a clean tree.

## Merges (--no-ff, in order); all branch SHAs as expected
1. fix-108 6acb166 - clean
2. fix-116 e518a9b - ONE conflict: src/gramtrans/Lib/preview.py (two hunks, purely textual add/add)
   - ~1982-2137: kept #108 render_struct_type_features_rs in full, then `return tuple(lines)`, 2 blank lines, then #116 sense-field constant + render_sense_list_reference_decisions (own return).
   - tuple at preview.py:2133-2134: struct_type_features_rs line, then sense_list_reference_decisions line (requested order).
   - categories.py auto-merged with NO conflict (#108 and #116 hunks); models.py also auto-merged.
3. fix-107 2ea7b9a - clean
4. fix-114 236b44f - clean
No categories.py conflicts at any step. No conflict markers remain.

## AST parse
preview.py, categories.py, transfer.py: all OK.

## Imports
gramtrans -> GramTrans-review-batch-107-116/src/gramtrans/__init__.py; flexicon -> D:/Github/_Projects/_LEX/flexicon/flexicon/__init__.py (not site-packages).

## Tests
- tests/unit: 5384 passed, 80 skipped, 14 xfailed (cycle-1 5368 + 16 new; matches +10/+3/+2/+1). No failures.
- fidelity_census.py: 118 passed (first census run including #107).

## Survival greps
- categories.py: FEATURES_RS_REORDERED :3219 (used :3357, :3464); _thesaurus_new_ancestors :8849 (body inside try at :8862); _merge_entryref_value_fields :12463 with `existing=False` kwarg :12464, caller passes existing=True :12703.
- transfer.py: _record_unfilled_pos_collections :3428; _same_lcm_member :3087; _fill_created_pos_collections :3453; _ensure_complex_feature_type_ra :328 followed directly by _ensure_struct_type_features_rs :367.
- _LEAF_DISPATCH_CATEGORIES (:601): PHONOLOGICAL_FEATURES :603 precedes PHON_FEAT_TYPES :607; INFLECTION_FEATURES :622 precedes FEATURE_STRUCT_TYPES :625.
