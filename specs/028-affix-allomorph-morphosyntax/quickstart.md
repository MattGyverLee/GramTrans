# Quickstart & Validation: Affix-Allomorph Morphosyntax Fidelity

How to validate feature 028 end-to-end. Two tiers: **offline** (unit + census, autonomous) and
**attended live** (a constructed non-Ejagham fixture — a T037-class item, never under an
unattended loop).

## Prerequisites

- Repo at the 028 worktree (`../GramTrans-028-affix-allomorph-morphosyntax` on branch
  `028-affix-allomorph-morphosyntax`), created at implementation start per CLAUDE.md.
- `pip install -e D:/Github/_Projects/_LEX/flexlibs2` (flexicon / `pyflexicon>=4.1`).
- For the live tier only: FLExToolsMCP active and a disposable, `-restore`-ready target.

## Tier 1 — Offline (autonomous)

### Unit suite
```powershell
python -m pytest tests/unit/test_028_affix_msenv_reproduction.py tests/unit/test_028_msenv_feature_struct.py -q
```
Expected: all pass. Coverage (see `contracts/affix-msenv-reproduction.md` test obligations):
- CREATE / LINK / REPORT_DROPPED per field family (POS ref, inflection classes, feature
  structure, positions).
- Preview/Move parity (G6), `PositionRS` order (G5), dedup (G4), empty-source no-blank (G2),
  vacuous `MoStemAllomorph`/unpopulated `MoAffixAllomorph` (SC-006).

### Fidelity census (FR-009)
```powershell
python -m pytest tests/verification/ -q
```
Expected: the four `("MoAffixAllomorph", …)` rows classify **COPIED** (was DROP_REPORTED);
`classify_field` never-silent guard still passes; no unclassified field.

### Full regression
```powershell
python -m pytest tests/unit -q
```
Expected: no new failures beyond the documented pre-existing baseline
(`test_wizard_pos_grammar_wiring`). SC-006: a transfer whose allomorphs populate none of the
four fields is byte-identical to a pre-028 run except for the (empty) report contribution.

## Tier 2 — Attended live proof (needs_human)

Ejagham Mini/Full are **vacuous** for these four fields (0/106 allomorphs populate any), so
the live `0→N` proof requires a **constructed fixture** — mirrors feature 027's constructed
complex-form proof. **Never run under an unattended loop.**

### Build the fixture
On a disposable source project, add an affix entry whose allomorph populates all four fields:
a `MsEnvPartOfSpeechRA` (POS absent from target), an `InflectionClassesRC` member (class under
that POS), a `MsEnvFeaturesOA` with ≥1 closed-feature value, and a `PositionRS` with ≥2
ordered infix positions referencing environments present in the target.

### Run (attended)
1. `-restore` the target from a clean backup; confirm no FLEx GUI / no `.lock`.
2. Preview (read-only): confirm the plan shows CREATE for the POS + inflection class,
   deep-copy for the feature structure, LINK for the positions' environments — no writes to
   the target on disk.
3. Move: run source → restored target.
4. Verify on fresh re-open:
   - target allomorph `MsEnvPartOfSpeechRA` → created POS (GUID preserved);
   - `InflectionClassesRC` → class present under the created POS, referenced;
   - `MsEnvFeaturesOA` → deep-copied structure with values resolved;
   - `PositionRS` → positions present **in source order**.
5. Re-Move (idempotency): 0 duplicate POS / classes / positions (dedup, SC-005).
6. Force one unresolvable item (e.g. a position env absent from target) → confirm a
   `DroppedItemRecord` names it (SC-003, never silent).

Record evidence in `specs/028-affix-allomorph-morphosyntax/verification-log.md` per STATUS.md
conventions.

## Success criteria mapping

| SC | Validated by |
|---|---|
| SC-001 (100% reproduced) | Tier 1 CREATE/LINK tests + Tier 2 step 4 |
| SC-002 (no blanking) | Tier 1 empty-source no-blank test (G2) |
| SC-003 (never silent) | Tier 1 REPORT tests + Tier 2 step 6 |
| SC-004 (census clean) | Tier 1 census flip |
| SC-005 (dedup) | Tier 1 dedup test + Tier 2 step 5 |
| SC-006 (no regression) | Tier 1 vacuous test + full regression |
