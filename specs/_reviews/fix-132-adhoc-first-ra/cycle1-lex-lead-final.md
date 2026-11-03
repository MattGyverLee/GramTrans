# Issue #132 — adhoc First*RA assignment never-silent — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#132** (P2 never-silent audit; issue closed, batched acceptance) — **`MoAlloAdhocProhib.FirstAllomorphRA` / `MoMorphAdhocProhib.FirstMorphemeRA`** on the adhoc create path.

Open PR **#267** (`fix-132-adhoc-rest-rs-add`) closes the `RestOfAllosRS` / `RestOfMorphsRS` `.Add` swallow and explicitly defers the head RA fields to a follow-up batch. After GUID resolution, those fields were assigned inside `except (AttributeError, TypeError): pass`, so Move could finish with a created prohibition whose head reference stayed null and no `DroppedItemRecord`.

## Resolution

- Add `_try_wire_adhoc_first_ra`: warning log + deduped `DroppedItemRecord` on assignment failure.
- Route both create-path head RA wires through the helper; thread `context._dropped` once per rule create.

## Verification

- `tests/unit/test_issue132_adhoc_first_ra_add.py` (new, 2 tests)

**Verdict: GO** — refs #132 (adhoc head RA assignment swallow).
