# T119 residuals -- R1 (MsFeatures -1) and R2 (FsComplexValue.Value -27), ngoreme

## R1: MoStemMsa.MsFeatures short 1 of 782

**Not a wiring-pass defect.** `MoStemMsa` itself is a class-level `SHORTFALL` in
the census (`census-038-t126-ngoreme.json`, class `MoStemMsa`:
`source_count=1954`, `destination_count_total=1953`, `difference=-1`,
`accounted_for=[]`) -- the object never arrived, full stop. Its owner
breakdown pins the drop to `LexEntry.MorphoSyntaxAnalyses` (source 1951 ->
destination 1950; the other three MoStemMsa owner buckets --
`MoEndoCompound.OverridingMsa`, `MoBinaryCompoundRule.{Left,Right}Msa` -- are
unchanged at 1/1/1). Yet `LexEntry` itself is 100% `MATCHED` (2017=2017,
`census` same file). So the owning entry IS present; one of its stem MSAs
simply was never created.

The destination's `feature_structure` bucket confirms the pass did not
hollow anything: `(none): 1172` is IDENTICAL source and destination (only
`MsFeaturesOA` moved 782->781). If `_wire_owner_feat_strucs`'s all-or-nothing
deferral had tripped for any of the 781 present owners, that owner would show
up in `(none)` instead, not disappear from the class count. It didn't --
every stem MSA that exists in the destination got its `MsFeaturesOA` filled,
100%. The loss is upstream of `_wire_owner_feat_strucs`, in whatever creates
`MoStemMsa` objects for stems (out of this task's owning-field scope, and not
one of the pre-named rulings either -- a genuinely new, unattributed,
single-object gap).

**Mechanism excluded:** owner-absent-because-entry-absent (T074 scoping) --
entry is present. **Mechanism excluded:** binding-key collision -- the key is
`"<owner guid>|<attr>"` and a collision would show as a wrong VALUE, not a
vanished owner. **Mechanism excluded:** empty source `FeatureSpecs` -- the
source count itself (782) already reflects only non-empty structures.
**Supported:** a MoStemMsa create-time loss, one object, unrelated to feature
enrichment.

## R2: FsComplexValue.Value short 27 of 825

Arithmetic across the two owner-probes fully accounts for it, no guessing.

At T124 (before the STEMS fix), `owner-probe-GT038-T124-Ngoreme.json` shows
`FsFeatStruc` owners `{InflFeats: 38, FsComplexValue.Value: 20}` with **no**
`MoStemMsa.MsFeatures` key at all (0). `MoInflAffMsa.InflFeats` was already
complete then (38/38) and stayed so through T126 with no regression -- so
**all 20 nested complex values reachable from InflFeats arrived, both then
and now, zero loss.**

At T126, `FsComplexValue.Value` reads 798. `798 - 20 (InflFeats, unchanged) =
778`, and the only other code path touched between T124 and T126 is the
`MoStemMsa` fix -- so those 778 are exactly the nested complex values
reachable from the 781 *present* `MoStemMsa.MsFeatures` structures, and since
`20 + 778 = 798` exactly (no slack), **zero complex values were lost from any
MoStemMsa or InflFeats structure that itself transferred.**

