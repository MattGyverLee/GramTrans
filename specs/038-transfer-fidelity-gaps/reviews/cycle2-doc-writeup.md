# Cycle 2 -- doc writeup for the crash-residue spurt (T123)

**RULING: T123 STAYS UNCHECKED.** `LexReference` now measures 5 -> 5 MATCHED
on ngoreme (recovered by transfer, `accounted_for: []`), but two of the row's
own acceptance lines -- ngoreme's single missing `MoStemMsa` (-1) and
`LexEntryType`'s -1/-1 -- are untouched by this session's commits, and a row
checks only when every one of its acceptance lines is satisfied.

## What was done

1. `specs/038-transfer-fidelity-gaps/tasks.md` -- appended a dated clause to
   the T123 row: the `(Name, MappingType)` fallback + `ILexRefTypeFactory`
   create leg (worktree `db41744`), the live re-census result, the
   `LexDb.References` ruling amendment closing the adjacent gap T123's own
   text had named, and the explicit STAYS-UNCHECKED ruling with its reason.
2. New journal entry
   `specs/038-transfer-fidelity-gaps/journal/T123-the-type-list-that-canonical-guids-could-never-match.md`
   -- covers the missing create path, why GUID-only resolution can never
   succeed (FLEx-canonical default types vs. project-local source GUIDs,
   zero overlap on ngoreme), what landed and what it does not close, and a
   dedicated governance paragraph on the crash residue: the debug driver's
   `--tag` guard covered the census artifact and recensus wrapper but not the
   owner-probe path (frozen at import time), so a validation run silently
   overwrote a pinned comparand on `main`'s spec tree; fixed in `1edb442`.
3. `STATUS.md` -- new section inserted after the title line, covering the
   spurt's landed work, commit shas (`db41744`, `1edb442`, prior-cycle
   `7fbb9f9`), the T123 ruling, and next pickup T119 (ngoreme `MsFeatures` -1,
   `FsComplexValue.Value` -27).

## Not done

**No commit was made.** My toolset for this task has no shell/git access
(Read/Grep/Glob/Edit/Write only), so the requested "ONE commit to `main`"
step could not be executed. The three files above are edited and ready;
`/lex-archivist` (or a session with git access) needs to stage exactly
`specs/038-transfer-fidelity-gaps/tasks.md`,
`specs/038-transfer-fidelity-gaps/journal/T123-the-type-list-that-canonical-guids-could-never-match.md`,
and `STATUS.md`, and commit in the `docs(038): ...` style. Confirmed
`.specify/extensions/companion/commands/speckit.companion.resume.md` was not
touched, and nothing under `src/`/`tests/` was edited.
