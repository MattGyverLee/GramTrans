# Cycle 8 -- Archivist Commit (spurt 3)

**Gate:** read cycle8-verification-postfix.md first. Verdict **GO** (3881->3894
reconciled +7/+4/+2; targeted 635/5/29 identical to cycle6 baseline, all five
failures pre-existing live-.fwdata drift; all four named code changes verified
in place by name). Proceeded.

## (1) Main tree -- COMMITTED AND PUSHED

`8972d9a` (main, fast-forward `7011b5b..8972d9a`): the two `specs/` contract
files (UNREFERENCED_IN_SOURCE token) plus 14 cycle5-8 review reports, staged
by name (no `-A`). `.specify/extensions/companion/commands/
speckit.companion.resume.md` deliberately left unstaged -- confirmed still
`M` and untracked-for-staging after the commit and again after the push.

## (2) Worktree -- NOT COMMITTED, NOT PUSHED (per task's own stop condition)

Discarded the two uncommitted mirror copies of the spec contract files
(`git checkout --`), then `git merge main --no-edit`. **Merge conflicted** in
two files unrelated to the two mirrored specs paths:
`tests/integration/harness/full_run.py` and `debug/run_fullcopy_sweep.py`.
`git log HEAD..main` on those paths shows they diverged back through six
feature-035 commits (`8235f4f`..`58cc970`) -- a real, non-trivial divergence,
not a mechanical rename/whitespace collision.

Per instructions on a non-trivial/conflicting merge: **aborted the merge**
(`git merge --abort`), then **restored the mirror** by copying the two spec
files' content straight from `main`'s just-committed blobs
(`git show main:<path> > <path>`) rather than reconstructing from memory --
same repo, shared object DB, so this is exact, not a guess. Confirmed the
restored diff is real content (the same UNREFERENCED_IN_SOURCE token
addition), not line-ending noise, by inspecting the diff body.

Worktree HEAD is unchanged at `5cf155c`, branch
`038-transfer-fidelity-gaps`. No code was committed there. No push attempted.
Targeted test re-run was **not** performed, since the merge that would
change what `_repo_root()` reads never completed.

## Status

- SHA (main): `8972d9a` -- pushed.
- SHA (worktree): `5cf155c` -- unchanged, uncommitted work restored to its
  original mirror-copy state, nothing pushed.
- `T123` untouched; `tasks.md` not edited.

## Follow-up needed

Someone with authority over `tests/integration/harness/full_run.py` and
`debug/run_fullcopy_sweep.py` needs to resolve the feature-035/feature-038
divergence on those two files before this branch can merge `main` cleanly.
