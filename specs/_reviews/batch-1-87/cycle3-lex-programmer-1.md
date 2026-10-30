# Cycle 3 programmer report, issue #1

- New commit: 8ba74d2 (single commit on d9f55c9, unpushed). Trailer: exactly one, verified.
- Diff stat: fingerprints.py (+87/-17 area) and tests/unit/test_issue1_deriv_msa_pos_base_typed.py (+124) only. 194 insertions, 17 deletions.
- Unit: 5075 passed, 0 failed, 81 skipped, 14 xfailed (baseline +1). gramtrans.__file__ verified as the worktree.

## Changes
1. `_cast_msa_to_concrete` now catches only ImportError, logs a one-time warning (module flag `_CAST_IMPORT_WARNED`). `_cast_to_concrete` (categories.py:279-325) and `_cast_lcm` (11819-11855) are fail-soft: no ClassName returns the object, a missing interface returns the object, a refused cast is caught. `_unwrap_lcm` (267-276) only does getattr. So no broad guard is kept.
2. `msa_label_from_obj` docstring documents the "From>To" form and the ">v" / "Root>" forms.
3. New test: lazy import raises ImportError, the label falls back to the uncast concrete object, it does not raise, and the warning fires once across two calls.

## Step 4: is "Grammatical Info" compared?
Yes, it is compared. It is not display-only.
- merge_preview.py:3430-3432 adds the label as a nested child prop. `_add_child` (3346-3371) writes it into `props[mk]`. It skips empty values (3366).
- merge_preview.py:1531 merges those props into the entry props that `diff_props` (402) diffs. For OVERWRITE/MERGE_KEEP, `diff_props` compares per union key (494-511): equal values are unchanged, differing values are marked, and MERGE_KEEP notes a conflict for a nonempty target.
- The old "" label was dropped on both sides (3431, 3366), so a real POS difference between source and target was hidden. The new real labels let those differences show.
- Spurious diffs: none expected. Source and target use the same code and the same key (sense token + "Grammatical Info"). A difference now appears only when the abbreviations differ, or when one side's deriv POS is null (">v" vs "Root>v"). Both are real differences.
- Caveat: abbreviations are read with BestAnalysisAlternative, so a ws-dependent abbreviation could differ across projects. This is the same as the existing behavior for other fields. I made no fix.
