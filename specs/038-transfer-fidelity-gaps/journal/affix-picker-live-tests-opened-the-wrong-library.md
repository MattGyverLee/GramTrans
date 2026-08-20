# The affix-picker live tests opened the wrong library and read nothing

**Status:** closed. `tests/integration/test_affix_pos_picker_live.py`, plus a
sweep into two sibling live files. No production code changed.

Not a 038 task -- surfaced while verifying the T028 tripwire remedy, where the
full suite showed 24 failures that skipped when the file ran alone.

## The symptom, and why it was misleading

Every assertion failed in the same shape:

```
E   AssertionError: Expected 68 affixes, got 0
esp_inv = PosGroupedAffixInventory(roots=(), junk=JunkDrawer(no_pos=(), no_analysis=()), ...)
```

Zero of everything, on a project that has 15,318 entries. That reads as a data
regression or a broken builder. It was neither: **no project was ever read.**

## Root cause -- the wrong library, plus a fail-soft that hid it

`_get_source` opened through stock `flexlibs`. GramTrans depends on **flexicon**
(dist `pyflexicon`), a standalone package that is not a fork of stock flexlibs
(CLAUDE.md). Both are importable in this environment, so the import succeeded.

Measured directly, read-only, on `Ejagham Full GT-Test`:

| Handle | `Cache` | `...LexDbOA.Entries` | inventory |
|---|---|---|---|
| `flexlibs.FLExProject` | **AttributeError: no attribute 'Cache'** | AttributeError | affixes=0 |
| `flexicon.FLExProject` | OK | OK | affixes=0 (project is empty -- see below) |

`build_pos_grouped_inventory` reads `source.Cache.LangProject.LexDbOA.Entries`
and `...PartsOfSpeechOA.PossibilitiesOS` behind
`except (AttributeError, TypeError)` and substitutes `[]`
(`selection.py:708`, `:716`). That fail-soft is correct for one malformed
object inside a real walk. It is wrong as a way to discover that the handle is
the wrong type entirely, because it converts "no project was read" into "this
project has no affixes" -- indistinguishable from a data regression, and
exactly how this hid for seven weeks.

## Why it skipped alone and failed in a suite

The file's own header said *"STATUS: Written, not executed."* It had never run.

`_get_source` wrapped everything in `except Exception -> pytest.skip`. A
standalone process must call `ensure_flex_initialized()` before any
`OpenProject`; without it the open throws (the harness names
`RegistryHelper.get_CompanyKey()`). So:

* **file alone** -- FieldWorks uninitialized, open raises, swallowed into
  `pytest.skip`. 29 skipped, and the file looked inert.
* **inside a full suite** -- an earlier test had already initialized
  FieldWorks, so the open "succeeded" and handed back the Cache-less handle
  from above. 24 failed.

The skip/fail split was never about ordering flakiness. It was the difference
between the bug being reachable and not.

`ensure_flex_initialized()` now runs before every open. It is idempotent and
re-verifies the SLDR rather than trusting a once-per-process latch -- the
harness warns that a `FLExCleanup()` in any fixture takes the SLDR down for the
rest of the session, and that the next open can then **quarantine the project's
`WritingSystemStore/*.ldml`**. `Esperanto` is read-only in the strong sense, so
this file must never be the thing that damages it.

## `_require_readable`

The fixtures now assert the handle exposes both LCM paths before the inventory
is trusted, and raise with a message that names the actual failure ("this is a
WRONG HANDLE, not an empty project") instead of letting a count of 0 stand in
for it. Verified to fire against a Cache-less object.

## Three anchors used the wrong instrument

With the handle fixed, **16 of 19 Esperanto anchors matched the contract
exactly** on the first live run: total 68, multi-POS 13, junk 7/0, all seven
attaches-to figures, all four produces figures.

The three that did not were `infl / deriv / uncl`, contract `41 / 31 / 12`,
measured `30 / 30 / 2`. The clue was sitting in the contract: 41+31+12 = **84**,
against an affix total of **68**. Those are not entry counts. Measured live over
the 68 affix entries:

| MSA class | MSAs | distinct entries |
|---|---|---|
| `MoInflAffMsa` | **41** | 30 |
| `MoDerivAffMsa` | **31** | 30 |
| `MoUnclassifiedAffixMsa` | **12** | 12 |
| total | **84** | -- |

The contract counted **MSAs**; `_count_affix_rows_by_msa_kind` counts distinct
entry GUIDs reached through the POS tree. Both are correct quantities and only
one is the anchored one. `_count_msas_by_class` is the matching instrument, and
both quantities are now pinned side by side so they cannot drift into each
other again -- plus the reconciliation (84 MSAs > 68 entries) as a stated
property rather than a suspicious inconsistency.

The `uncl` gap is the most informative: 12 entries carry an unclassified MSA
but only 2 reach a POS node, because an `MoUnclassifiedAffixMsa` need name no
part of speech -- the rest land in the junk drawer.

Accounting checks out end to end: 61 entries reachable through the POS tree
+ 7 junk = 68 total, nothing missing.

## Ejagham Full GT-Test is empty, and that is expected

Measured 2026-08-20: **0 lexical entries**. It is the throwaway TARGET of the
`Ejagham Mini -> Ejagham Full GT-Test` pair and is restored blank between runs,
so its contents are a function of which transfer last ran. No sibling carries
the anchored state either:

| Project | entries | affixes | junk no_pos |
|---|---|---|---|
| `Ejagham Full` | 4304 | 20 | 1 |
| `Ejagham Mini` | 252 | 88 | 5 |
| `Ejagham Full GT-Test` | 0 | 0 | 0 |
| *contract anchor* | -- | *33* | *1* |

Those 11 tests now **skip with the re-anchoring recipe**, on the same reasoning
as the T024 live block in `test_object_census.py`, which self-skips when its
sources no longer match their recorded digests: a fixed figure that no longer
describes the file cannot be asserted against it. Re-anchoring is flagged in
the skip message as a deliberate act -- re-run the transfer, re-measure, and
update `specs/008-affix-pos-picker/contracts/pos-grouped-inventory.md` **in the
same change**, or the two diverge silently.

`Esperanto` is a stable read-only reference, so its 20 anchors run for real.

## Sweep

`grep -rn "import flexlibs"` found the identical opener in
`tests/integration/test_phonology_live.py:44` and
`test_rules_live.py:55`. In both it is **dead** -- defined but never called,
because every fixture in those modules `pytest.skip`s first. Fixed anyway
rather than left armed for whoever wires those fixtures up, since the failure
mode is silent. No live `import flexlibs` remains anywhere under `tests/`,
`src/` or `debug/`.

## Verification

* `test_affix_pos_picker_live.py`: **29 skipped (never executed) -> 20 passed,
  11 skipped, 0 failed**.
* Full suite: **25 failed -> 0 failed** (3663 passed, 154 skipped, 14 xfailed,
  14 xpassed).
* `_require_readable` verified to fire against a Cache-less handle.
* All three touched files parse.

Every live open in this work was read-only. Nothing was written to `Esperanto`,
`Ejagham Full`, `Ejagham Mini` or `Ejagham Full GT-Test`.
