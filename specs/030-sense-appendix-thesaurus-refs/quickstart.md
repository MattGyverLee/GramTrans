# Quickstart / Validation Guide: 030 Sense Appendix & Thesaurus References

Proves both sections end-to-end. Because both fields are **vacuous-live across every
project**, validation depends on **constructed fixtures** — there is no harvested data to
transfer.

## Prerequisites

- flexicon installed editable: `pip install -e D:/Github/_Projects/_LEX/flexlibs2`
- Offline test suite runnable: `pytest` from repo root.
- FLExTools MCP available for live proof; a disposable target project
  (`Ejagham Full GT-Test`) that can be restored/cleaned after writes.

## Part 1 — Offline (fakes/unit) proof

```bash
pytest tests/unit/test_cycle16c_sense_scope_gaps.py -q      # appendix + thesaurus cases
pytest tests/verification/fidelity_census.py -q             # both fields report COPIED
```

**Expected**:
- Appendix cases A-link / A-absent / A-partial / A-empty / A-shared pass
  (contracts/appendix-link-by-guid.md).
- Thesaurus cases B-create / B-link / B-nested / B-nolist / B-nomirror / B-empty /
  B-shared pass (contracts/thesaurus-dynamic-owner.md).
- Census: `("LexSense","AppendixesRC")` and `("LexSense","ThesaurusItemsRC")` classify
  as `COPIED`; `OUT_OF_SCOPE_EXCLUDED` unchanged; classifier never-silent guard green.

## Part 2 — Live fixture proof (MCP)

### Fixture construction (write-enabled MCP session on the disposable target)

- **Section A**: in the SOURCE, create a `LexAppendix` (GUID *G*) in `LexDb.AppendixesOC`
  and reference it from a sense's `AppendixesRC`. Prepare TWO target states: (a) target
  that already owns a `LexAppendix` with GUID *G*; (b) target without it.
- **Section B**: in the SOURCE, reference a `CmPossibility` (in some list *L*) from a
  sense's `ThesaurusItemsRC`. Target has the equivalent list *L* but lacks the item.

### Transfer + assertions

| Scenario | Action | Expected (inspect via MCP, read-only) |
|---|---|---|
| A present | transfer sense into target (a) | copied sense `AppendixesRC` → target appendix *G*; dropped-items report has **no** appendix record |
| A absent | transfer sense into target (b) | `LexDb.AppendixesOC` count unchanged (not created); dropped-items report names the sense + `AppendixesRC` + *G* |
| B create | transfer sense into target | item created in target list *L* (with ancestors if nested); copied sense `ThesaurusItemsRC` → it; 0 drops |
| B link | re-run transfer | item linked, not duplicated (list *L* count unchanged); 0 drops |

### Cleanup

Delete the temp appendix/items created in the disposable target (or restore its backup);
confirm the target is left clean, per the 024 live-proof convention.

## Part 3 — Regression guard (common case)

Run a transfer whose source senses reference **no** appendixes or thesaurus items (every
real project). Confirm output is unchanged except that the two fields no longer appear as
DROP_REPORTED gaps (SC-007).

## Done when

- [ ] Part 1 offline suite green.
- [ ] Part 2 four live scenarios observed via MCP with pre/post evidence captured.
- [ ] Part 3 no-regression confirmed.
- [ ] Census shows both fields `COPIED`, never-silent guard intact.
