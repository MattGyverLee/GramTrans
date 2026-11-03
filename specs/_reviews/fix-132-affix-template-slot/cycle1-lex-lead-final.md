# Issue #132 — affix-template slot sequence Add swallow — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without an open PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue **closed**, acceptance batches continue) — **affix-template create-time slot ref sequences** (`impl-111` §5 / issue body: "template slot sequences").

`affix_templates_execute_action` wired `PrefixSlotsRS` / `SuffixSlotsRS` / … with `.Add()` after GUID lookup. Failures were caught as `(AttributeError, TypeError): pass`, so Move could finish with a new template **missing** slot columns and no `DroppedItemRecord`. The #134 repair pass (`_repair_template_slot_seqs`) already reports absent slots and insert failures for **already-present** templates; the **create** path was the remaining silent gap.

## Resolution

- Add `_try_add_affix_template_slot_member`: log + `DroppedItemRecord` on any `Add` exception (deduped via `_append_dropped_once`).
- Route create-time slot wiring through the helper; `context._dropped` unchanged when absent.

## Verification

- `tests/unit/test_issue132_affix_template_slot_add.py` (new, 2 tests)

**Verdict: GO** — refs #132 (affix-template slot sequence Add swallow).
