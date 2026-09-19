# Cycle 2 -- landing the crashed T123 diff, plus the tag-leak fix

Worktree `GramTrans-038-transfer-fidelity-gaps` @ 009642e -> two new commits.

## Commit 1 -- T123 LexRefType key/create

`db41744` -- `feat(038): T123 -- LexRefType natural key + create leg for
lexical relations`. Staged exactly the 4 files QC reviewed
(`src/gramtrans/Lib/categories.py`, the new unit test, both t123b snapshots).
Re-ran both gates before committing, both green, matching QC's cycle-1
numbers exactly:

- `pytest tests/unit/test_038_t123_lexreftype_key_and_create.py -q` -- 19 passed
- `pytest tests/unit -q` -- 3877 passed, 79 skipped, 14 xfailed, 0 failed

## Commit 2 -- the tag leak

`1edb442` -- `fix(038): tag the T124 recensus driver's probe output
directory too`. `debug/run038_t124_recensus.py` built its probe output
paths from `_PROBE_OUT`, a module-level constant frozen at import time
(`_MAIN / "probes" / "t124"`), while `--tag`/`--tag=` parsing mutates the
`RUN_TAG` global later, inside `main()`. Both the Wave 1 owner-probe
artifact (`_probe_path`) and the source-side
`t124-supplements-<source>.json` derived from that frozen constant, so any
tagged run still wrote into `probes/t124/` -- the exact directory the tag
exists to protect, and the same shape of leak the driver's own
`# TAGGED TOO` comment already records for a sibling artifact
(`recensus-038-<tag>-<pair>.json`), fixed once before and missed here.

Fix: `_PROBE_OUT` is now `_probe_out_dir()`, a function reading `RUN_TAG` at
call time; default tag reproduces the original path unchanged. Added
`tests/unit/test_038_t124_probe_tag_isolation.py` (4 tests, offline, no FLEx
import): default-tag stability, non-default-tag directory divergence, and
divergence for both derived filenames (owner-probe, supplements). Full
`tests/unit` re-run after this change: 3881 passed (3877 + 4 new), 79
skipped, 14 xfailed -- still green. No live driver run performed.

**Would this have prevented the observed residue?** Yes, most likely. The
residue was `specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json`
showing modified in `main`'s working tree (already restored by a sibling
agent before this cycle started). The T123 validation snapshots landed in
commit 1 are tagged `t123b` (`census-038-t123b-ngoreme.json`,
`recensus-038-t123b-ngoreme.json`), which only exist if the recensus driver
was invoked with `--tag t123b` while validating the T123 fix. Under the
pre-fix code, that `--tag t123b` run would correctly tag the census/report/
recensus artifacts but would still funnel its owner-probe write into the
hardcoded `probes/t124/`, silently overwriting the pinned Ngoreme
comparand -- matching the file and symptom observed exactly. Under the
fixed code that same `--tag t123b` invocation resolves `_probe_out_dir()`
to `probes/t123b/`, leaving `probes/t124/` untouched.

No live FLEx/LCM run performed. No merge to `main`. Two separate commits as
required.
