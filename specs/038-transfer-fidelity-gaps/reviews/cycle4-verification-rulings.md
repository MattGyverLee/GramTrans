# Cycle 4 -- verification of T119/T120 doc rulings

**Scope:** read-only. No FLEx project opened, no live LCM touched -- this
task checks arithmetic/documentation claims against committed JSON
artifacts, not database state. Not a live-LCM verification task.

## Per-claim results

| Claim | Artifact | Value read | Status |
|---|---|---|---|
| `census-038-t126-ngoreme.json` MoStemMsa 1954/1953/-1, `accounted_for: []` | branch `038-transfer-fidelity-gaps` (see note) | source 1954, destination_count_total 1953, difference -1, accounted_for [] | PASS |
| `census-038-t126-ngoreme.json` LexEntry 2017=2017 MATCHED | same | 2017/2017, verdict MATCHED | PASS |
| `owner-probe-t126-Ngoreme` FsComplexValue.Value=798 | `probes/t126/owner-probe-GT038-T126-Ngoreme.json` | 798 | PASS |
| `owner-probe-t126-Ngoreme` MoStemMsa.MsFeatures=781 | same | 781 | PASS |
| `owner-probe-t126-Ngoreme` MoInflAffMsa.InflFeats=38 | same | 38 | PASS |
| `owner-probe-t126-Ngoreme` PartOfSpeech.ReferenceForms=0 | same | absent from owner list; owner sum (798+781+41+38+21=1679) equals class subtree_total exactly, so 0 is the only value consistent | PASS |
| `owner-probe-t124-Ngoreme` FsComplexValue.Value=20, no MsFeatures key | `probes/t124/owner-probe-GT038-T124-Ngoreme.json` | 20; owners dict has no `MoStemMsa.MsFeatures` key | PASS |
| source `owner-probe-Ngoreme-FLEx` 825/782/44/38 | `probes/owner-probe-Ngoreme-FLEx.json` | FsComplexValue.Value 825, MoStemMsa.MsFeatures 782, PartOfSpeech.ReferenceForms 44, MoInflAffMsa.InflFeats 38 | PASS |
| `20 + 778 = 798` | arithmetic | 798 | PASS |
| `825 - 798 = 27` | arithmetic | 27 | PASS |
| `(none): 1172` identical source/destination in MoStemMsa.feature_structure | source probe + t126 probe | source `{"(none)":1172,"MsFeaturesOA":782}`, destination `{"(none)":1172,"MsFeaturesOA":781}` -- (none) bucket is 1172 on both sides | PASS |
| T120 `PhFeatureConstraint` 70->23 ngoreme, 89->57 mbugwe | `census-038-t126-ngoreme.json`, `-mbugwe.json` | ngoreme 70/23/-47; mbugwe 89/57/-32 | PASS |

## Structural checks

1. T123 (tasks.md line 711) still carries the open "single missing `MoStemMsa`
   under `LexEntry.MorphoSyntaxAnalyses`" acceptance line -- PASS (line 711
   text byte-identical before/after this change; confirmed via full-file
   line diff, `old[710]==new[710]` True).
2. Rows 707/708 (T119, T120) are purely additive -- PASS. Programmatic check:
   stripping the `- [ ]`/`- [X]` prefix, the OLD row text is an exact string
   prefix of the NEW row text for both rows (T119 +3288 chars appended,
   T120 +3219 chars appended, zero characters altered or removed). All
   other lines in the file (0-705, 708 (=old709) onward) are byte-identical.

## One finding not in the brief

The four cited `tests/integration/_snapshots/census-038-t126-*.json` files
and the `probes/t126/*.json` files quoted with paths under `specs/...` do
**not** exist on `main` (current checkout, commit `6bad425`) -- they were
committed only on the sibling worktree branch `038-transfer-fidelity-gaps`
(commit `efa57b5`). This matches the repo's stated split (spec docs to
`main`, work product to the worktree), so it is not a defect, but a plain
`git show HEAD:<path>` or `find` on `main` alone cannot see them -- I read
them via `git show 038-transfer-fidelity-gaps:<path>`. Flagging so the next
verifier doesn't waste time concluding the artifacts are missing.

## Result

**All quantitative claims: PASS.** No arithmetic, no cited count, and no
structural (append-only / T123-line-preserved) claim in the newly appended
T119/T120 text was found to be wrong.
