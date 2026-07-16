# Contract C-A: Appendix reference, link-by-GUID (Section A)

**Field**: `LexSense.AppendixesRC` → `LexAppendix`
**Requirements**: FR-001, FR-002, FR-006, FR-007, FR-008; SC-001, SC-002, SC-005

## Behavior

For each `LexAppendix` referenced by a source sense's `AppendixesRC`, during both the
Preview decision pass and the Move write pass:

```
INPUT:  src_appendix (ILexAppendix), target (FLExProject), copied_sense (target)
STEP 1: guid = src_appendix.Guid
STEP 2: tgt_appendix = first a in ILexDb(target...LexDbOA).AppendixesOC where a.Guid == guid
STEP 3a (found):  Move  -> add tgt_appendix to copied_sense.AppendixesRC (idempotent)
                  Prev  -> record decision LINK (no DroppedItemRecord)
STEP 3b (absent): emit DroppedItemRecord(owner_kind="LexSense", field_name="AppendixesRC",
                  item_guid=guid, item_name="", reason="no LexAppendix with this GUID in
                  target LexDb.AppendixesOC (030 link-by-GUID scope; not created)")
```

## Guarantees

| ID | Guarantee |
|---|---|
| G-A1 | A referenced appendix present in target by GUID is linked; **no** `DroppedItemRecord` for it. |
| G-A2 | A referenced appendix absent from target is **never created**; its `IStText` `ContentsOA` is never reproduced; exactly one `DroppedItemRecord` is emitted. |
| G-A3 | An empty/unset source `AppendixesRC` never blanks a populated target `AppendixesRC`. |
| G-A4 | An appendix referenced by K senses is linked at most once per sense; no duplication in `LexDb.AppendixesOC`. |
| G-A5 | Preview decision set == Move drop set for this field, by construction. |
| G-A6 | Never raises on absent GUID (linear scan, not `Repository.GetObject`). |

## Test cases (fakes + fixture)

| Case | Setup | Expected |
|---|---|---|
| A-link | source sense → appendix G; target owns appendix G | sense.AppendixesRC contains target G; 0 drops |
| A-absent | source sense → appendix G; target lacks G | 0 created; 1 DroppedItemRecord for G |
| A-partial | source sense → {G1,G2}; target owns only G1 | G1 linked; 1 drop for G2 |
| A-empty | source sense AppendixesRC empty; target sense has appendix | target unchanged (no blank) |
| A-shared | two senses → appendix G; target owns G | both link G; no dup |
