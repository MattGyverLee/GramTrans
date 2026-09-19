# T123 -- the type list that canonical GUIDs could never match

**Date:** 2026-08-28
**Task:** T123 (`LexReference`)
**Worktree commits:** `db41744` (LexRefType key/create), `1edb442` (tag-leak fix)
**Main commits:** `7fbb9f9` (crash-residue refile, prior cycle)
**Test state:** `pytest tests/unit -q` -- 3877 passed, 79 skipped, 14 xfailed, 0
failed; `test_038_t123_lexreftype_key_and_create.py` 19/19.

---

## 0. The one-line answer

`LexReference` reads **5 -> 5, MATCHED, `accounted_for: []`** on ngoreme --
recovered by the transfer, not by an accounting line. T123 still stays
unchecked: two of its own acceptance lines (`MoStemMsa`'s ngoreme -1,
`LexEntryType`'s -1/-1) are untouched by this session's work.

## 1. The misconception: "GUID-only resolution will find the type eventually"

Every earlier reading of this defect asked the wrong next question. T124
measured that all 5 relations died at `_resolve_target_lex_ref_type` with
reason "lexical relation type not found in target" and asked whether the
per-`MappingType` structural rulings (TREE / COLLECTION / SEQUENCE) would hold
once the type was found. They were never going to be reached, because the
premise under them was false: `LexRefType` has **no create path anywhere** in
this codebase (`grep ILexRefTypeFactory` over `src/` and `tests/` returns
zero hits), so resolution was GUID-only by construction, and GUID-only
resolution cannot succeed against this class on any real pair.

The reason is structural, not a corpus accident. `LexDb.References` ships
with FLEx-canonical default relation types -- every fresh project gets the
same fixed GUIDs for `Synonyms`, `Antonyms`, `Calendar`, and the rest,
because a fresh `.fwdata` is built from the same template every time. A
source project's relation types, by contrast, carry whatever GUIDs they were
assigned when that project's history first created them. Measured on
ngoreme: 7 relation types, identical to the destination's 7 by `Name` and by
`MappingType`, **zero GUID overlap**. So the destination's `LexRefType` row
reads 7 -> 7 count-MATCHED, and none of the 7 matched objects is the source's
-- the census's own MATCHED verdict was true and useless at the same time,
which is why nothing upstream of T123 ever flagged it.

The fix is a `(Name, MappingType)` fallback used as a resolution key, plus a
create leg for the case a source type has no destination counterpart by that
key at all. Neither half is optional on its own: a fallback with no create
leg still drops a type the destination genuinely lacks; a create leg with no
fallback key would create a duplicate `Synonyms` beside the canonical one
every single run, since GUID-only resolution would keep reporting "not
found" for a type that plainly already exists under a different identity.

## 2. What landed, and what it does not close

`db41744` adds the natural key (`_lex_ref_type_natural_key`, `(Name,
MappingType)`, exact and case-sensitive per this codebase's established key
discipline) and the create leg (`_create_target_lex_ref_type`,
`ILexRefTypeFactory`), threaded through `_resolve_target_lex_ref_type`'s
four-leg resolution order and `_evaluate_lexical_relation`'s reporting. QC's
cycle-1 review (`reviews/cycle1-qc-t123.md`) found the diff complete and not
cut off, all four helpers consumed, both call sites consistent, and flagged
two P2-severity items (an unreferenced key-fields tuple, an asymmetric
dedup granularity) as polish rather than blockers -- neither touches the
correctness of the fix.

The live re-census in `census-038-t123b-ngoreme.json` is the artifact that
matters: `LexReference` source_count 5, destination_count_total 5, difference
0, MATCHED, `accounted_for: []`. Empty `accounted_for` is the tell that
distinguishes this from every other closed row on this feature so far --
`CmFile`/`CmFolder`'s OUT_OF_SCOPE_CLASS lines and `PhCode`'s
STARTER_CONTENT line are accounting closing a gap the transfer does not; this
is the transfer itself doing the work.

It does not close T123. The row's own acceptance carries five clauses; two
were addressed in earlier sessions (the nesting fix, `CmFile`/`CmFolder`,
`MoAffixProcess`'s refusal), `LexReference` closes here, and two remain
exactly where T124 measured them: ngoreme's single missing `MoStemMsa` under
`LexEntry.MorphoSyntaxAnalyses`, and `LexEntryType`'s -1/-1 (two named
absent objects, `Perfective` on ngoreme and `Periphrastic Form` on mbugwe,
confirmed by GUID but not fixed). A task with five acceptance lines does not
check because the largest one closed.

## 3. The crash-residue lesson -- a governance finding, not a typo

The session this fix was validated in crashed after the validating run
completed. Every artifact the run produced was correct; what never happened
was the commit, the journal entry, and this tasks.md write-up -- three
housekeeping steps, none of them the transfer.

The residue it left is worth its own paragraph because it is not a one-off
mistake, it is a gap in a guard that already exists for exactly this
failure mode. `debug/run038_t124_recensus.py` (a debug driver living on the
`038-transfer-fidelity-gaps` feature branch/worktree) writes three kinds of
output for a tagged run: the census artifact, the recensus wrapper, and the
Wave-1-style owner probe. The `--tag` mechanism exists so a validation run
(`--tag t123b`) cannot collide with the pinned comparand a different task
depends on (`--tag t124`, i.e. `probes/t124/owner-probe-GT038-T124-*.json`,
which T124's own obligations treat as load-bearing history). Before this
session's `1edb442` fix, the tag guard covered the census artifact and the
recensus wrapper -- two of the three outputs -- and the owner-probe path was
still built from a module-level constant frozen at import time, before
`--tag` had been parsed. A `--tag t123b` run therefore wrote its probe
straight into `probes/t124/`, overwriting the pinned ngoreme comparand, and
the crash left that overwrite sitting in a **branch worktree's** working
tree while the surviving process state pointed at **main's** pinned spec
tree -- the file that showed up modified was
`specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json`
on `main`, not merely in the worktree that ran the driver.

Two things follow from stating it this way rather than as "a stray file got
overwritten". First, the guard's own author had already anticipated exactly
this shape of leak and fixed it once for a sibling artifact (the driver
carries a `# TAGGED TOO` comment recording that prior fix) -- the omission
here is the same class of gap recurring, not a new one, which is why
`1edb442` is a fix commit and not a one-line patch buried in something else.
Second, a debug driver invoked from a feature worktree does not confine its
side effects to that worktree: `specs/` is pinned on `main` per this
project's workflow, and any tool that writes into it needs the SAME
completeness discipline a production write-path gets, not the lighter
standard a "debug" label suggests. `1edb442` closes the gap by resolving the
probe output directory at call time from `RUN_TAG` rather than at import
time, and a new test (`test_038_t124_probe_tag_isolation.py`, 4 tests)
pins both the default-tag path (unchanged) and the divergence for a
non-default tag, for both derived filenames. The recovery itself -- restoring
`probes/t124/owner-probe-GT038-T124-Ngoreme.json` to HEAD and refiling the
run's actual output to `probes/t123b/` -- was handled by a sibling agent this
cycle (`7fbb9f9`) and is not repeated here; it is recorded because the
governance question it raises (a debug tool's write-scope guard needs to be
as complete as the surface it protects) outlives the one file it clobbered.
