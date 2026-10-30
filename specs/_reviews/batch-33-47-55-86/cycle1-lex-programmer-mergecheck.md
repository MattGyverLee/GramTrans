# Cycle 1 merge check: PRs 86, 55, 33, 47

Worktree: D:/Github/_Projects/_LEX/GramTrans-review-batch-33-47-55-86 (branch review/batch-33-47-55-86, from aa0d36f; not pushed; PR branches untouched).
Note: origin/main has since advanced (5d0f886b -> 4211f7ed); this check is against aa0d36f as instructed.

## Merges (--no-ff, in order)
1. fix-86-census-rebaseline: clean
2. fix-55-gold-merge-liveness: clean
3. fix-33-scope-msa-slot-bindings: clean
4. fix-47-reconcile-guid-collision: clean (git auto-merged categories.py; no conflict markers)

Conflicts: none. No resolutions needed. STATUS.md only touched by #86.
Caveat: categories.py auto-merged textually (#33 +8/-? vs #47 +652); a semantic review of that file is still worthwhile.

## Unit suite
PYTHONPATH=<worktree>/src, python -m pytest tests/unit -q -p no:cacheprovider
Result: 5122 passed, 81 skipped, 14 xfailed, 0 failed (138.5s). Matches expected 5122.

## Import paths
gramtrans -> D:\Github\_Projects\_LEX\GramTrans-review-batch-33-47-55-86\src\gramtrans\__init__.py
flexicon -> D:Github_Projects_LEXlexiconlexicon__init__.py ; pyflexicon metadata version 4.13.0 (>= 4.8.0; no __version__ attr)
