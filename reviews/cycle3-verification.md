# Verification Report - cycle3 (independent, no files modified)

**Date:** 2026-07-15
**Worktree:** d:\Github\_Projects\_LEX\GramTrans-msa-slot-wiring-v2
**Commit under test:** 95cfb81 "fix(preview): populate msa_slot_bindings via IMoInflAffMsa cast (FR-333, #28 MSA->slot leg)"
**Status:** PASS

## 1. HEAD / tree cleanliness

```
git log -1 --format="%H %s"
95cfb81c571d9b2448c2dee12db7c1fff99a1101 fix(preview): populate msa_slot_bindings via IMoInflAffMsa cast (FR-333, #28 MSA->slot leg)

git status
On branch msa-slot-wiring-v2
Untracked files:
  reviews/
nothing added to commit but untracked files present
```
HEAD matches exactly; only untracked item is this verification report's own directory (created by this run, not a pre-existing dirty-tree condition). **PASS.**

## 2. py_compile

```
python -m py_compile src/gramtrans/Lib/categories.py src/gramtrans/Lib/preview.py
PY_COMPILE_OK
```
Both files compile cleanly with no syntax/import errors. **PASS.**

## 3. Single-producer claim for `msa_slot_bindings`

Grepped the entire `src` tree for `msa_slot_bindings`. Findings:

- **models.py:696** — dataclass field declaration only (`msa_slot_bindings: dict = field(default_factory=dict)`), not a write site.
- **preview.py:390** — `_populate_msa_slot_bindings(source, _msa_slot_bindings)` call inside `build_run_plan`, the sole call site.
- **preview.py:801-915** — `_populate_msa_slot_bindings` (the producer). Casts each MSA to `IMoInflAffMsa` (live LCM) and writes `msa_slot_bindings[msa_guid] = slot_guids` at **line 915** when `slot_guids` is non-empty.
- **preview.py:878/890** — falls back to `_populate_msa_slot_bindings_duck` when `SIL.LCModel` casts are unavailable or the entries are duck-typed fakes (host-free unit tests).
- **preview.py:918-940** — `_populate_msa_slot_bindings_duck` (the duck fallback), writes `msa_slot_bindings[msa_guid] = slot_guids` at **line 940**.
- **categories.py:2934-2986** — `_stash_entry_bindings`. Confirmed this function **only** writes to `lexentry_ref_bindings` (via `ref_map`) and `entryref_create_bindings` (via `create_map`). Its docstring (lines 2949-2953) explicitly documents that the formerly-present duck-only `msa_slot_bindings` branch was **removed in cycle-2 (#28 QC-P1#2)** because it no-op'd on live LCM and used a different GUID formatter than preview.py's duck fallback. No `msa_slot_bindings[...] =` write exists anywhere in categories.py — confirmed by grep, the only categories.py references to the string are comments/docstrings and the **consumer** at `_run_171_subpass`.
- **categories.py:4954** (consumer) — `_run_171_subpass` reads `plan.msa_slot_bindings` (direct-plan path, line 4970) or `_binding_map(context, "msa_slot_bindings")` (context-attribute path, line 4973). Read-only; no writes.
- **transfer.py:348** — comment only, no write.

**Conclusion:** exactly ONE producer path remains for `msa_slot_bindings` — `_populate_msa_slot_bindings` in preview.py (line 801, live-LCM `IMoInflAffMsa` cast writing at line 915) with its duck-typed fallback `_populate_msa_slot_bindings_duck` (line 918, writing at line 940). The previously-present duck-only write inside categories.py's `_stash_entry_bindings` is confirmed gone (removed, documented in the docstring). Consumer is `_run_171_subpass` at categories.py line 4954. **PASS — matches the claim exactly.**

## 4. Sibling bindings remain untouched producers (not consumer-only)

Grepped for `lexentry_ref_bindings`, `entryref_create_bindings`, `feature_category_links`:

- **`lexentry_ref_bindings`** — still produced in categories.py's `_stash_entry_bindings` (categories.py:2954, 2963-2969, writing into `ref_map`). Consumed in categories.py (~5202-5219, "wire ... after both affix and stem entries are stable"). Producer path intact and unchanged by this fix.
- **`entryref_create_bindings`** — still produced in the same `_stash_entry_bindings` function (categories.py:2955, 2970-2986, writing into `create_map`, unconditional per `EntryRefsOS` member). Consumed at categories.py ~5056-5104. Producer path intact.
- **`feature_category_links`** — still produced by `_stash_feature_category_links` (categories.py:2989-3004+, called from `gram_categories_plan_action`). Consumed by the Move wiring post-pass `_run_infl_feature_link_pass` and rendered via `preview.py:render_feature_category_links` (line 573). Producer path intact.

None of these three siblings were converted to consumer-only or otherwise touched by the 95cfb81 fix — their producer functions (`_stash_entry_bindings`, `_stash_feature_category_links`) remain fully in place in categories.py, only the msa_slot_bindings-specific dead branch was excised from `_stash_entry_bindings`. **PASS.**

## 5. Test counts

### tests/unit/test_preview_msa_slot_bindings.py
```
..........  [100%]
10 passed in 0.17s
```
Expected 10 passed — **matches exactly. PASS.**

### tests/unit (full suite)
```
1 failed, 1590 passed, 9 skipped, 14 xfailed, 14 xpassed in 6.71s
```
Expected: 1590 passed, 1 failed, 9 skipped, 14 xfailed, 14 xpassed — **matches exactly.**

The single failure is:
```
FAILED tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
AssertionError: assert 0 == 1
 +  where 0 = len([])
```
This is the documented pre-existing baseline failure (unrelated POS-closure wiring gap, not touched by this commit). No other failures observed — **no regressions. PASS.**

### Renamed tests
```
tests/unit/test_categories_affixes.py::test_plan_action_does_not_stash_msa_slot_binding PASSED
tests/unit/test_categories_stems.py::test_plan_action_does_not_stash_msa_slot_bindings PASSED
```
Both renamed tests exist and pass, confirming `_stash_entry_bindings` no longer stashes `msa_slot_bindings` in either the affix or stem plan-action path. **PASS.**

## Final Assessment

**Overall Status: PASS**

All five verification items confirmed exactly as claimed:
1. HEAD = 95cfb81, tree clean.
2. py_compile clean on both files.
3. Single-producer claim confirmed: sole producer is `_populate_msa_slot_bindings` (preview.py:801) + duck fallback `_populate_msa_slot_bindings_duck` (preview.py:918); the old duck-only branch in categories.py's `_stash_entry_bindings` is gone (documented removal, cycle-2 #28 QC-P1#2); sole consumer is `_run_171_subpass` (categories.py:4954).
4. Sibling bindings (`lexentry_ref_bindings`, `entryref_create_bindings`, `feature_category_links`) remain intact producers in categories.py, untouched by this fix.
5. Test counts match exactly: 10/10 in the targeted file; 1590 passed / 1 failed / 9 skipped / 14 xfailed / 14 xpassed in the full suite, with the single failure being the documented pre-existing `test_plan_emits_pos_action_for_picked_pos` baseline. Both renamed tests exist and pass.

**No regressions found. No blockers. Recommend APPROVE.**

---
**Verified By:** Verification Agent
**Date:** 2026-07-15
