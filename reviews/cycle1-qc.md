# QC Report — MSA Slot-Binding Producer (msa-slot-wiring-v2, aa7788b)

**Date:** 2026-07-15
**Quality Score:** 72/100
**Status:** ISSUES (gate-blocked)

## Pattern-Audit Gate
- Sweep present in commit body (aa7788b): ABSENT
- Bug shape: matches BOTH (a) declared+consumed-never-*effectively*-produced dict (commit body itself: "dict was declared, threaded... yet never populated") and (b) getattr-over-live-LCM-cast drop (docstring, preview.py:806-810)
- Gate status: **BLOCK** — return to `/lex-programmer` to add a "Pattern audit" section (sibling table below may be reused) to the commit message before merge.

## Sweep-Audit Table (required)
| Binding | Producer | Consumer | Status |
|---|---|---|---|
| `msa_slot_bindings` | preview.py:801 `_populate_msa_slot_bindings` (**new, this PR**) + categories.py:2948-2954 `_stash_entry_bindings` (old, still present, unremoved) | categories.py:4956 `_run_171_subpass` | Was CONSUMER-ONLY-on-live/BUG; **fixed** by this PR |
| `lexentry_ref_bindings` | categories.py:2956-2971 `_stash_entry_bindings`, called from AFFIXES (5512) + STEMS (5900) | categories.py:5204/5218 tail pass | PRODUCED (027) — verified |
| `entryref_create_bindings` | categories.py:2957,2972-2988 `_stash_entry_bindings`, same call sites | categories.py:5058/5103 | PRODUCED (027) — verified |
| `feature_category_links` | categories.py:2991-3006 `_stash_feature_category_links`, called categories.py:362 | categories.py:5349/5366 `_run_infl_feature_link_pass` | PRODUCED (031) — verified |

No other consumer-only siblings found. Spot-check of `lexentry_ref_bindings` producer call site (5512) confirmed real (not a stub).

## P0
- Pattern-audit section missing from commit message — HARD-BLOCK per gate.

## P1
1. **preview.py:387-390** — `_populate_msa_slot_bindings` scans the entire source lexdb unconditionally, ignoring `Selection.leaf_picks_for(AFFIXES/AFFIX_TEMPLATES)` (categories.py:5475, 5690). Consumer `_run_171_subpass` (categories.py:4978-4999) has no scope guard, so GUID-preserved but out-of-leaf-pick MSAs will resolve to `None` in target -> false `Skip(DEPENDENCY_UNRESOLVED)` noise. Untested: all 10 tests use `Selection(categories={})`, never a partial leaf-pick. (Corroborated by domain review P1.)
2. **categories.py:2948-2954** — old, still-broken `_stash_entry_bindings` msa_map branch left in place, writing the same dict via a different guid-format helper (`_guid_str_from`, categories.py:102) than the new inline `str(...Guid).lower()` (preview.py:909-910). Dead/duplicate producer (its live output is always empty; its fake output duplicates the new duck fallback) — DRY violation, divergence risk. Remove or converge.
3. **preview.py:866-915** — 0% test coverage of the live-LCM cast path (the actual bug fix). All 10 tests exercise only `_populate_msa_slot_bindings_duck`.

## P2
- preview.py:873 `except (ImportError, Exception)` — redundant tuple.
- preview.py:801-915 — single 115-line function, could split cast-mode detection out.
- preview.py:892/900/911 broad `except Exception` — consistent with repo style but masks real bugs.

## Final Assessment
**Overall Score:** 72/100
**Recommendation:** FIX ISSUES (gate-blocked — see P0)

---
**Reviewed By:** QC Agent
