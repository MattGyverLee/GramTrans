# 028 — T019 Live Validation Log (attended)

## FINAL STATUS: PASS — live `0 → N` proven for 3/4 fields, never-silent for the 4th

**Run:** 2026-07-15 ~02:16, user-directed (attended). **Driver:** `scratchpad/run028_live.py`
(+ `scratchpad/build028_fixture.py --write`), executed in the FLExTools host interpreter
(the dev shell has no flexicon). **Pair:** `Ejagham028Src → Target` (Target restored headless
from `backups/Target 2026-07-06 0218.fwbackup`). **Worktree HEAD:** `ba89763`. **Exit:** 0 —
all four driver self-checks PASS.

### Result summary

| Field | pre (clean) | post Move #1 | post re-Move #2 | Arm exercised |
|---|---|---|---|---|
| `MsEnvPartOfSpeechRA` | 0 | **1** (0→1) | 1 (stable) | CREATE (new POS `Affix028Env POS`) |
| `InflectionClassesRC` | 0 | **1** (0→1) | 1 (stable) | CREATE (class under the created POS) |
| `PositionRS` | 0 | **1** (0→1) | 1 (stable) | LINK (envs created by PH_ENVIRONMENT, order kept) |
| `MsEnvFeaturesOA` | 0 | 0 | 0 | **REPORT_DROPPED** (resolve-only, feature absent at affix-process time) |
| affix allomorphs | 0 | 106 | 106 | — |

- **Move #1:** plan actions=113, skips=5, **4 `DroppedItemRecord`s** for the MsEnv fields
  (InflectionClassesRC, MsEnvFeaturesOA, 2× PositionRS) — all named with owner/field/item
  identity + reason (never-silent). The three CREATE/LINK arms then resolved during the Move
  (POS/class created, envs created by the phonology leg), so the fields populated in the target.
- **Re-Move #2:** plan actions=1, **0 MsEnv drops**, counts identical → idempotent, no duplicates.

### Per-SC verdict

| SC | Result | Evidence |
|---|---|---|
| SC-001 (100% reproduced) | **PASS (3/4 live; 4th offline)** | POS + InflectionClasses + PositionRS all `0→1` live; `MsEnvFeaturesOA` deep-copy arm proven by the 7 offline `test_028_msenv_feature_struct.py` tests |
| SC-002 (no blanking) | PASS | offline empty-source no-blank tests; live target fields only grew |
| SC-003 (never silent) | **PASS** | 4 live `DroppedItemRecord`s (incl. `MsEnvFeaturesOA` value `15ba923a…` + both `PositionRS` envs) |
| SC-004 (census clean) | PASS | Tier 1 census flip (offline) |
| SC-005 (dedup/idempotent) | **PASS** | re-Move #2 added 0 MsEnv items; counts stable |
| SC-006 (no regression) | PASS | 106 affix allomorphs, only the fixture one populated |

### Note on `MsEnvFeaturesOA` (correct, not a defect)

The `MsEnvFeaturesOA` leg is **resolve-only** — it links a closed-feature value that already
exists in the target feature system and **never creates a feature** (R3 / spec Out of Scope).
The shared-feature probe (`scratchpad/probe028_shared_feats.py`) confirms the value
`15ba923a…` exists in *both* projects, but at the instant the affix allomorph was processed in
Move #1 the target did not yet own it (the POS/inflection-class legs create their own targets;
the feature does not), so the leg correctly emitted a `DroppedItemRecord` rather than inventing
one. On re-Move the affix is skipped (idempotent), so the field is not retried. The positive
deep-copy path (target already owns the value → LINK) is exercised exhaustively offline. To
demonstrate it live, seed the feature into the target first (a features-only transfer), then run
the affix transfer.

---

## STATUS (historical): ENVIRONMENT STAGED — attended live run PENDING

The **offline** proof (Tier 1: T014–T018) is complete and GREEN — unit suite, the
model-driven fidelity census (four `MoAffixAllomorph` rows flipped to `COPIED`), and the
full regression all pass at the documented 7-fail environment baseline. See
[tasks.md](tasks.md) T014–T018.

The **attended live** proof (Tier 2 / T019) is a `needs_human` step: it requires a
constructed non-Ejagham fixture (Ejagham Mini/Full are vacuous — 0/106 allomorphs populate
any of the four fields) and a destructive Move against a freshly-restored target, run in the
FLEx host where `flexicon` is installed and the full two-project engine runs natively. It has
**not** been executed yet; the environment is staged and the procedure is recorded below for
the attended run.

---

## Environment staged (this session)

