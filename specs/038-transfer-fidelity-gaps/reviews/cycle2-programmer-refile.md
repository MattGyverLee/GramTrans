# Cycle 2 -- programmer refile of the t123b/t124 mix-up

**Task:** recover the crashed 2026-08-28 16:58 spurt's misfiled artifacts without losing data.

## What moved where

1. Created `specs/038-transfer-fidelity-gaps/probes/t123b/`.
2. Copied (not moved) the working-tree `probes/t124/owner-probe-GT038-T124-Ngoreme.json`
   (the run's actual output, sitting in the wrong slot) to
   `probes/t123b/owner-probe-GT038-T123b-Ngoreme.json`. Verified non-empty first
   (11877 bytes) before touching the original.
3. Ran `git checkout -- specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json`
   to restore the pinned T124 reading. `git diff --quiet -- <that path>` exited **0**
   -- HEAD's pinned reading is confirmed restored byte-for-byte.
4. As corroborating evidence for the README's byte-identity claim, also checked
   `t124-supplements-Ngoreme-FLEx.json` against HEAD: `git diff --quiet` exits **0**
   there too, i.e. the run left the source-side supplement completely untouched --
   consistent with a destination-only re-probe.
5. Wrote `probes/t123b/README.md` explaining the misfile, the driver's hardcoded
   `_PROBE_OUT` bug, the revert, and the byte-identical-supplements evidence.
6. Moved (plain filesystem `mv`, not git -- the file was untracked in the worktree)
   `GramTrans-038-transfer-fidelity-gaps/.../reviews/cycle1-verification-gate.md`
   to `GramTrans/.../reviews/cycle1-verification-gate.md`, then `rmdir`'d the now-empty
   `reviews/` directory in the worktree. Worktree `git status --short` afterward shows
   only its pre-existing unrelated dirty files (`categories.py`, two `_snapshots/*t123b*`
   json, one unit test) -- the reviews dir is gone cleanly, nothing else in the worktree
   was touched.
7. Committed on `main`, one commit, sha **`7fbb9f9`**: adds
   `probes/t123b/README.md`, `probes/t123b/owner-probe-GT038-T123b-Ngoreme.json`,
   `reviews/cycle1-qc-t123.md`, `reviews/cycle1-verification-gate.md`,
   `reviews/cycle1-verification-probe.md` (658 insertions, 5 files, all creates --
   the t124 restore produced no diff to commit, as expected).

## Constraint compliance

- `.specify/extensions/companion/commands/speckit.companion.resume.md` was never
  staged; `git status --short` post-commit shows it as the sole remaining
  modification (`M`), untouched.
- No FLEx/LCM code executed; `run038_t124_recensus.py` was never invoked.
- Feature worktree only had its empty `reviews/` dir removed; its three other
  pre-existing dirty files were left exactly as found.

## Surprises

None functionally -- both `git diff --quiet` checks (t124 probe and its
supplements) returned exit 0 on the first try, so the crash's blast radius was
exactly as scoped: one misdirected file, cleanly reversible. The only mild
surprise was that `cycle1-qc-t123.md` was *also* sitting untracked in main's
reviews/ already (not part of this incident) -- it got swept into the same
commit since it belonged on main anyway per CLAUDE.md and there was no reason
to leave it dirty separately.
