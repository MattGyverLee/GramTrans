# Contract C-B: Thesaurus reference, dynamic-owner resolver (Section B)

**Field**: `LexSense.ThesaurusItemsRC` → generic `CmPossibility`
**Requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008; SC-003, SC-004, SC-005

## Behavior

For each `CmPossibility` referenced by a source sense's `ThesaurusItemsRC`, during both
the Preview decision pass and the Move write pass:

```
INPUT:  src_item (ICmPossibility), target (FLExProject), copied_sense (target)
STEP 1  discover source owning list:
          cur = ICmObject(src_item)
          for _ in range(DEPTH_CAP):
              if cast ICmPossibilityList(cur) succeeds: src_list = cur; break
              if cur.Owner is None: break
              cur = cur.Owner
          if no src_list: DROP("owning CmPossibilityList not found on source"); continue
STEP 2  mirror to target list:
          owner_class = src_list.Owner.ClassName ; flid = src_list.OwningFlid
          tgt_list = target list reached by (target owner of owner_class) + flid
          fallback: target ICmPossibilityList whose Name matches src_list.Name
          if none: DROP("owning CmPossibilityList could not be resolved in target"); continue
STEP 3  resolve item via 024 resolver:
          spec = ReferenceFieldSpec("LexSense","ThesaurusItemsRC", COLLECTION,
                                    target_list_path=lambda _: tgt_list, hierarchical=True)
          decision = references.decide_reference(src_item, target, spec, cache, source=...)
          Move  -> references.apply_reference(decision, target, copied_sense, spec, cache, tag, ...)
          Prev  -> record decision (ADD / LINK / UPDATE / SKIP)
          any residual unresolvable item -> DroppedItemRecord (never silent)
```

## Guarantees

| ID | Guarantee |
|---|---|
| G-B1 | A referenced item whose owning list resolves and is absent in target is **created** in the equivalent target list, including its hierarchical ancestor chain, and the sense references it. |
| G-B2 | A referenced item already present in the equivalent target list is **linked** (024 custom-vs-shared/default reconciliation), never duplicated. |
| G-B3 | If the owning `ICmPossibilityList` cannot be discovered (source) or mirrored (target), exactly one `DroppedItemRecord` is emitted; **no throw**, no silent loss. |
| G-B4 | The equivalent target list is found by owner-class + `OwningFlid` (model-stable), never by list GUID (list GUIDs differ per project). |
| G-B5 | An empty/unset source field never blanks a populated target field. |
| G-B6 | An item referenced by K senses is created/linked at most once (resolver cache). |
| G-B7 | Preview decision set == Move outcome set (+ identical residual drops), by construction. |

## Test cases (fakes + fixture)

| Case | Setup | Expected |
|---|---|---|
| B-create | src sense → item I in list L; target has equiv list, lacks I | I created in target L (with ancestors); sense refs it; 0 drops |
| B-link | src sense → item I; target equiv list already has I | I linked; no dup; 0 drops |
| B-nested | src item I nested under parent P in L | P then I created; I at correct depth |
| B-nolist | src item's `.Owner` never reaches a list (synthetic) | 1 DroppedItemRecord; no throw |
| B-nomirror | owning list has no target equivalent (owner+flid and Name both miss) | 1 DroppedItemRecord; no throw |
| B-empty | src ThesaurusItemsRC empty; target sense populated | target unchanged (no blank) |
| B-shared | two senses → item I | I created once; both ref it |
