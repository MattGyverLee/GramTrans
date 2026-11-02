# Issue #178 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 without an open PR: none (#22 is feature-scale). Selected **#178** (P3 umbrella, no open PR): PR #239 landed items 1–3 and the Preview/Move wording fixes on `main`, but the issue stayed open and item 4 lacked dedicated regression tests for the two DROP labels (`part of speech absent` vs `feature absent`) and the planned-create exceptions.

## Resolution

- Add `tests/unit/test_issue178_preview_link_labels.py` pinning Preview rows for item 4 (POS absent DROP, feature absent DROP, planned POS/feature still show Link).
- Close the umbrella: all four acceptance bullets are satisfied on `main` plus the new tests.

## Verification

- `python -m pytest tests/unit/test_issue178_preview_link_labels.py -q`
- Existing #178 coverage in `tests/unit/test_133_pos_inflfeats_single_writer.py` (items 1 and 3) and `tests/unit/test_133_deferred_reconciliation.py` (item 2)

**Verdict: GO** — closes #178.
