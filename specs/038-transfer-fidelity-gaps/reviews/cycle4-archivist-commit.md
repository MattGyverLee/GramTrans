# Cycle 4 -- archivist commit for T119 ruling

**Gate:** `cycle4-verification-rulings.md` read in full -- all quantitative
claims PASS, both structural checks (T123 line untouched; T119/T120 rows
purely additive) PASS. No FAIL recorded. Commit proceeded.

**Commit:** `1e1a3c7`
"docs(038): T119 R1/R2 ruled -- both residuals closed, defect relocated not fixed"

**Files committed:**
- `specs/038-transfer-fidelity-gaps/tasks.md` (T119 checkbox flipped to [X],
  ruling text appended, additive-only per verification's structural check)
- `specs/038-transfer-fidelity-gaps/journal/T119-the-shortfall-was-never-created-to-reach.md`
  (new, 119 lines)
- `specs/038-transfer-fidelity-gaps/reviews/cycle4-doc-rulings.md` (new)
- `specs/038-transfer-fidelity-gaps/reviews/cycle4-verification-rulings.md` (new)

**Files skipped (deliberately, not in scope for this commit):**
- `.specify/extensions/companion/commands/speckit.companion.resume.md` --
  intentionally left dirty on main per task instruction; not staged.
- `specs/038-transfer-fidelity-gaps/reviews/cycle3-archivist-commit.md` --
  pre-existing untracked file from a prior cycle, not part of this
  briefing's file list; left untracked.

**Staging method:** explicit path-scoped `git add <path>` per file, no
`-A` / `.` used.

**Post-commit confirmation:** `git status --porcelain` shows
`.specify/extensions/companion/commands/speckit.companion.resume.md` still
`M` and unstaged, and `cycle3-archivist-commit.md` still `??` untracked --
both exactly as before the commit, unaffected.
