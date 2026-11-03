# Issue #132 — artifact-schema WRITE_FAILED — lex-lead cycle 1 (final)

## Issue selection

- Open **P0:** none.
- Open **P1 without PR:** only **#22** (conflict-mode epic — not a bounded fix).
- **Chosen:** **#132** (P2 never-silent audit; closed umbrella with open acceptance) — **`artifact-schema.md` did not document the `WRITE_FAILED` affix-slot-link outcome** (impl-111 §6 / #132 body).

Many other #132 sites already have open PRs (#262–#273); this item had none.

## Diagnosis

PR #120 / issue #111 extended `AffixSlotLinkRecord` with `WRITE_FAILED`,
`unwritten_slot_guids`, and `detail`, and wired them through
`report._affix_slot_link_block` into `RunReport.to_dict()` as `affix_slot_links`.
The 035 fullsweep contract (`specs/035-fullsweep-fidelity/contracts/artifact-schema.md`)
never named that block or outcome, so sweep validators and agents reading only
the contract could not interpret a gate artifact that carried write failures —
violating the #132 acceptance line that the schema document the new keys.

## Resolution

- Add an `affix_slot_links` example and a dedicated subsection describing
  `WRITE_FAILED`, `unwritten_slot_guids`, and `detail`.
- Add invariant (11): `WRITE_FAILED` failure rows must carry non-empty
  `unwritten_slot_guids`.
- Pin contract ↔ implementation with
  `tests/unit/test_issue132_artifact_write_failed.py`.

## Verification

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_issue132_artifact_write_failed.py -q
```

**Verdict: GO** — refs #132 (artifact-schema WRITE_FAILED documentation).