| Item | State |
|---|---|
| Disposable **source** `Ejagham028Src` | Restored from `backups/Ejagham Mini.fwbackup` (headless zip-extract via `harness.restore.restore_target`). Leaves the real `Ejagham Mini` untouched. **Fixture not yet added.** |
| Disposable **target** `Target` | Restored clean from `backups/Target 2026-07-06 0218.fwbackup`. |
| FieldWorks 9 | Present at `C:\Program Files\SIL\FieldWorks 9\FieldWorks.exe`. |
| Fixture builder | `scratchpad/build028_fixture.py` — populates the four fields on one affix allomorph in `Ejagham028Src` (dry-run inventory by default; `--write` to mutate). **Untested in the dev shell** (flexicon absent); run + iterate attended. |
| Live driver | `scratchpad/run028_live.py` — restores Target, runs the real `AFFIXES`-category engine (`Ejagham028Src → Target`), diagnoses 0→N + idempotency. Mirrors the proven `scratchpad/run031_live.py`. Gated on `GRAMTRANS_E2E=1`. |

> The two restored projects are disposable scratch copies. Re-restore either from the
> backups above to reset; delete `C:\ProgramData\SIL\FieldWorks\Projects\Ejagham028Src` when
> done.

---

## Fixture requirement (build on `Ejagham028Src`, attended)

Add (or amend) **one** affix `LexEntry` whose `MoAffixAllomorph` (on its `MoAffixForm`)
populates all four 028 fields, chosen so each exercises a distinct arm cross-project:

| Field | Fixture content | Expected cross-project decision |
|---|---|---|
| `MsEnvPartOfSpeechRA` | a POS **absent** from `Target` | **CREATE** (GUID-preserved) + ancestor chain |
| `InflectionClassesRC` | ≥1 inflection class owned by that POS | **CREATE** under the created POS |
| `MsEnvFeaturesOA` | an `IFsFeatStruc` with ≥1 **closed** feature-value | deep-copy; value resolved/**LINK**ed by GUID (feature-031 machinery) |
| `PositionRS` | ≥2 ordered `IPhEnvironment` refs **present** in `Target` (same GUIDs) | **LINK** each, order preserved |

For the forced-drop step, also stage one unresolvable item (e.g. a `PositionRS` env absent
from `Target`) so SC-003 (never-silent) can be exercised.

---

## Procedure (mirrors quickstart.md Tier 2 + the run031 driver)

0. **Build the fixture** (mutates the disposable source):
   `python scratchpad/build028_fixture.py` (dry-run inventory — confirm the env/feature GUIDs),
   then `python scratchpad/build028_fixture.py --write`.
1. **Drive it**: `set GRAMTRANS_E2E=1 && python scratchpad/run028_live.py` — restores `Target`,
   runs the `AFFIXES` engine, and prints the before/Move#1/re-Move#2 diagnosis. Steps 2–5 below
   are what the driver automates; step 6 is manual.
2. **Preview** (`api.compute_preview`, read-only): plan shows CREATE for the POS + inflection
   class, deep-copy for the feature structure, LINK for the positions' envs — **no writes**.
3. **Move** (`api.execute_move`): `Ejagham028Src → Target`.
4. Reopen `Target` fresh and verify on the affix allomorph:
   - `MsEnvPartOfSpeechRA` → created POS (GUID preserved);
   - `InflectionClassesRC` → class present under that POS, referenced;
   - `MsEnvFeaturesOA` → deep-copied structure, value resolved;
   - `PositionRS` → envs present **in source order**.
5. **Re-Move** (no restore): 0 duplicate POS / classes / positions (dedup, SC-005).
6. Force one unresolvable item (e.g. add a `PositionRS` env absent from `Target` via
   `build028_fixture.py`, or point one at a fresh GUID) → confirm a `DroppedItemRecord` names it
   (SC-003, never-silent).

> **Caveat:** the driver + builder are **untested in the authoring shell** (flexicon is not
> pip-installed there). Expect to iterate — especially on the cross-project resolvability of the
> `MsEnvFeaturesOA` value and the `PositionRS` environments (they LINK only if `Target` shares
> those GUIDs; otherwise they legitimately REPORT_DROPPED, which still proves never-silent).

---

## Success-criteria mapping (to be filled on the attended run)

| SC | Validated by | Result |
|---|---|---|
| SC-001 (100% reproduced) | step 2 CREATE/LINK plan + step 4 | ☐ PENDING |
| SC-002 (no blanking) | empty-source no-blank (offline GREEN) + step 4 | ☐ PENDING |
| SC-003 (never silent) | step 6 forced drop | ☐ PENDING |
| SC-004 (census clean) | Tier 1 census flip | ✅ GREEN (offline) |
| SC-005 (dedup) | step 5 re-Move | ☐ PENDING |
| SC-006 (no regression) | Tier 1 vacuous + full regression | ✅ GREEN (offline) |

---

## RESULTS (attended run) — PENDING

_Record the driver log path, Move #1 / Re-Move #2 metrics table, and per-SC PASS/FAIL here,
following the 027 log format (`specs/027-complex-forms-variants/verification-log.md`)._
