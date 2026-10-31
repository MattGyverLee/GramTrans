# cycle1-lex-qc-110 (PR #121, HEAD ce672ad)

> Saved by the main session: lex-qc has no Write tool and returned this text verbatim.

88/100, APPROVE (no P0 or P1). Nothing was run live. The live-evidence gate PASS rests on impl-110.md section 5; I did not look for the evidence artifact under specs/<feature>/evidence/.

Q1, no path skips the tail: confirmed, with one caveat.
- The only dispatch is transfer.py:773, and the tail runs unconditionally at transfer.py:874 (own latch, outside the per-leaf try).
- `_stash_complex_feature_type_ref` is the first line of `inflection_features_plan_action` (categories.py:1522), before any GOLD skip or overwrite. Closure pull-ins also go through `plan_action` (preview.py:696, 837, 1445).
- P2: the tail reads the edge map through `_binding_map` (categories.py:5280), so a hand-built plan not made by `build_run_plan` leaves TypeRA null. The old create path used to cover that case. Production plans are fine.

Q2, picks asymmetry: confirmed inert today.
- `leaf_item_picks` is written only by `collapse_phonology` and the custom-field, rules and stems pages (selection.py:2944, 3666; selection_wizard.py).
- No INFLECTION_FEATURES group exists in any of them, and ui/ has none.
- P2: categories.py:2006 is a latent trap. Add a comment or a guard test.

Q3, mutation test: sound as a pin on the test harness, mildly brittle.
- It monkeypatches `LEAF_CATEGORIES[...]["execute_action"]` via `setitem`, which works because transfer.py:773 indexes the dict at call time.
- It shows the count assertion bites. The product pins are the unit test and the main live test, both shown to fail on old code.
- P2: it asserts the defect (`writes == 0`) and hardcodes source GUIDs in `EXPECTED`. It breaks if the count semantics change legitimately, or if the source project is edited.

Q4, HIGH sibling at transfer.py:3074: shape is real, but the HIGH rating is not confirmed.
- Enrichment `live.Add` (3074) is counted by `added += 1` (3253) before the link pass.
- `_run_infl_feature_link_pass` (categories.py:12333-12338) then skips the existing pair and has no counter.
- The enrichment count is reported via `EnrichedCollection.added`, so the total is not necessarily short against Preview's Link rows. Treat it as MED until reproduced, and file it as its own issue.

P0: none. P1: none. P2: the caveat, trap and brittleness points above.
