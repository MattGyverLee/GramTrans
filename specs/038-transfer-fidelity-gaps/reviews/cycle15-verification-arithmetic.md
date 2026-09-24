# Verification arithmetic -- cycle 15

Offline re-derivation; no live LCM read.

## Claim 1 -- CONFIRMED, mbugwe hole real

`t119_per_owning_field` sums vs. the `FsFeatStruc` row:

| pair | sum(src) | sum(dest) | row source_count | row dest_total |
|---|---|---|---|---|
| ejagham | 269 | 248 | 269 | 248 |
| ngoreme | 1771 | 1681 | 1771 | 1681 |
| mbugwe | **429** | 782 | **1197** | 782 |

Exact match; mbugwe hole = 1197-429 = 768, confirmed.

**Cause: genuinely stale, not truncated/filtered.** `debug/run038_t124_recensus.py`
builds the per-field **source** side from a fixed, never-regenerated Wave-1
file (`owner-probe-Mbugwe-LizzieHC-practice.json`, `run_wave1=False` every
T124/T126/T131/T133 run); **destination** is freshly re-probed each run. The
same module's T129 docstring records Mbugwe's source `.fwdata` changing
digest between t126 and t123c, while the census's live `source_count`
(1197) reflects the CURRENT source. Ejagham never moved and ngoreme's
FsFeatStruc count held steady despite its own digest move, so their sums
still land exactly; mbugwe's did not -- it gained 768 FsFeatStruc objects
after the Wave-1 probe was captured and never rerun. Stale cached source vs.
a live comparison, not a summation bug.

## Claim 2 -- confirmed, with a correction: code is fixed, artifacts are not

`census.evaluate_phase(artifact, 5)` at HEAD (08b5f15), run against the
committed `census-038-t131-ngoreme.json` / `census-038-t133-mbugwe.json`,
**still fails** P5 for `PhFeatureConstraint` (diff -47/-34, `accounted_for:
[]`, `unexplained_shortfall: 47`/`34`). Offline recompute against the stored
artifacts does not flip the verdict.

But `census_cli.accounted_for_ruled_residue("PhFeatureConstraint", diff, ...)`
-- the pure function `565b9b5` added -- run against those same differences
**does** produce a fully-covering `UNREFERENCED_IN_SOURCE` line (47 of
max_claim 47; 34, under the cap) for both. `git log` confirms the stored
files predate the fix: `c81262c` (ngoreme) and `bafe5dc` (mbugwe) are both
ancestors of `565b9b5`, not descendants. So the failure is artifact
staleness, not a live defect -- a fresh re-census would pass it.

## Claim 3 -- live P5 failure table (HEAD 08b5f15, current artifacts)

| pair | class | diff | unexplained | accounted_for |
|---|---|---|---|---|
| ejagham | CmPossibility | -308 | 308 | none |
| ejagham | FsClosedValue | -355 | 355 | none |
| ejagham | FsFeatStruc | -21 | 21 | none |
| ejagham | PhSequenceContext | -5 | 5 | none |
| ejagham | MoAffixProcess | -1 | 0 | SOURCE_REFERENT_ABSENT (not admissible) |
| ngoreme | CmPossibility | -397 | 397 | none |
| ngoreme | FsClosedValue | -463 | 463 | none |
| ngoreme | FsFeatStruc | -90 | 90 | none |
| ngoreme | PhFeatureConstraint | -47 | 47 | none (**stale, see Claim 2**) |
| mbugwe | CmPossibility | -335 | 335 | none |
| mbugwe | FsClosedValue | -1002 | 1002 | none |
| mbugwe | FsFeatStruc | -415 | 415 | none |
| mbugwe | PhFeatureConstraint | -34 | 34 | none (**stale, see Claim 2**) |
| mbugwe | PhSimpleContextNC | -1 | 1 | none |

HEAD's code changes the verdict vs. the stored supplements only for
`PhFeatureConstraint` (both pairs, now fully covered pending regeneration).
Every other row is a live, unaccounted failure today.

## Claim 4 -- genuine regression, source stable throughout

| tag | source | dest | verdict |
|---|---|---|---|
| t126 | 78 | 78 | OK |
| t131 | 78 | 55 | SHORTFALL |
| t132 | 78 | 55 | SHORTFALL |
| t133 | 78 | 55 | SHORTFALL |

Source identical (78) across all four runs rules out (b) source drift for
this field. Destination reproducibly 55 across three independent
fresh-transfer runs rules out (c) a one-off artifact. This is **(a) a
genuine regression**, introduced between the commit behind t126 (`efa57b5`)
and t131 (`c81262c`). Only commits in that range touching MSA
identity/wiring: `b7c9296`/`f60b361` ("wire MSAs for subsenses"/"rewire MSA
referent on all four exit paths") and `73552e4` ("MSA natural-key dangling
referent") -- a plausible cause (natural-key MSA dedup collapsing source
`MoInflAffMsa` into fewer destination objects), not confirmed here. **Live
read that would decide it:** bisect the recensus at `efa57b5`, `b7c9296`,
`f60b361`, `73552e4` against mbugwe, or diff GUIDs of the 78 source
`MoInflAffMsa` vs. the 55 that arrived to find the missing 23.
