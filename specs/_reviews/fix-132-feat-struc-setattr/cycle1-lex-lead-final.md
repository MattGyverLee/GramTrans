# Issue #132 — `_get_or_create_feat_struc` owner assignment — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132** (P2 never-silent audit; issue closed, acceptance lists open sites) — **`_get_or_create_feat_struc` setattr** (`impl-111` §5 HIGH list).

After `IFsFeatStrucFactory.Create`, the helper assigned the new structure with a bare `setattr(target_msa, attr, struc)`. A binding failure raised out of the 17.1 sub-pass (or was swallowed only at phase level) while the structure object already existed — a silent partial create with no Skip naming the owner slot. `TypeRA` assignment failures were also swallowed with no log when the type had resolved.

## Resolution

- Wrap the owner `setattr` in `try/except`: log a warning and return `None` so callers (`_wire_msa_infl_feats`, `_wire_owner_feat_strucs`) emit their existing "could not create … structure" Skip instead of aborting the sub-pass.
- Log a warning when `TypeRA` wiring fails after the type GUID resolved (structure still returned; values may still copy).

## Verification

- `tests/unit/test_issue132_feat_struc_setattr.py` (2 tests)

**Verdict: GO** — refs #132 (feat-struc owner assign never-silent).
