# coverage-content-fidelity Part B — Attended Live Proof (needs_human) — PASS

## FINAL STATUS: PASS — all 4 new Part B categories transfer 0->N under their
## correct owner collection, idempotent on re-Move. Target restored clean.

**Run:** 2026-07-15 ~10:30, user-authorized (attended). **Execution path:**
FLExToolsMCP `run_module` (flexicon in-process), NOT the FLExTools host
interpreter — per user direction this session. **Driver:**
`debug/run_partB_live.py` (Main-shaped; reuses the MCP-injected `project`
as the read-only SOURCE handle, restores + opens TARGET itself).
**Worktree HEAD:** `d3f501d`. **Exit:** 0 — driver return code 0, all 12
acceptance checks PASS.

### Source selection note

The handoff named `French-FLExTrans-Demo2025`, but a read-only probe showed that
project has **0** phonological feature-struct types (PH TypesOC), so it cannot
prove **B.4 PHON_FEAT_TYPES** live. A read-only sweep found **Mbugwe Lizzie**
carries content for **all four** Part B categories, so it was used as the
read-only source instead (only TARGET is written — within the authorized
destructive scope). French would have left B.4 unproven; Mbugwe Lizzie proves
all four in a single run.

- Source inventory (Mbugwe Lizzie): complex inflection feats **4**, open feats
  **0**, MS feature-struct types **5**, POS inflectable-feat pairs **6**, PH
  feature-struct types **1**.

### Metric

Project-wide, GUID-based (resolution-independent): for each category, the count
of source GUIDs present in the TARGET's owner collection, measured on a fresh
read-only re-open at baseline, after Move #1, and after re-Move #2.

| Category | Owner collection | source | base | post #1 | post #2 |
|---|---|---:|---:|---:|---:|
| B.1 complex inflection features | `MsFeatureSystemOA.FeaturesOC` | 4 | 0 | **4** | 4 |
| B.2 feature_struct_types | `MsFeatureSystemOA.TypesOC` | 5 | 0 | **5** | 5 |
| B.3 pos_inflectable_feats | per-POS `IPartOfSpeech.InflectableFeatsRC` | 6 | 0 | **6** | 6 |
| B.4 phon_feat_types | `PhFeatureSystemOA.TypesOC` | 1 | 0 | **1** | 1 |
| B.1 open features (must NOT create) | `MsFeatureSystemOA.FeaturesOC` | 0 | 0 | 0 | — |

### Plan / Move composition

- **Move #1:** plan actions=64, skips=5. Per-category actions: INFLECTION_FEATURES
  9, FEATURE_STRUCT_TYPES 5, POS_INFLECTABLE_FEATS 6, PHON_FEAT_TYPES 1. Move
  added=64, 0 move-skips for any of the 4 categories.
- **Re-Move #2:** plan actions=0, skips=38. Every one of the 4 categories reports
  its full source count as `ALREADY_PRESENT_BY_GUID` move-skips
  (FEATURE_STRUCT_TYPES 5, POS_INFLECTABLE_FEATS 6, PHON_FEAT_TYPES 1;
  INFLECTION_FEATURES via the GOLD/edit arm) — **0 net-new → idempotent.**

### Acceptance checks (12/12 PASS)

Per category: (a) baseline 0 of source present, (b) all source landed (0 -> N),
(c) idempotent re-Move stable. B.1/B.2/B.3/B.4 all PASS all three. Open-feature
clean-skip check was correctly SKIPPED (source has 0 open features).

### Known deferred item observed live (NOT a regression)

The runtime log shows complex-feature `TypeRA` left unset:
`inflection_features_execute_action: complex feature <guid> references struct-type
<guid> not (yet) present in target MsFeatureSystemOA.TypesOC -- TypeRA left unset
(FEATURE_STRUCT_TYPES coverage sub-part pending)`. This is exactly **post-merge
follow-up concern #1** (TypeRA intra-run two-phase wiring pass): within one run
`inflection_features` dispatches before `feature_struct_types`, so the struct-type
is not yet in the target when the complex feature is created. Owner-collection
creation (0->N) of every category still succeeds; only the cross-link `TypeRA` is
deferred. Slated for a post-merge ticket, per the Part B handoff.

### Residue

Target restored clean from `backups/Target 2026-07-06 0218.fwbackup` at end of
run. `Mbugwe Lizzie` opened read-only only (source untouched).

### Reproduce

`debug/run_partB_live.py`, driven via FLExToolsMCP `run_module`
(`project_name="Mbugwe Lizzie"`, `write_enabled=True`, `confirmed=True`), with
`drv.SOURCE="Mbugwe Lizzie"` and `drv.SELECTED_CAT_NAMES` = the grammar-only
subset (WRITING_SYSTEMS_CHECK, GRAM_CATEGORIES, POS, INFLECTION_FEATURES,
FEATURE_STRUCT_TYPES, POS_INFLECTABLE_FEATS, PHON_FEAT_TYPES,
PHONOLOGICAL_FEATURES).