Source total is 825. `825 - 798 = 27`, and by the above, none of it can come
from the 781 present MoStemMsa owners or the 38 InflFeats owners -- both are
proven loss-free. That leaves exactly two source buckets able to hold the 27:
(a) whatever complex values were nested under the ONE MoStemMsa that never
arrived (R1's object -- mechanical, not a separate defect), and (b) whatever
complex values were nested under the 44 `PartOfSpeech.ReferenceForms`
structures, which are a **total** loss (44->0, created as empty shells,
already ruled to T045's depth-limit create path). `X + R = 27` where `X` =
bucket (a), `R` = bucket (b); the committed counts don't carry a per-object
breakdown that splits X from R further, so I cannot attribute past that, but
**every other possible source is excluded by the identity above**. This is a
partial, not a guessed, attribution: 0 of 27 unaccounted-for-in-bucket,
27 of 27 pinned to {R1's single object, T045's ReferenceForms}.

## Verification cost per residual

- **R1:** closable as a RULING from committed artifacts (census + owner-probe
  deltas already prove entry-present/owner-absent and zero hollowing among
  survivors). Pinning WHY that one stem MSA's create failed (to fix it) would
  need either a live read-only probe of the source/target pair (not a write)
  or a live re-run; neither is available in this session (no FLExToolsMCP
  tool bound) and neither is required to close T119's line, since the gap is
  outside `_wire_owner_feat_strucs`'s contract (it cannot enrich an owner
  that does not exist).
- **R2:** closable as a RULING from committed artifacts alone -- the T124/T126
  probe delta arithmetic above is exact and needs no new measurement. Splitting
  X from R (bucket a vs b) would need a live READ-ONLY probe (not a write) of
  source Ngoreme's ReferenceForms/MoStemMsa complex-value nesting; that is a
  nice-to-have bookkeeping detail, not a blocker, and not owed to T119.

## Recommended disposition

**RULE both**, no code change to `_wire_owner_feat_strucs`,
`_resolve_feat_struc_binding`, or `_apply_feat_struc_rows`. T119's own
acceptance (per-pair, per-owning-field enrichment of owners that exist) is
met at 781/781 and 798/798-of-what's-reachable; the residue is a single
upstream MoStemMsa creation gap (new, unattributed, out of T119's scope) plus
its mechanical FsComplexValue consequence, and the already-ruled T045
ReferenceForms empty-shell defect. Neither residual requires a live write
to close at this diagnostic level -- **BLOCKED-NEEDS-LIVE-WRITE does not
apply to either.** If the team later wants the exact X/R split or the missing
MSA's identity, that is a live READ-ONLY probe (human-authorised but not a
destructive boundary), separate from this spurt.

## No fix sketch

Not warranted -- see disposition. If a future session wants to chase the
single missing MoStemMsa, the risk to name up front is the same one T119
already carries: any change near stem-MSA creation must not regress
`MoInflAffMsa.InflFeats` (86/38/78, the reference implementation) or the
781/781 `MsFeaturesOA` parity this session measured.

## Evidence cited

- `tests/integration/_snapshots/census-038-t126-ngoreme.json` -- `MoStemMsa`,
  `FsFeatStruc`, `LexEntry`, `LexSense`, `MoStemAllomorph` class rows.
- `specs/038-transfer-fidelity-gaps/probes/owner-probe-Ngoreme-FLEx.json` --
  source owner breakdown (825/782/44/41/41/38 = 1771).
- `specs/038-transfer-fidelity-gaps/probes/t126/owner-probe-GT038-T126-Ngoreme.json`
  -- destination owner breakdown (798/781/0/41/38/21).
- `specs/038-transfer-fidelity-gaps/probes/t124/owner-probe-GT038-T124-Ngoreme.json`
  -- pre-STEMS-fix breakdown (20/0/41/38/21), the pivot the arithmetic turns on.
- `specs/038-transfer-fidelity-gaps/probes/t126/owner-probe-GT038-T126-{Ejagham,Mbugwe}.json`
  -- comparands showing exact MoStemMsa/MsFeatures parity where no loss occurs.
- `src/gramtrans/Lib/categories.py:10352-10482` (`_wire_owner_feat_strucs`),
  `:10720-10785` (`_resolve_feat_struc_binding`), `:10800-10824`
  (`_apply_feat_struc_rows`) -- all-or-nothing deferral and binding-key shape.
- `src/gramtrans/Lib/preview.py:2189-2299` (`_read_feat_struc_live`),
  `:2475-2598` (`_populate_msa_feat_struc_bindings`) -- producer scope and the
  explicit "NOT covered here" list (InflFeats, ReferenceForms, CmAnnotation).
- `specs/038-transfer-fidelity-gaps/tasks.md` line 707 (T119 full history).
- `specs/038-transfer-fidelity-gaps/journal/T119-T123-the-object-that-was-matched-by-name.md`
  (natural-key-matched-owner ruling, cited but not re-litigated).
