# Issue #132 — late repair Insert never-silent — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; closed umbrella) — **`_insert_missing_in_order` / `Insert` on #134 late repair** (`PositionRS` on allomorphs, affix-template slot sequences). Open PR **#279** covers `PhoneEnvRC.Add` on the same helper only; this slice is distinct.

`_insert_missing_in_order` called `tgt_seq.Insert(idx, found)` with no guard. A raising or no-op Insert could leave the member missing while incrementing `writes`, or abort the whole late pass — the same silent-loss shape #111 fixed for `SlotsRC.Add` and the broader #132 audit targets for `.Add` sites.

## Resolution

- Extend `_insert_missing_in_order` with optional `on_insert_failed(src_obj, guid, detail)`.
- On Insert failure or read-back mismatch: invoke the callback and continue (never abort the pass).
- When Insert raises but read-back shows the member at the expected index: log a warning and do not count a write (#111 parity).
- Wire `on_insert_failed` from `_repair_one_allomorph` (`PositionRS`) and `_repair_template_slot_seqs` (`DroppedItemRecord` with `WRITE_FAILED`-style detail).

No semantic change when Inserts succeed and read-back confirms.

## Verification

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_issue134_med_ref_repair.py -q
```

**Verdict: GO** — refs #132, #134.
