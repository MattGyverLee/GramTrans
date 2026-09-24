# Cycle 14 -- Archivist dossier: T085 merge hazard + spec-artifact divergence

**Date:** 2026-09-18
**Trees confirmed (both read-only for this task; no merge/commit/checkout performed):**
- `main` at `D:/Github/_Projects/_LEX/GramTrans` -- HEAD `7d9965bc7da52e591f29c36a021e97c766aaedd1` (`7d9965b chore(038): ignore the companion run self-trace`)
- `038-transfer-fidelity-gaps` at `D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps` -- HEAD `6811894276d9558f489e8aa44b8afdadae2e601f` (`6811894 fix(038): T081 -- a null ContentRA is not a dangling one, plus the per-list dimension`)
- `git merge-base main 038-transfer-fidelity-gaps` = `4a319af7bccb27d1487bd4dc4d98ca78ee24a7a6`

**Method note:** to enumerate the conflict precisely I ran a real `git merge --no-commit --no-ff 038-transfer-fidelity-gaps` inside a throwaway third worktree (`scratchpad/merge-probe`, detached from `main`, created solely for this analysis), inspected the conflict markers and the auto-merged result, then ran `git merge --abort` and `git worktree remove --force` on that throwaway worktree only. Neither `main` nor the `038-transfer-fidelity-gaps` worktree was touched, checked out into, or committed to at any point.

---

## PART A -- T085's pre-identified merge hazard (tasks.md:610)

### The full conflict set (confirmed empirically, not just by merge-tree diffing)

```
Auto-merging tests/integration/harness/full_run.py
CONFLICT (content): Merge conflict in tests/integration/harness/full_run.py
Auto-merging specs/038-transfer-fidelity-gaps/contracts/fidelity-census.md      <- clean, no conflict
Auto-merging specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json  <- clean, no conflict
Auto-merging debug/run_fullcopy_sweep.py
CONFLICT (content): Merge conflict in debug/run_fullcopy_sweep.py
```

