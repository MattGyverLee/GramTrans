# Issue #132 batch 2 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 bugs without an open PR: none (#22 is the sole open P1 epic).

Selected **#132** follow-up (P2 never-silent audit, issue closed; MattGyverLee comment 2026-11-01): after #183 fixed GenresRC `.Add` swallowing, two reference-field paths still used `except (AttributeError, TypeError): pass` on collection `.Add`:

- `categories._apply_reference_fields` (~7185)
- `owned._apply_child_refs` (~456)

When `apply_reference` succeeded but `.Add` failed (live pythonnet binding gaps), the decision was applied in memory but the owner collection stayed empty with no `DroppedItemRecord` — same shape as pre-#161 text genres silent loss.

## Resolution

- Add `categories._add_resolved_to_reference_collection` (shared helper, #161 drop pattern + `_append_dropped_once` / `_enrich_dropped`).
- Route `_apply_reference_fields` collection writes through the helper.
- Route `owned._apply_child_refs` collection writes through the helper (lazy import of `categories`).

## Verification

- `tests/unit/test_issue132_ref_collection_add.py` (helper, `_apply_reference_fields`, `_apply_child_refs`)

**Verdict: GO** — refs #132 (batch 2: reference collection Add failures).
