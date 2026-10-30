# QC cycle3 -- issue #87 (commit 32cd022, rebased on 3a86bb0) -- static review only

**Score: 90/100 -- APPROVE.** No P0/P1. Cycle-2 P1 closed. Three P2s, none blocking.

(Saved by the main session: lex-qc has Read/Grep/Glob only. Static review -- QC could not run tests or `git diff`; it read the worktree files and the working-tree COMMIT_EDITMSG.)

## (1) residue.py strip helper -- OK

- Line-start matching only (`_is_tag_line`, residue.py:318); mid-line marker mentions are kept.
- `strip_residue_props` ws-alternative branch (residue.py:376-393) handles every alternative; an alternative holding only residue is dropped.
- Blank separator is popped; no-residue text is returned byte-identical. Traced "A\n\n[tag]", a leading-blank tag, and multi-tag history -- no stray blank.
- **P2 (residue.py:355):** the `rstrip` after a strip means a source Description ending in a newline never equals the stripped target, so that object would UPDATE every run. Disclosed by the programmer. Add a source-side trailing-newline normalisation or a test.

## (2) Comparison sites -- all covered

- Target side stripped at transfer.py:3383 (UPDATE disposition, apply and snapshot) and at the OVERWRITE executors (2248, 3590, 3641, 3726, 3825, 4026, 4061).
- Also stripped at categories.py:553 (sole caller `_plan_gold_reserved_edit`, :1021), conflict.py:403, merge_preview.py:3693 (`_fetch_props`).
- Unstripped `props_for` at merge_preview.py:1491 feeds only `_fetch_props`, so covered.
- Remaining `GetSyncableProperties` uses read the source or stamp new objects only (owned.py:716, references.py).
- Side effect at categories.py:559: a tag-only target Description vs a non-empty source now plans a gap-fill instead of a conflict -- correct.

## (3) Cycle-2 P1 -- closed

- `parse` uses `rfind` (residue.py:177): last tag line wins.
- UPDATE appends history first and the new line last (transfer.py:3416-3418).
- Non-snap stamps land only on created objects, snap-bearing stamps only on matched ones -- disjoint sets.

## (4) texts.py -- OK

`_apply_paragraphs` returns `(already, created_count)`; the count increments only after a successful create (:1357); the stamp gate is `_created or _paras_created > 0` (:825).

## (5) Live test -- strict on tags, but the exclusion filter is broader than the defect

- Check (1), no tag-line change on any pre-existing object, is unfiltered and fully strict.
- **P2 (test_issue87_residue_idempotent_live.py:63-65, :118):** whole-class excludes for MoInflAffMsa and FsFeatStruc changes -- a regression in those classes would pass. The docstring says this scenario never reaches MoInflAffMsa, so drop it.
- **P2 (:66-67, :118):** `_OWNER_LINK_BLOCKS` removes the whole AffixSlots / AffixTemplates / ReferenceForms blocks from PartOfSpeech, hiding any change to those fields, not just links to new objects. Narrow to references to excluded-class GUIDs.

## (6) Commit message -- OK

Exactly one unindented trailer (`Co-Authored-By: Claude Opus 5.5`). "closes #87" justified: the live test fails on main (11 PartOfSpeech + 4 Text re-stamped) and passes on the fix; the excluded template/slot defect has its own draft issue. (Programmer report names f5bff14 on d9f55c9; 32cd022 on 3a86bb0 is the rebased commit, with the trailer corrected by the main session.)

## Gates

Pattern audit / live evidence: the programmer reports live results (30 baseline failures unchanged, new test passes); QC could not confirm an evidence artifact under specs/.../evidence.
