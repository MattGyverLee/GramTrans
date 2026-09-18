# Cycle 8 — destination-side GUID diff: T123(a) IS DIAGNOSED, and the object is named

**One missing object, named, with its mechanism visible in the destination.**
This supersedes the branch-2/3/4 hypothesis search. No further source-side
guessing is needed.

Run by the main session. All five reads read-only: `write_enabled: false`,
`write_certification.is_certified_readonly: true`, `mutating_calls_detected: []`.
Ops `op-103945760-010`, `op-104009300-011`, `op-104035721-012`, `op-104104411-013`.

## Provenance — the destination is the exact state the census measured

Destination project `GT038 T124 Ngoreme`
(`C:\ProgramData\SIL\FieldWorks\Projects\GT038 T124 Ngoreme`), named as
`projects.destination` in both `census-038-t126-ngoreme.json` and
`census-038-t123b-ngoreme.json`.

Live `.fwdata` SHA-256 = `5d05ffc16f133c7c12427a4fbb646937c17f5a6282dfd332a8e65be0a0b076af`,
**byte-identical** to `census-038-t123b-ngoreme.json`'s recorded
`fwdata_sha256_before`/`_after`. It has moved on from t126's `3821fe3b…`, so
**t123b is the correct comparand** and this is not a stale or overwritten target.
Live counts reproduce the census exactly: 1950 `MoStemMsa`, 781 carrying
`MsFeaturesOA`.

## The diff

```
source MoStemMsa: 1951      destination MoStemMsa: 1950
IN SOURCE, NOT IN DESTINATION: 1
IN DESTINATION, NOT IN SOURCE: 0
```

Zero extras, so nothing was regenerated under a new GUID. The single missing
object:

| field | value |
|---|---|
| MSA GUID | `8617b725-efc1-4f6d-935c-c6c87081c7cb` |
| owning entry | `e2cd79ef-2ee5-4d56-ae54-9210060bcdae` |
| headword | `omoona` |
| `MsFeaturesOA` | **True** — matches the known fingerprint (782 -> 781) |
| `PartOfSpeechRA` | `c46c8242-8b3a-4021-9aed-2da8517438b5` — **set, not null** |

The POS being set independently re-confirms the POS-guard refutation (op 009).

## The mechanism, visible in both projects

**Source** `omoona` — two MSAs, identical in every syncable property, differing
only by GUID:

```
13b8f64f-…  MoStemMsa  feats=True  pos=c46c8242-…   <- sense 'child'
8617b725-…  MoStemMsa  feats=True  pos=c46c8242-…   <- sense 'small child'
senses: 2
```

**Destination** same entry:

```
owned MSAs: 1
  13b8f64f-…  MoStemMsa  feats=True  pos=a8e41fd3-…
senses: 2
  885182d0-…  'child'        -> 13b8f64f-…
  3081d6f8-…  'small child'  -> None        <-- DANGLING NULL
8617b725-… : NOT PRESENT anywhere in the project (KeyNotFoundException)
```

So: **the second MSA of an entry whose two MSAs share a natural key was never
created, and its sense's `MorphoSyntaxAnalysisRA` was left null.**

This is the worst of both outcomes and it is why the count moved: the object was
lost **and** the reference was nulled. Note it is specifically **not** a
dedup-and-reuse — the orphaned sense does not point at the surviving
`13b8f64f`; it points at nothing. A reuse would have left the count short but the
graph intact; this leaves both broken.

## This is T123's own defect family, and cycle 5 dismissed it on bad grounds

`journal/T119-T123-the-object-that-was-matched-by-name.md` established "a
destination object matched by NATURAL KEY rather than by GUID is invisible to
everything downstream". Cycle 5 considered this family and ruled it out because
"a natural-key match would leave the COUNT matched, and this row is short by one".

**That inference is wrong.** A natural-key match that skips the create *without
rewiring the referent* leaves the count SHORT and the reference NULL — exactly
what is on disk. The family was the right answer, discarded for a reason that
does not hold.

## Two incidental observations, recorded not diagnosed

- The destination MSA's POS GUID is `a8e41fd3-…` where the source's is
  `c46c8242-…`. POS is matched across projects by natural key rather than
  GUID-preserved, which is expected for shared category lists and is not part of
  this defect.
- The destination entry's headword renders `'*???'` where the source reads
  `'omoona'`. Possibly a writing-system/vernacular-form artifact of the reader,
  possibly a real fidelity gap. **Out of scope for T123(a); flagged for triage,
  not investigated.**

## Recommendation

**FIX, with a counted population of exactly 1 on this corpus.** The patch must do
both halves, or it will trade one defect for another:

1. do not skip the create when a second source MSA carries a distinct GUID,
   whatever its natural key; and
2. whatever the resolution, the referring sense's `MorphoSyntaxAnalysisRA` must
   end up non-null — a skip that leaves a dangling null is a worse outcome than
   either a duplicate or a reuse.

The patch site is the MSA create/match path in `_create_msa_for_closure` and its
key-matching helper **on the worktree** (`GramTrans-038-transfer-fidelity-gaps`,
`categories.py` ~16,022 lines, `_create_msa_for_closure` ~:9746) — **not** main's
copy, which is ~5,900 lines shorter and materially different.

**Acceptance is two-sided**: `MoStemMsa` 1951 = 1951 **and** zero senses with a
null `MorphoSyntaxAnalysisRA` whose source sense had one. Counting only the MSAs
would accept a fix that restores the object and leaves the sense dangling.
