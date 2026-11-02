# fix-132 sense-list Add swallow — lex-lead cycle 1

**Issue**: #132 (P2, never-silent audit; issue closed, acceptance batches continue)  
**Scope**: `LexSense.AppendixesRC` and `LexSense.ThesaurusItemsRC` post-resolver `.Add()` writes

## Diagnosis

No open P0 bugs. Open P1 without a PR is only #22 (epic). Selected **#132** site batch — `AppendixesRC` / `ThesaurusItemsRC` from the issue body's RA/RS `except: pass` list — with **no open PR** (distinct from ref-collection, StratumRA, post-pass A, TargetsRS batches already in flight).

After a successful target-side resolution, Move recorded a LINK `ReferenceDecisionRecord` then called `coll.Add(...)`. Failures were caught as `(AttributeError, TypeError): pass`, so the run report showed a clean link while the sense collection stayed empty — SC-010 never-silent violation on a real 030 path. A missing collection attribute took the same silent path (`coll is None` skipped the Add without a drop).

## Resolution

- Added `_report_sense_list_add_failure` and call it when the sense collection is missing or `.Add()` raises (any exception).
- Applied to `_resolve_sense_appendixes` and `_resolve_sense_thesaurus_items` Move writes only; Preview behaviour unchanged.

## Verification

- `tests/unit/test_issue132_sense_list_add_swallow.py` (new)
- `tests/unit/test_cycle16c_sense_scope_gaps.py` appendix section (regression)

**Verdict: GO** — refs #132 (AppendixesRC / ThesaurusItemsRC Add swallow).