Only two files actually conflict. Everything else under specs/038-transfer-fidelity-gaps/
and every other 038 file (all the debug/run038_*.py, tests/unit/test_038_*.py,
tests/integration/test_038_*.py, all _snapshots/*-038-*.json, src/gramtrans/Lib/*.py,
src/gramtrans/census_cli.py) merges as a clean addition (038 added files/hunks main
never touched). Verified: `git diff main -- . ':!debug/run_fullcopy_sweep.py'
':!tests/integration/harness/full_run.py'` inside the merged probe tree shows nothing but
A (new 038 files) and additive hunks -- no unexpected loss anywhere outside the two
named files.

### Root cause of both conflicts: real, both-legitimate divergence since feature-035

debug/run_fullcopy_sweep.py since the merge-base:
- **main** (6 commits, all feat(035): 8235f4f, e60b8ba, f72c29a, 66fe390, 88c2632, 58cc970) -- feature-035 promoted the sweep monolith into a debug/fullsweep/ package and replaced the file's compare_objects stub with reconcile_project_objects / findings_from_accounting / payload_never_compared / drop_records_from_artifact. Confirmed: feature-035 is fully merged to main (`git merge-base --is-ancestor 7011b5b main` -> true; the 035-fullsweep-fidelity worktree at D:/Github/_Projects/_LEX/GramTrans-035-fullsweep HEAD 7011b5b has zero commits not already in main). Main's copy is therefore the current, landed, authoritative state -- not a stale side branch.
- **branch** (1 commit, `2c5d797 docs(038): T097 -- the stub whose replacement had already been written`) -- a pure 26-line comment insertion into the branch's own stale compare_objects stub (no behaviour change; stat confirms "1 file changed, 26 insertions(+)", zero deletions). The commit's own message is definitive: "the replacement is not this branch's to write, because it already exists on the branch that owns the file... Re-implementing the comparator here would fork another feature's instrument, duplicate finished work, and conflict with the branch that is ahead. The correct resolution is that 035's version lands with 035."

tests/integration/harness/full_run.py since the merge-base:
- **main** (58cc970, feat(035) T045a): added a plain positional `exclude: Optional[frozenset] = None` parameter to run_full_transfer.
- **branch** (5fa53d7 feat(038 T024c), then fe81a55 T070/T071/T072, 4d56c65 T067): independently reinvented the same exclude need but as part of a keyword-only block (`*, exclude=None, ws_mapping_mode="default-vernacular", report_path=None, preview_only=False, selection_transform=None`), because the branch diverged before 58cc970 landed.

### Hunk-by-hunk resolution

**1. debug/run_fullcopy_sweep.py -- one conflicting hunk (build_run_context / reconcile_project_objects vs compare_objects), ~lines 418-505 (base numbering)**
- Introduced by: main side = 66fe390/58cc970 (feature-035); branch side = 2c5d797 (feature-038, T097).
- **Proposed resolution: take-main.** Authorized in writing by the branch's own commit message (quoted above). Nothing on the branch calls compare_objects (grep confirms zero call sites outside its own definition); reconcile_project_objects is main's real, tested, landed implementation. The branch's 26-line doc paragraph exists precisely to record this and can be dropped once the merge lands (its content is now historical, not a standing instruction).
- **This is a hunk-level take-main, not a whole-file `-X ours`.** The rest of the file's differences (the entire safety/corpus/ledger machinery: WriteSafetyError, ExclusiveTargetClaim, CorpusEntry, SourceFingerprint, Ledger, etc., ~1337 lines on the branch vs 1126 on main) auto-merge cleanly because the branch made no other edits to this file since the base -- main's 035 restructure (moving that machinery into debug/fullsweep/) applies without conflict since branch and base agree everywhere else.

**2. tests/integration/harness/full_run.py -- two conflicting hunks**
- **Hunk 2a (signature):** main side is `exclude: Optional[frozenset] = None,`; branch side is `*, exclude: Optional[frozenset] = None, ws_mapping_mode: str = "default-vernacular", report_path: Optional[str] = None, preview_only: bool = False, selection_transform=None,`.
  - Verified safe to make exclude keyword-only: every call site in both trees (debug/run_fullcopy_sweep.py:600,627 on main; every debug/run038_*.py call on branch; every tests/integration/test_*.py call in both trees) either passes only 3 positional args (source, target, path) or passes exclude=... by keyword already. Zero callers pass a 4th positional argument anywhere in either tree.
  - **Proposed resolution: hand-integrate = adopt branch's full signature.** It is a strict superset: it already contains main's entire contribution (exclude: Optional[frozenset] = None) plus the four keyword-only params 038 needs (ws_mapping_mode, report_path, preview_only, selection_transform). Confirmed empirically by re-running the merge probe and reading the fully-merged body below the conflict: every one of the branch's downstream uses of ws_mapping_mode/preview_only/report_path auto-merges cleanly against main's untouched code, so branch's signature is not just compatible but already the file's working shape everywhere except these two conflict markers.
- **Hunk 2b (body):** immediately after `selection = (build_full_selection() if exclude is None else build_full_selection(exclude=exclude))`, main's side is empty; branch adds `if selection_transform is not None: selection = selection_transform(selection)`. Main contributed nothing here.
  - **Proposed resolution: hand-integrate = take branch's addition** (main's side is empty; this is a pure branch addition that git only flagged as conflicting due to adjacency to hunk 2a's context lines, not a competing edit).
- Net effect: the merged run_full_transfer signature and body are, hunk for hunk, exactly branch's current content -- but arrived at by hand-integration (verifying no caller breaks, verifying main contributes nothing unique in either hunk) rather than a wholesale `-X theirs`, which the task explicitly prohibits and which would also be substantively wrong for the *other* conflicting file (run_fullcopy_sweep.py, which resolves the opposite direction, take-main).

### Ownership / sign-off for feature-035's landing

- Branch: 035-fullsweep-fidelity; worktree: D:/Github/_Projects/_LEX/GramTrans-035-fullsweep (HEAD 7011b5b).
- Feature-035 is already fully merged to main via `19653a6 merge: 035 fullsweep lands on main, additive and green`, plus a later `49da83b docs(035): the 038 cut -- allowlist struck, field plane kept, corpus gated` (also on main). `git merge-base --is-ancestor 7011b5b main` returns true -- zero unmerged commits remain on the 035 worktree.
- **Practical consequence for sign-off:** there is no live 035 owner left to consult for a code decision on debug/run_fullcopy_sweep.py -- main's copy already IS feature-035's final, landed word on that file. The person whose sign-off the integration needs is whoever authorizes the 038 -> main merge itself (i.e. T085, gated per tasks.md:610 on Phase 10 / T124 / T125 / 038-NK-P3), not a separate 035 reviewer. The 035 worktree is stale bookkeeping and should eventually be removed (out of scope for this dossier; not touched).

---

## PART B -- spec-artifact inventory, specs/038-transfer-fidelity-gaps/ (main vs branch)

`git diff --name-status main 038-transfer-fidelity-gaps -- specs/038-transfer-fidelity-gaps/`
splits cleanly into two groups:

### B.1 -- Files present on main only (~100 files: contracts/*-rulings.md, all of journal/*.md,
all of probes/**, all of reviews/*.md, .crew-handoff.json, .gitignore)

**Not a problem.** These are exactly the protocol working as designed: sessions running
against main (or committing spec output straight to main per CLAUDE.md's Git Workflow
Protocol) produced them; the 038 worktree never fast-forwarded to pick them up because
it has been living at/near the merge-base for these paths. No divergence -- branch is purely
behind. They arrive on the branch for free the moment main is merged into it (or reached
via the eventual 038->main merge); no action needed now.

### B.2 -- Files modified on both sides ("M" in name-status): the only ones needing a decision

| file | branch's own commits since base | verdict |
|---|---|---|
| .spec-context.events.jsonl | none (unchanged since 4a319af) | main strictly ahead; branch stale only. Safe, no action. |
| .spec-context.json | none | same. |
| contracts/natural-key-roster-extension.json | none | same. |
| contracts/natural-key-roster-extension.md | none | same. |
| spec.md | none | same. |
| tasks.md | none | same. |
| contracts/fidelity-census.md | commits exist (accd761, 8501f23, b2cb356, 36ae30f), but every line the branch ever added to this file is already among main's added lines (comm -23 of the two diffs' +-sets against 4a319af returns 0 lines) | main is a strict superset. This is the file named in the task's deliberate-exception clause. |
| contracts/census-artifact.schema.json | 6811894 (T081, today) added the owning_lists property | real, isolated divergence -- see below. |

For tasks.md/spec.md/.spec-context.*/natural-key-roster-extension.*: confirmed via
`git diff 4a319af 038-transfer-fidelity-gaps -- <file>` returning empty for all six --
the branch has not touched them at all since the merge-base. They are not a "divergence" in
the merge-conflict sense at all, just staleness, and carry no risk.

### B.3 -- The one real divergence: contracts/census-artifact.schema.json's owning_lists

- **Confirmed via comm:** every +-line the branch ever added to this file since the base
  is the owning_lists property block (14 lines: the property definition, its $comment,
  and its JSON Schema scaffolding) -- nothing else. Main's independent additions since the
  base (the baseline_gross zero-baseline carve-out comment, UNREFERENCED_IN_SOURCE added
  to the reason enum and to report_ref's exemption list) are untouched by the branch and
  auto-merge with owning_lists without conflict (verified: git merge-tree and the real
  probe merge both show "changed in both" with no conflict markers for this file).
- **This is the protocol inversion the task asked me to find.** Commit 6811894 on the
  branch is "fix(038): T081 -- ... plus the per-list dimension". Its own commit message
  documents FOUR files as the T081 PIECE 2 implementation: census.py (code, correctly
  worktree-only), models.py (code, correctly worktree-only), census_cli.py (code,
  correctly worktree-only), and census-artifact.schema.json (a specs/ contract file,
  which the repo's Git Workflow Protocol requires to commit to main directly). Only the
  fourth was committed to the wrong tree.
- **Safe to move now?** Yes, structurally: (a) it auto-merges with main's independent later
  edits to the same file with zero conflict, textually verified twice (merge-tree and a
  real git merge --no-commit); (b) the corresponding CODE (census.py, models.py,
  census_cli.py) that depends on owning_lists existing in the schema is on the branch
  and stays there per protocol, so moving only the schema fragment to main does not create
  a code/spec mismatch on main (main has no code reading owning_lists, so an unused-but-
  present schema property is inert there, exactly like every other 038 schema addition
  already sitting ahead of its own code on main, e.g. UNREFERENCED_IN_SOURCE). The
  commit's own message frames this as "NOT YET MEASURED LIVE" for the CmPossibility gate
  consequence, but that caveat is about the gate, not about the schema shape being unready
  to publish.
- **Companion prose gap, also confirmed:** contracts/fidelity-census.md (on main, on the
  branch's stale committed copy, and in the branch's deliberately-dirty working copy) contains
  zero occurrences of the literal string "owning_lists" anywhere. The schema field is
  undocumented in the prose contract on both trees. (The document does reference the general
  concept -- section 4's "per-owning-list dimension" -- in prose, but never names the
  concrete $defs.classRow.owning_lists field the way it names every other classRow field.)
  This is a doc-content gap, not code or archivist work: flagged for /lex-doc, not
  drafted here.

---

## PART C -- Prose sites that now need amending (T081 PIECE 1's refutation of straggler-rulings.md #5)

Commit 6811894's own message names two sites explicitly and says the ruling "is left
standing and contradicted here rather than quietly edited, because the amendment is a spec
artifact and commits to main." Inventorying every site carrying the refuted claim
("MoAffixProcess's ejagham refusal is correct/pre-existing and no fix is available/exists"),
not just the two the commit names:

### C.1 -- Sites asserting the refusal as a standing, present-tense ruling (need real amendment)

1. **specs/038-transfer-fidelity-gaps/contracts/straggler-rulings.md:151** (ruling prose, section "## 5. MoAffixProcess"):
   "Ruling: correctly refused; no fix is available in this repo."
2. **specs/038-transfer-fidelity-gaps/contracts/straggler-rulings.md:189** (summary table row):
   "| 5 | MoAffixProcess | correctly refused, source-side cause | none possible |"
3. **specs/038-transfer-fidelity-gaps/contracts/straggler-rulings.md:8** (document framing, immediately under the title "The six stragglers, ruled one at a time"):
   "One needed code; the other five did not, and saying why is the deliverable."
   -- now two needed code, not one; the framing sentence itself is stale.
4. **specs/038-transfer-fidelity-gaps/tasks.md:503**, inside the closed T107 entry, the clause:
   "...its Content is EMPTY IN THE SOURCE -- verified in the .fwdata, a copy step with nothing to copy, and the FR-023 refusal is correct and pre-existing."
5. **specs/038-transfer-fidelity-gaps/tasks.md:597**, inside the still-open T081 entry's fourth/fifth re-gate narrative, the "kind (ii)" bucket that classifies MoAffixProcess as a "ruled, no-accounting-line" residue class alongside CmFile/CmFolder/LexEntryType/PhCode:
   "...CmFile / CmFolder / LexEntryType / MoAffixProcess / PhCode (all ruled in contracts/straggler-rulings.md and contracts/boundary-marker-code-ruling.md)."
   -- once PIECE 1 is live-measured, MoAffixProcess likely moves out of "ruled residue" entirely (a real transfer fix, not an accounting-line fix), which changes this bucket's membership, not just its footnote.
6. **specs/038-transfer-fidelity-gaps/journal/T107-the-blocker-behind-the-blocker.md:89**:
   "There is nothing to copy. The refusal is correct and pre-existing."
7. **src/gramtrans/Lib/models.py:1469-1480** (branch/worktree, D:/Github/_Projects/_LEX/GramTrans-038-transfer-fidelity-gaps; code comment, not a specs/ file, so it commits with the branch, not main -- named anyway because the task and the commit message both call it out by name):
   "MoAffixProcess. Its ruling (straggler-rulings.md #5) DOES support a line -- 'correctly refused; no fix is available in this repo'... [explains why the census roster excludes it]"
   -- the entire paragraph's premise (no fix available) is gone; the paragraph's conclusion
   (don't roster it via CENSUS_RULED_RESIDUE_CLASSES, because Phase 4 already has an
   executable gate on it) may still hold on independent grounds (T109 LOCK 1), but that needs
   re-derivation, not just a one-line edit.

### C.2 -- Sites carrying the historical "13 -> 12" measurement (accurate as history; will need a forward note once PIECE 1 is live-measured, but are not themselves false)

8. specs/038-transfer-fidelity-gaps/tasks.md:687 (closed T118 entry): "MoAffixProcess IS 13 -> 12, NOT 13 -> 0 -- the ejagham destination is post-T107 and that one missing rule is also what costs the 5 affix-process contexts in T116."
9. specs/038-transfer-fidelity-gaps/journal/T114-T118-every-row-was-a-bucket.md:49,161,166,235 -- same 13 -> 12 figure, table and prose.
10. specs/038-transfer-fidelity-gaps/tasks.md:644 -- the Phase-10-scoping table row "| MoAffixProcess | -13 | - | - | yes |". This one is already doubly stale independent of 6811894 (it predates T107's own 13->12 fix and was never updated to match); flagged for completeness but its staleness is pre-existing, not newly created by this commit.

Not listed above (checked and found clean): census-evidence.md, data-model.md, plan.md,
quickstart.md, research.md, two-mode-live-evidence.md,
contracts/feature-system-create-path.md, contracts/process-morphology-create-path.md,
contracts/unreferenced-feature-constraint-ruling.md, contracts/cmpossibility-list-rulings.md
(this last one is fulfilled by PIECE 2, not contradicted -- its item 4 specifies exactly the
per-owning-list measurement owning_lists implements, and item 5's refusal of a
class-keyed shortcut is respected, not violated), and contracts/t078-comparand-retirement.md
(its "correctly refused" phrase is a generic methodological aside, not about MoAffixProcess).
journal/T108-the-write-that-was-not-silent-after-all.md mentions rule 24ed706a three times
but only descriptively (as the rule that "never reaches its input members"), asserting no
present-tense "no fix" ruling -- not listed as needing amendment.

No draft amendments are proposed here per instructions -- this is inventory only.
