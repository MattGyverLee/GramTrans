# Issue #132 — StemNameRA never-silent — lex-lead cycle 1 (final)

## Issue selection (lex-lead)

- **Open P0/P1 without an open PR:** none (#22 is conflict-mode epic-scale).
- **Chosen:** **#132** (P2 never-silent audit; closed umbrella) — **`StemNameRA` assignment** on allomorph hung-data reproduce (`owned._reproduce_stem_name_ra`) and #134 late repair (`_repair_one_allomorph`). Open PR **#279** covers `PhoneEnvRC.Add` on the same repair helper only; this slice is distinct.

## Diagnosis

When a target stem name resolved in the owning POS's `StemNamesOC`, both paths assigned `StemNameRA` with a bare setattr. Create-time reproduce swallowed `AttributeError`/`TypeError` with `pass`; late repair incremented `writes` without read-back. A binding failure left the allomorph with a null `StemNameRA` and no `DroppedItemRecord` when `context._dropped` was wired — the same #132 never-silent gap closed for adhoc head RAs and other RA wiring batches.

## Resolution

- Add `_try_wire_allomorph_stem_name_ra`: warning log, GUID read-back, deduped `DroppedItemRecord` with `WRITE_FAILED` detail on failure.
- Route `owned._reproduce_stem_name_ra` and `_repair_one_allomorph` through the helper; count a late-repair write only when read-back confirms the stem GUID.

No semantic change when assignment succeeds and read-back confirms.

## Verification

```bash
PYTHONPATH=src python3 -m pytest \
  tests/unit/test_issue132_stem_name_ra_wire.py \
  tests/unit/test_issue134_med_ref_repair.py \
  tests/unit/test_allomorph_hung_data.py -q
```

**Verdict: GO** — refs #132, #134.
