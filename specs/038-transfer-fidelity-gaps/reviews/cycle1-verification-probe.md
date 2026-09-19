# Provenance review -- t124 owner-probe (crash remnant)

**File:** `specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json`
**Verdict: legitimate measurement, wrong path. Disposition: (b) restore + refile.**

## (1) Provenance

The modified content is a genuine POST-FIX re-probe of the SAME live throwaway
`GT038 T124 Ngoreme` -- not a different project, not the source `Ngoreme FLEx`.
Every changed number except `LexReference` exactly matches the already-committed
`probes/t126/owner-probe-GT038-T126-Ngoreme.json` (`efa57b5`): `FsFeatStruc`
1679, `FsClosedValue` 2075, `PhSegRuleRHS` 21, `PhSequenceContext` 13,
`PhSimpleContextNC` 47, `MoStemMsa.MsFeaturesOA` 781. `LexReference` 0->5 is
the ONE figure T126 did not yet have: commit `6fa753a` (14:57) and `2837fab`
(16:28) both say explicitly "LexReference stays 5 -> 0" / "latest committed
probes still read LexReference 0." Between 16:28 and the file's 16:58 mtime,
the worktree gained an **uncommitted** `src/gramtrans/Lib/categories.py` diff
(+364/-18) implementing `_lex_ref_type_natural_key`, `ILexRefTypeFactory_ref`,
`_create_target_lex_ref_type` -- the exact `(Name, MappingType)` fallback +
create-leg `2837fab` said was still missing -- plus an untracked unit test
`tests/unit/test_038_t123_lexreftype_key_and_create.py`. The untracked
`tests/integration/_snapshots/{census,recensus}-038-t123b-ngoreme.json`
(mtime 16:58:50/54, seconds after the probe file) corroborate directly:
`LexReference` is `MATCHED` 5/5, and `recensus-038-t123b-ngoreme.json`'s own
`destination_probe` field names this exact clobbered path. This is a real,
live-verified improvement, measured against the live LCM, not a stray edit.

## (2) Driver and its guard gap

Driver: `debug/run038_t124_recensus.py` (in-repo, `debug/`). Commit `0610d3e`
added `--tag` so a re-run "cannot overwrite T124's comparand" -- but the guard
is incomplete. `RUN_TAG` only reparametrizes the census/report paths
(`census-038-%s-%s.json`, `_run_reports/038-%s-%s-report.json`, lines 442/444).
`_PROBE_OUT` (line 106) and `_probe_path()` (line 400-403) are hardcoded to
`probes/t124/` and to the live project's own name regardless of `--tag`, and
`_run_pair` (line 500-505) reads-then-rewrites `dest_probe_path`
UNCONDITIONALLY on every run via `_probe_project`'s re-execution of the Wave-1
probe. So `probes/t126/owner-probe-GT038-T126-*.json` exists only because
someone manually copied the driver's output after the fact; the driver itself
always overwrites `probes/t124/owner-probe-GT038-T124-*.json` in place. This
is the exact mechanism of the crash-remnant clobber, and it will recur on the
next `--tag` run unless fixed.

## (3) Load-bearing status

`GT038 T124 Ngoreme` is **not** `GT038 Ngoreme After` -- T124's tasks.md entry
is explicit that it re-pinned into three FRESH throwaways restored from
`Target 2026-07-06 0218.fwbackup`, distinct from `GT038 Ngoreme After` (still
on its T078 pin, its own artifact `probes/owner-probe-GT038-Ngoreme-After.json`
at probes/ root). T081's "most load-bearing comparand" claim is about that
different project/file, not this one. This file is still a pin in its own
right: T119's and T125's tasks.md entries quote figures straight off it
("MoStemMsa.MsFeatures 0 of 1,003", "0 of 5 LexReference surviving ... at an
absent LexRefType"), and `recensus-038-t126-ngoreme.json`'s `net_t124` columns
treat it as a frozen middle layer between T078 and now. Overwriting it in
place would silently falsify those already-committed citations.

## Recommendation: (b)

```
git -C D:/Github/_Projects/_LEX/GramTrans checkout -- \
  specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json

mkdir -p D:/Github/_Projects/_LEX/GramTrans/specs/038-transfer-fidelity-gaps/probes/t123b
# (save the pre-restore working-tree content first, then:)
cp <saved-copy> \
  D:/Github/_Projects/_LEX/GramTrans/specs/038-transfer-fidelity-gaps/probes/t123b/owner-probe-GT038-T123b-Ngoreme.json
git -C D:/Github/_Projects/_LEX/GramTrans add \
  specs/038-transfer-fidelity-gaps/probes/t123b/owner-probe-GT038-T123b-Ngoreme.json
```

Also: commit the categories.py LexRefType fix + its new unit test once
re-verified, and patch `debug/run038_t124_recensus.py` so `_PROBE_OUT`/
`_probe_path` are parameterized by `RUN_TAG` (mirroring lines 442/444) --
otherwise the next `--tag` recensus reproduces this exact clobber.
