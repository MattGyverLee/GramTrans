# Cycle 10 — t123c restore-bounded live re-census: T123 acceptance READ

**Verdict: T123 CANNOT be checked. T123(b) PASSES both pairs. T123(a) FAILS its
referent half — the object was restored, the sense was not rewired.**

User-authorized, restore-bounded. Two runs from the worktree:
`python debug/run038_t124_recensus.py ngoreme --tag t123c`, then `mbugwe`.
Each restores its own destination from `backups/Target 2026-07-06 0218.fwbackup`
before transferring; sources opened read-only. Census artifacts
`census-038-t123c-{ngoreme,mbugwe}.json`, recensus + `probes/t123c/` beside them.
Follow-up reads: ops `op-121511068-018`, `op-121546205-019`, both certified
read-only.

**Note on the command:** the handoff's `--tag t123c ngoreme` ordering does not
work — `main()` takes the pair from `argv[1]`, so `--tag` lands in that slot and
the run exits 2 at the usage branch. Correct form is **pair first**:
`ngoreme --tag t123c`.

## T123(b) — LexEntryType misclassification: PASSES, two-sided, both pairs

| | ngoreme | mbugwe |
|---|---|---|
| `LexEntryType` exact-class | 13 → **13** | 12 → **12** |
| `LexEntryInflType` exact-class | 3 → **3** | 4 → **4** |
| `LexEntryType` by GUID | same=13, CHANGED=0, absent=0, dest_only=0 | same=12, CHANGED=0, absent=0, dest_only=0 |
| `LexEntryInflType` by GUID | same=3, CHANGED=0, absent=0, dest_only=0 | same=4, CHANGED=0, absent=0, dest_only=0 |

vs T078: `LexEntryType SHORTFALL -> MATCHED` on both (net 1 → 13; net 0 → 12).
Confirmed directly: mbugwe's `Periphrastic Form`
(`99e0cab9-f284-45fb-84a5-4cb2516d0bf4`) now resolves with
**`ClassName=LexEntryType`**, not `LexEntryInflType`. The factory-by-source-class
fix does what it claimed.

## T123(a) — MoStemMsa: count half PASSES, referent half FAILS

**Passes:**
- `MoStemMsa 1954 -> 1954  diff 0  MATCHED  unexp -0/+0` (vs T078: net 1953 → 1954)
- `MoStemMsa.MsFeatures 782 -> 782 OK` — T119's identity restored from 782→781
- The named object `8617b725-efc1-4f6d-935c-c6c87081c7cb` is **present**; entry
  `omoona` owns 2 MSAs again, both carrying feature structures.

**Fails — the referring sense is still dangling:**

```
entry e2cd79ef-... 'omoona'
  sense 'child'        -> msa=13b8f64f-...
  sense 'small child'  -> msa=None      <-- source had 8617b725-...
```

Project-wide: destination **2233 senses, 2219 with `MorphoSyntaxAnalysisRA`, 14
null**. Source: 2233 senses, 2220 with RA, **13 null** (op `op-102758805-007`).
The delta is exactly **+1**, and it is `omoona`/`small child`.

**The acceptance line reads: zero senses with a null `MorphoSyntaxAnalysisRA`
whose source counterpart had one. Measured: one. T123(a) does not pass.**

This is precisely the failure the two-sided acceptance existed to catch. A
count-only check would have read `1954 = 1954` and closed the row. The fix
delivered half of what it claimed: the create is no longer lost, but the
`_create_via_wrapper_or_reuse` path does not rewire the referring sense.

## NEW — `Periphrastic Form` arrives with an EMPTY Name: a genuine loss

The three-way ambiguity is resolved, and it is the bad option.

```
object present, ClassName=LexEntryType
Name per WS   : en=None  swh=None  mgz-fonipa-x-emic=None
                mgz-fonipa-x-etic=None  etu=None  mgz=None
Abbreviation  : None in all six
BestAnalysisAlternative: '***'
```

- **Residue is excluded by construction** — this run restored the destination
  from backup first. Cycle 5's "unrestored Target" guess is dead.
- **Writing-system rendering is excluded by measurement** — the Name is empty in
  **all six** writing systems, not merely the default vernacular. This is *not*
  the same cause as ngoreme's `'*???'`, which had real values under `ngq`.

So a `LexEntryType` now arrives with correct GUID and correct class and **no
name at all**. Invisible to a class-count census by construction: the object is
present and counted. Needs its own row.

## REGRESSION on mbugwe, not to be lost

`MoMorphAdhocProhib   MATCHED -> SHORTFALL (net 2 -> 35)`, census difference
**-4**, carrying no accounting line. Listed under "vs T078: regressed=1". Cause
unknown; it was MATCHED on the T078 baseline and is not MATCHED now. It must be
attributed before T123 or T081 can close — a regression introduced while fixing
another row is exactly what this feature's gates exist to catch.

## Run verdicts (expected, not T123 failures)

Both pairs exit 1 `UNEXPLAINED_SHORTFALL` on P5 rows outside T123's scope —
ngoreme: `CmPossibility -397`, `FsClosedValue -463`, `FsFeatStruc -90`,
`PhFeatureConstraint -47`; mbugwe adds `MoMorphAdhocProhib -4` and
`PhSimpleContextNC -1`. `PhFeatureConstraint` -47/-34 is the population T120
ruled out of scope via `UNREFERENCED_IN_SOURCE`, which is landed on main but not
yet wired into the roster — that is T081's remaining work, deliberately not done.

## State

T123 stays **unchecked**. Phase 10 does not close. T085 stays gated.
The pre-run forensic copies are preserved in the session scratchpad
(`GT038 T124 Ngoreme.fwdata.pre-t123c`, sha `5d05ffc1…`, matching
`census-038-t123b-ngoreme.json`), so cycle 8's diagnostic artifact survives this
overwrite.
