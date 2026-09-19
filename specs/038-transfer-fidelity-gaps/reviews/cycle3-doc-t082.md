# cycle3-doc-t082: T082 / 038-NK-P3 closure check

**Task:** verify T126 measurement claims against artifacts, amend T082 (038-NK-P3 half only; 038-NK-P2 already settled/refuted, untouched), flip checkbox if both halves settled.

## Artifacts read (worktree `GramTrans-038-transfer-fidelity-gaps`)

Per pair, from `tests/integration/_snapshots/census-038-t126-{pair}.json` and `recensus-038-t126-{pair}.json`:

| pair | `PhNCFeatures` verdict_class | source/dest count | `totals.duplicate_extra_objects` | `verdict` | `exit_code` | recensus `phase_5.failures` (count, none = PhNCFeatures) |
|---|---|---|---|---|---|---|
| ejagham | MATCHED | 15/15 | 0 | UNEXPLAINED_SHORTFALL | 1 | 6 |
| ngoreme | MATCHED | 41/41 | 0 | UNEXPLAINED_SHORTFALL | 1 | 10 |
| mbugwe | MATCHED | 113/113 | 0 | UNEXPLAINED_SHORTFALL | 1 | 7 |

Matches the T126 claim exactly: was 3/21/66 duplicate objects and `DUPLICATE_IDENTITY`/exit 3 at T124; now 0/0/0 and `UNEXPLAINED_SHORTFALL`/exit 1 on all three. None of the 6/10/7 remaining P5 failure lines name `PhNCFeatures` (they're `CmPossibility`, `FsClosedValue`, `FsFeatStruc`, `LexReference`, `PhFeatureConstraint`, ngoreme `MoStemMsa`, `PhCode`, `LexEntryType`, `CmFile`, `CmFolder` -- T081/P5's residue, matching T081's line verbatim).

## Finding

The contract file (`contracts/natural-key-roster-extension.md` section 3.1) already carried a T086-style amendment narrowing `038-NK-P3` to the four originally-named losses (MSA subclasses, `PhPhoneme`, `PartOfSpeech`, `LexEntryInflType`, all confirmed recovered against T124) plus a note that the PhNCFeatures census-key fix was "predicted" to zero out `duplicate_extra_objects`. That prediction is now confirmed as measured fact by the real T126 artifacts. `038-NK-P3` is therefore met on both the amended per-row reading and the plainer T098 reading (PhNCFeatures duplicates, which were the sole open claim as of 2026-08-22, are now genuinely zero). Searched both files for the struck "sources have moved off their pinned digests" premise (T081's 2026-08-28 amendment) -- it does not appear anywhere in the contract file, and T082's own tasks.md text had already struck it citing T081. Nothing further to strike.

**Verdict: 038-NK-P3 CLOSES. Combined with 038-NK-P2 (already SETTLED/REFUTED 2026-08-26, untouched here), T082's checkbox flips `[ ]` -> `[x]`.**

## Files edited

- `D:\Github\_Projects\_LEX\GramTrans\specs\038-transfer-fidelity-gaps\tasks.md` -- appended a closing 2026-08-28 note to T082's line citing the T126/recensus artifacts by name, and flipped its checkbox to `[x]`.
- `D:\Github\_Projects\_LEX\GramTrans\specs\038-transfer-fidelity-gaps\contracts\natural-key-roster-extension.md` -- appended a "Closure, 2026-08-28 (T126 artifacts)" paragraph to section 3.1 with the same figures.

No source code touched. No docstrings touched.
