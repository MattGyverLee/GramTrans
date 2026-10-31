# QC cycle 2: PR #151 (#131, 7270299) and PR #152 (#133, f3618dc)

> Saved by the main session. The lex-qc agent had no Write tool and returned this report as its final message.
> It was a read-only review of the staged diffs and the clean checkouts GramTrans-qc-7270299 and GramTrans-qc-f3618dc. Nothing was run live.
> The reviewed SHA is f3618dc. The branch has since moved to 971c3b32, a main merge verified in cycle2-lex-programmer-133merge.md.

## Gates
- **Pattern audit:** the reviewer did not check the commit or PR bodies. The Q2 table below is a sibling sweep for #131.
- **Live-LCM evidence:** both live tests exist: `test_issue131_semdomain_create_live.py` and `test_issue133_pos_inflfeats_live.py`. No `specs/**/evidence/live-*131*/*133*.md` artifact was found. Confirm the live evidence before #152 merges.

## #131 (merged): 90/100

**Q1: yes.** `_copy_multistrings_ws_mapped` runs before `apply_carrier_b` in both create branches: the nested-owner closure (~4670) and the demoted top-level branch (~4689). The [GT-Tag] line therefore stays last. Unit tests cover both branches.

**Q2: sibling create sites at 7270299**

| Site | Copies on create? | Where | flexicon emits |
|---|---|---|---|
| adhoc_compound_rules | Yes (Name/Description) | categories.py:5250-5253 | Name, Description (MorphRuleOperations.py:1208); no Abbreviation needed |
| natural_classes | Yes (Name/Abbreviation/Description) | categories.py:15350-15351 | All three (NaturalClassOperations.py:1165) |
| phonological_rules (create) | Yes (Name/Description) | `_phon_rule_apply_body` categories.py:17277-17278 | Name, Description (PhonologicalRuleOperations.py:2046) |
| phonological_rules (structural update) | Yes | same body, through `_execute_phon_rule_structural_update` (18121) | same |

None of these sites has the #131 gap. The caveat is that each one swallows a text-copy failure:
- adhoc (5252): `except (AttributeError, TypeError): pass`
- phon (17279): `except Exception: pass`
- natural classes (15352)

**#131 findings**
- **P2:** the three silent swallows above. Follow-up issue suggested.
- **P2:** the unit tests stub SIL.LCModel, so the live test carries the real proof.

## #133 (open): 72/100

**Q3: test inversions**
- **test_031** (`test_gathers_even_when_features_not_selected`): an intentional reversal, not a weakening. The absent-feature drop is covered by `test_133::test_feature_absent_from_target_is_a_dependency_drop`.
- **test_038_enrichment_executor** (2 tests): the old link and drop behaviour moved to the pass tests in test_133. **Gap:** no test chains a created POS through deferred enrichment into the link map and then the pass. That is the #107 end-to-end path.
- **test_categories_pos_inflectable_feats** (2 tests): slightly weakened. The executor now records intent for a feature that may not exist, and only the pass reports it.
- **P2:** `test_enrichment_has_no_inflectable_feats_writer` and `test_link_pass_is_not_anchored...` assert on `inspect.getsource` strings, which is brittle.

**Q4: interaction with #107**
- `_fill_created_pos_collections` (transfer.py:889) relied on the enrichment write, which is now `deferred`.
- `_ensure_infl_feature_links` (transfer.py:970) covers that case only if the pair is in `plan.feature_category_links`.
- The stash (categories.py:5737) covers in-scope POS. Coverage of a POS created only through dependency closure was not verified.
- **P1 (transfer.py:3304-3320): `deferred` pairs are reported nowhere.** A deferred pair is silently lost if:
  - the pair is absent from the link map (the leaf-pick filter at categories.py:5775-5799, or a closure-created POS);
  - `_run_plan` is None (transfer.py:344 returns silently);
  - the pass raises (transfer.py:356 only logs).

  The old code reported drops. **Fix:** after the pass, reconcile the deferred pairs against the pairs it confirmed or dropped, and emit a drop for every remainder.

**Q5: no stranded callers.** In src/, `inflection_features_execute_action` appears only at its definition and its registry entry (categories.py:18358). `_run_infl_feature_link_pass` is called only from `_ensure_infl_feature_links` (transfer.py:355), and that only from `execute()` (970). Nothing in api.py or the FlexTools module paths calls them.

**Q6: the read-back is sound** (categories.py ~13049-13095).
- A no-op Add is not counted and produces a WRITE_FAILED DroppedItemRecord plus a Skip.
- A raising Add follows the same path.
- A raising read-back is treated as unconfirmed.
- An existing pair hits `continue` before the read-back and is not counted.

Q6 P2s:
- The WRITE_FAILED Skip is labelled GRAM_CATEGORIES / DEPENDENCY_UNRESOLVED, which misleads.
- An absent feature is reported twice (Skip plus drop).
- An Add that raises after partially applying still counts if the read-back finds the pair.

**Q7: Preview and Move are consistent in logic.**
- `_target_feature_present` uses the same `categories._resolve_target_by_guid` resolver as Move. It falls back to `target.ObjectRepository`, so it works on a live project.
- The POS lookup goes through `_resolve_target_pos`.

Q7 P2s:
- Preview shows "Link" when a feature is planned but its create fails in Move.
- Preview shows "Link" when the POS is absent and not planned, while Move skips it.

**Q8: the domain ruling is honoured.**
- The pass only adds links to existing features. It never creates or edits a feature.
- Feature creation stays only in `inflection_features_execute_action`, which runs only when that category is selected.
- **P2:** `_resolve_target_by_guid` does not type-check its result. A wrong-type hit fails at Add and becomes WRITE_FAILED.

**Other P2s**
- A dead `finally: pass` in `inflection_features_execute_action` (~1943).
- Stale `_run_tail_once` comments at categories.py:5743 and models.py:3641-3643.

## Recommendation
- **#151:** no action beyond the P2 follow-up issue (silent text-copy swallows).
- **#152: FIX ISSUES.**
  - Fix the P1 deferred-pair reconciliation.
  - Add an end-to-end test that takes a created POS through deferred enrichment into the link map and the pass.
  - Confirm the live evidence.
