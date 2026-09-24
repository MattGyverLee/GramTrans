# Cycle 11 archivist commit

**Gate:** `cycle11-verification-postfix.md` verified GO (independently
re-read: all 4 wiring exit paths confirmed, instrument-gate fail-then-pass
independently reproduced, 3895/79/14 unit + 635/5/29 targeted, no new
failures).

## Worktree (038-transfer-fidelity-gaps)
**SHA f60b361** (parent 73552e4), pushed to
`origin/038-transfer-fidelity-gaps`. Staged by filename: only
`src/gramtrans/Lib/categories.py` and
`tests/unit/test_038_t123_msa_naturalkey_reuse.py`. Commit states: MSA
referent now rewired on all four exit paths (GUID-preserving create,
fresh wrapper create, reuse, cache-hit caller-side); prior fix delivered
only the create half, proven by t123c (dest 14 null MsaRA vs source 13,
delta +1 on 'omoona'/'small child'); root cause was a tautological
pinning test; repaired test proven fail-against-73552e4 /
pass-against-this-code via verification's independent swap-and-restore;
T123 remains unchecked pending live re-census (t123d). No `closes #N`.

**Confirmed still dirty/unstaged in worktree:** both contract mirrors
(`census-artifact.schema.json`, `fidelity-census.md`). Four
`tests/integration/_snapshots/*t123c*.json` probe-output files left
untracked (not code/tests, not staged).

## Main
**SHA 7f418f6** (parent 59385a5), pushed to `origin/main`. Staged:
`tasks.md` (T127 LexEntryType-empty-name row, T128 corrected
not-a-regression/mbugwe-source-drift row, both verbatim as specified,
placed after T125), `.crew-handoff.json`, and the four cycle10/cycle11
review reports. STATUS.md was not dirty, so left untouched.

**Confirmed still dirty/unstaged on main:**
`.specify/extensions/companion/commands/speckit.companion.resume.md`.
`specs/038-transfer-fidelity-gaps/probes/t123c/` left untracked (not
requested for staging).

**T123 confirmed `- [ ]`** (unchecked) in tasks.md after both commits.

No `git merge`, no merge-strategy options, no force-push, no branch
other than each tree's own tracking branch touched.
