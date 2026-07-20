# Contract: Writing-System Mapping Default (related languages)

**Feature**: 032 (US4) | Surface: `Lib/ws_mapping.py`

## Inputs

- Source WS inventory and target WS inventory (enumerated via `_enumerate_ws` ~158).
- Each side has (at most) one **primary vernacular** WS; zero or more **sub** WSs whose
  tags extend the primary's base subtag.

## Default computation

1. **Primary → primary** (FR-012): source primary vernacular WS defaults to the target's
   primary vernacular WS when the target has one.
2. **Sub → sub by suffix** (FR-013): for each source sub WS, compute its subtag suffix
   *relative to the source primary vernacular base* (e.g. `eja-fonipa` with primary `eja`
   → suffix `-fonipa`). Default it to the target sub WS whose suffix *relative to the
   target primary vernacular base* equals it (e.g. target `abc-fonipa` → suffix
   `-fonipa`), even though base subtags differ (`eja` vs `abc`).
3. **Real mapping only** (FR-014): a default MUST be a concrete target WS Id — never
   "create new", never "skip".

## Ambiguity / no-correspondence (FR-015, spec Edge Cases)

| Situation | Behavior |
|---|---|
| Target has no primary vernacular | primary row left unresolved |
| No target sub shares the source sub's suffix | that row left unresolved |
| >1 target sub shares the suffix | treated as not unambiguous → left unresolved |

Unresolved rows keep confirmation **gated** (`is_complete` / `validate` still fail until
the user resolves them). No false auto-mapping is ever written.

## Non-goals

- Does not create target WSs (materialization stays in `Lib/transfer.py` pre-step).
- Does not change `WSChoice.SKIP` semantics (still not folded).

## Acceptance

- `test_ws_mapping.py`: clean related-languages pair → primary→primary + every sub→sub
  pre-filled; step confirmable with **no manual edits** (SC-004).
- `test_ws_mapping_detect.py`: ambiguous/absent correspondence → row unresolved, confirm
  gated; suffix match works across differing base subtags (`eja-fonipa`→`abc-fonipa`).
- Live: WS wizard pre-fill exercised read-only against the reference pair (SC-008).
