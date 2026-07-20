# Contract: Per-Category Preview Props (Stage-1 readers)

**Feature**: 032 | Consumed by `diff_props` → `to_html` in `Lib/merge_preview.py`

## Dispatch registration contract

For each newly covered category, both dispatch tables MUST be updated consistently:

- `_CATEGORY_VALUE_TO_KEY` (~1148-1160): map the wizard `GrammarCategory.value` to a
  non-`None` ops-key (blank categories currently map to `None` or table-miss).
- `_PROPS_TABLE` (~1087-1119): the key resolves to `(ops_attr, finder_fn, needs_owner,
  is_gap)` OR a dedicated path (like the inflection-feature branch ~1230).

**Invariant**: after registration, `props_for(category, guid, ...)` returns a non-empty
dict for a populated item of that category, and the UI pane's string dispatch
(`ui/merge_preview_pane.py` `_render_preview`) needs no change.

## Reader output contract (all categories)

| Rule | Requirement |
|---|---|
| Shape | plain dict — scalar `str`, multistring `{ws_id: text}`, or `list[str]` of resolved labels |
| Non-blank | populated item → non-empty dict (SC-001) |
| Degradation | read/cast failure → label-level dict + `debuglog` entry, never `None`, never blank pane (FR-011) |
| Bounding | unbounded fields truncated with an indicator field (FR-018) |
| Read-only | no writes, no LCM object mutation, no Move-plan change (FR-010) |
| Diff-compat | shapes must be consumable by `diff_props` so new-vs-differs (FR-009) works unchanged |

## Per-category field contracts

See [data-model.md](../data-model.md) for the field tables. Summary of the eight:

| Category | Key fields beyond Name/Abbrev/Desc |
|---|---|
| Text | Title, bounded Baseline excerpt, Truncated indicator |
| Writing System | Code, Kind, Rank, MapsTo |
| Complex Form Type | Type/pattern detail (diffed if target match) |
| Ad hoc/Compound rule | ReferencedElements (morphemes/classes) |
| Phonological Feature | Type, Values |
| Phonological Rule | Structure (StrucDesc/RHS/environment/ordering) |
| Slot | Affixes (bounded) |
| Natural Class | Members, Features (regression fix — must be present after) |

## Acceptance

- Offline: `test_merge_preview_props.py` / `test_merge_preview_html.py` assert a non-empty
  props dict and non-blank HTML for a populated item of each category.
- Natural Class: a test asserts Members/Features **absent before** the fix and **present
  after** on identical data (SC-003).
- Qt-free: `test_merge_preview_qt_free.py` still passes (SC-007).
- Live: read-only render pass over real projects asserts non-blank panes (SC-008).
