# Live Validation Log — #28 MSA->slot producer port (FR-333)

**Run:** 2026-07-15, attended (user-authorized) · **HEAD:** `95cfb81`
**Driver:** `scratchpad/run_msa_slot_live.py` (v2, project-wide count) · exit 0
**Pair:** `Ejagham Mini -> Target` (Target restored from `Target 2026-07-06 0218.fwbackup`)

## FINAL: PASS

| Metric | Value |
|---|---|
| SOURCE MoInflAffMsa / with-SlotsRC / slot-refs | 83 / **79** / 79 |
| TARGET baseline (post-restore) with-SlotsRC | **0** |
| PRODUCER `msa_slot_bindings` on live LCM | **79** MSAs / 79 slot refs (was 0 pre-fix) |
| Move identity_remap entries / MSA keys present | 538 / **79** |
| CONSUMER (17.1 sub-pass) DEPENDENCY_UNRESOLVED skips | **0** |
| TARGET post-Move#1 with-SlotsRC / slot-refs | **79 / 79** (0 -> 79, matches source) |
| TARGET post-Move#2 (idempotent) | 79 / 79 (stable) |

All 5 acceptance checks PASS: producer works on live; target SlotsRC 0 -> 79;
consumer wired all source affix slots; no unresolved skips; idempotent.

## Why the sub-pass is necessary (not redundant)

`categories.py` creates each `MoInflAffMsa` with **`slots=None`**
(`target.MSA.CreateInflAff(new_sense, tgt_pos, slots=None)`, categories.py:4899)
— SlotsRC is **deliberately deferred** to the 17.1 sub-pass because the slots
must exist on the target first. The owned-child copy therefore leaves SlotsRC
empty. The 79/79 wired slots on the target could only have come from the FR-333
consumer `_run_171_subpass` reading the (now non-empty) producer bindings and the
move-populated `identity_remap` (79 MSA keys). This is the exact bug the port
fixes: pre-fix the sole producer was a getattr duck path that no-opped on live
LCM (SlotsRC hidden on the base interface) -> empty dict -> consumer wired
nothing -> affix slots silently lost on live. Offline fakes exposed SlotsRC via
getattr, so the suite could not catch it.

## Driver-bug note (first run vs corrected run)

The first driver (`run_msa_slot_live.log`) reported the consumer check FAILED
because it captured `identity_remap` from a **pre-move preview** (always empty —
remap is populated during `execute_move`, not `compute_preview`) and probed by
GUID, resolving 0/79. That was a probe defect, not a fix defect: MSAs are not
GUID-preserved, so a stale/empty remap can never resolve them. The corrected
driver (v2) uses a GUID-resolution-independent project-wide count of affix MSAs
with non-empty SlotsRC and reads the move-populated remap for diagnostics —
confirming 79 MSA keys land in `identity_remap` and the consumer emits 0 skips.
Cross-checked independently by `scratchpad/diag_msa_slots.py` (target 79/79) and
`scratchpad/diag_remap.py` (preview-time remap empty, as expected).

## Fast-follow (non-blocking, unchanged from cycle-1)

1. Selection-scope: `_populate_msa_slot_bindings` scans the whole lexdb; partial
   transfers can emit false `DEPENDENCY_UNRESOLVED` noise (full-project transfer
   — this proof — is unaffected).
2. Live-cast-path unit coverage (all 10 unit tests hit the duck fallback; this
   live proof is the cast-path evidence).
3. P2 nits (redundant `(ImportError, Exception)` tuple; 115-line function split).
