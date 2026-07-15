# 028 — T019 Live Validation Log (attended)

## STATUS: ENVIRONMENT STAGED — attended live run PENDING

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
| Template driver | `scratchpad/run031_live.py` (feature 031 — 028's `MsEnvFeaturesOA` leg reuses its closed-feature machinery, R3). The 028 driver mirrors it with a focused Selection that walks affix entries + their allomorph hung-data. |

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

1. Confirm `Target` is closed in FLEx (no `.lock`); `restore.restore_target("Target", backup_path="backups/Target 2026-07-06 0218.fwbackup")`.
2. **Preview** (`api.compute_preview`, read-only): confirm the plan shows CREATE for the POS +
   inflection class, deep-copy for the feature structure, LINK for the positions' envs — and
   **no writes** to `Target` on disk.
3. **Move** (`api.execute_move`): `Ejagham028Src → Target`.
4. Reopen `Target` fresh and verify on the affix allomorph:
   - `MsEnvPartOfSpeechRA` → created POS (GUID preserved);
   - `InflectionClassesRC` → class present under that POS, referenced;
   - `MsEnvFeaturesOA` → deep-copied structure, value resolved;
   - `PositionRS` → envs present **in source order**.
5. **Re-Move** (no restore): 0 duplicate POS / classes / positions (dedup, SC-005).
6. Force one unresolvable item → confirm a `DroppedItemRecord` names it (SC-003, never-silent).

Run gate: `set GRAMTRANS_E2E=1` (double-gated so it never runs unattended).

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
