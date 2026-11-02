# Issue #139 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#139** (P3 umbrella, no open PR) — item **MsEnvFeaturesOA dual writer**.

Feature 028 (`owned.reproduce_moaffix_msenv_data` / `_reproduce_msenv_features_oa`) is the canonical Move writer for `MoAffixAllomorph.MsEnvFeaturesOA` at allomorph create time. Feature 038 T119's post-loop `_wire_owner_feat_strucs` also processed `msa_feat_struc_bindings` for the same attribute on owners recorded in `context._copy_set`. On a newly created allomorph both legs ran, so the T119 pass could fight the owned deep-copy (reported in batch 107–116 impl-110 as a fidelity defect, not merely a tally drift).

Other #139 items (picks asymmetry comment + pin test, hand-built plan TypeRA derivation, Preview-vs-Move Wire count warning, live GUID load) were already on `main`.

## Resolution

- In `_wire_owner_feat_strucs`, skip `MsEnvFeaturesOA` bindings whose `owner_guid` is in `context._copy_set` (allomorph created this run and already handled by feature 028).
- Pre-existing allomorphs (not in `_copy_set`) still use the T119 pass to fill hollow matched structures.

## Verification

- `tests/unit/test_issue139_msenv_single_writer.py` (new)
- `tests/unit/test_038_t119_feat_struc_owners.py` (unchanged stem/deriv paths)
- `tests/unit/test_issue37_complex_type_ra.py::TestIssue139` (unchanged)

**Verdict: GO** — closes the dual-writer item on #139 (refs #139).
