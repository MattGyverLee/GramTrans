# Contract: Reversal-Category Resolution (per-index `PartsOfSpeechOA`) — Part A

Covers how `IReversalIndexEntry.PartOfSpeechRA` is resolved. This is a thin adapter over the
024 `references` resolver, not new resolution logic — the point of the contract is to pin down
the *target list* and *classification*.

## Field spec

```
ReferenceFieldSpec(
    owner_class   = "ReversalIndexEntry",
    field_name    = "PartOfSpeechRA",
    cardinality   = ATOMIC,
    target_list_path = lambda tgt_index: tgt_index.PartsOfSpeechOA,   # PER-INDEX list
    hierarchical  = True,                                             # reversal POS lists nest
)
```

The `target_list_path` receives the **target reversal index** (from the reversal walk), not the
project/lang-project — because `PartOfSpeechRA` points into that index's own
`PartsOfSpeechOA`, which is a distinct `ICmPossibilityList` from `LangProject.PartsOfSpeechOA`
(MCP-confirmed 2026-07-11).

## Resolution (delegated to 024 `decide_reference` / `apply_reference`)

| Condition | action |
|---|---|
| source `PartOfSpeechRA` is None | no-op |
| target index list has same-GUID item, identical (R7 fingerprint) | `LINK` |
| same-GUID, diverged, `not _is_protected` | `UPDATE` (non-destructive) |
| same-GUID, diverged, `_is_protected` | `REPORT_DROPPED` (+ LINK existing) |
| absent, target index list exists | `CREATE` (+ ancestor chain, GUID preserved) |
| target index has no `PartsOfSpeechOA` (or index absent) | `REPORT_DROPPED` (reason `target reversal category list absent`) |

## Guarantees
- Custom-vs-shared classification uses `protection._is_protected` (no new GUID table).
- Hierarchical create walks `source_pos.Owner` up to the list and creates ancestors top-down
  under the correct parent's `SubPossibilitiesOS`, preserving GUIDs.
- Shared per-run cache (024) → a reversal category used by K entries is created at most once.
- Dropped/divergence records carry `owner_kind="ReversalIndexEntry"`,
  `field_name="PartOfSpeechRA"`.
