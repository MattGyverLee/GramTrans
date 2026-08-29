# T081 census-gate verification (artifact-only, cycle 1)

**Scope:** read-only, no live LCM. All findings derived from committed/untracked
JSON artifacts and code already on disk, using `python -m gramtrans.census_cli gate`.

## (1) Current gate, newest committed artifacts

Gated directly (raw files, `--phase 5`), `tests/integration/_snapshots/`:
`census-038-t126-ejagham.json`, `census-038-t126-ngoreme.json`,
`census-038-t126-mbugwe.json` (each is a real census artifact, `schema_version`
present; the `recensus-038-t126-*.json` files are *wrapper* docs whose
`census_artifact` field just names the sibling above -- gating them directly
fails with "no integer schema_version", exit 7).

Result, byte-for-byte reproducing the stored `recensus` wrapper's `phase_5`:
**6 / 10 / 7** P5 failures (ejagham/ngoreme/mbugwe), verdict
`UNEXPLAINED_SHORTFALL`, **exit 1** on all three. Matches T081's 4th re-gate
exactly; no drift since that prose was written.

## (2) Which kind-(ii) rulings are emitted?

**In the persisted `census-038-t126-*.json` files: none.** Checked every named
class (CmFile, CmFolder, PhCode, LexEntryType, MoAffixProcess, LexReference)
across all three pairs -- `accounted_for` is `[]` on every one. This is
**absence-from-a-pre-emitter artifact, not an emitter bug**: `census-038-t126-*`
were captured at 14:58-15:02, commit 009642e (the emitter) landed at 16:39, same
day. Confirmed by timestamp and by re-deriving in memory: applying
`census_cli.accounted_for_ruled_residue` + `accounted_for_drops` +
`census.unexplained_counts`/`build_totals` to fresh copies of the three t126
artifacts (exactly what `TestT081...` does in
`tests/integration/test_object_census.py`, no project opened) reproduces the
commit's claimed **6->5, 10->7, 7->5** P5 failures and **692->689, 1024->1019,
3005->829** unexplained-shortfall totals precisely. `pytest -k T081` (37 tests)
passes. So the emitter is correct and exercised only in-memory; it has never
been baked into a committed artifact file.

**One untracked artifact already proves it live**, though: `tests/integration/
_snapshots/census-038-t123b-ngoreme.json` (generated 16:58:49, i.e. *after*
009642e) carries real `accounted_for` lines -- `CmFile`/`CmFolder`:
`OUT_OF_SCOPE_CLASS`, `PhCode`: `STARTER_CONTENT`, each `unexplained_shortfall:
0`. Gating it directly reproduces its wrapper's stored `phase_5` exactly: 6
failures, exit 1 (down from 10 in t126, because this artifact also closes
LexReference for real, see below).

## (3) census-038-t123b-ngoreme.json: LexReference

`census-038-t123b-ngoreme.json`: `LexReference` `source_count: 5,
destination_count_total: 5, difference: 0, verdict_class: MATCHED` --
**recovered by real transfer, not by accounting** (`accounted_for: []`). This
is the T123 fix, separate from T081's accounting fix. `recensus-038-t123b-
ngoreme.json`'s `phase_5.failures` list confirms `LexReference` no longer
appears. (`census-038-t123b-ngoreme.json` predates this pair, at `difference:
0` already too -- both snapshots agree; no before/after regression in this
pair's own two files, but T126 vs T123b together show the 5->0->5 arc.)

## (4) Sized remaining work for P5 green

1. **Bookkeeping only (no live re-census needed in principle):** persist the
   T081 emitter's output into a committed artifact. Proven safe by (2)'s
   in-memory reproduction; only committed step missing is writing the
   regenerated JSON to `_snapshots/` and updating T081's/T038's/T048's prose.
   Closes CmFile/CmFolder/PhCode (ejagham 6->5, ngoreme 10->7, mbugwe 7->5).
2. **Requires a live re-census (already done once, untracked):** commit an
   ngoreme-equivalent full re-census for ejagham and mbugwe under the current
   code -- `census-038-t123b-ngoreme.json` shows the shape; no sibling exists
   for the other two pairs yet.
3. **Requires new transfer code (kind-(i), no ruling covers these):**
   `CmPossibility` (-308/-397/-332), `FsClosedValue` (-355/-465/-394),
   `FsFeatStruc` (-21/-92/-59), `PhFeatureConstraint` (-47/-32, ngoreme+mbugwe),
   `PhSequenceContext` (-5, ejagham only), `MoStemMsa` (-1, ngoreme only),
   `LexEntryType` (-12, deliberately left un-rosterable per T081 -- magnitude
   correction, not exemption). These are the floor: P5 cannot go green without
   either fixing the transfer or a human ruling for each.
4. **Human ruling, not code:** `MoAffixProcess` — token emitted
   (`SOURCE_REFERENT_ABSENT`), `unexplained_shortfall` already 0, but P5-
   admissibility of that token on a Phase-4-owned class is explicitly left to
   a human in the T081 commit; deciding it either closes or permanently
   excludes this row from P5 without further engineering.

Order: (1) commit the accounting bake-in for all three pairs (cheapest, known
to work) -> (2) commit missing live re-censuses for ejagham/mbugwe -> (4) get
the MoAffixProcess ruling -> (3) the six/seven real kind-(i) losses, which is
the actual remaining fidelity gap.
