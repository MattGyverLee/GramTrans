# T031 / T032 / T033 / T037 -- the plan decides, the report tells

**Date**: 2026-08-19
**Branch (code)**: `038-transfer-fidelity-gaps`
**Commits**: `edea030` (T031), `52b0961` (T032/T033), `b6787da` (T037)
**Unit suite**: 2826 passing, **zero net-new failures** against the 27
pre-existing (verified each time by diffing the sorted `FAILED` sets, never by
comparing counts)

Still open in Phase 4: **T034/T035** (`categories.py`) and **T036**
(`transfer.py`), both in flight, then the **T038/T039 census gates**, which
need a live pair and are blocked on the merge described at the end.

---

## T031 -- the match decision is computed once, in the plan

Preview and Move have to agree about which destination object a source object
corresponds to. Before this they agreed by *parallel construction*, and there
were **three** implementations of that one question, not two:

- `preview.py` scanned category-scoped lists (`_target_has_pos_guid` and
  friends);
- `transfer.py` used `_idempotency_guard`, which calls `target.Object(guid)`
  -- a cache lookup that finds objects **regardless of category scoping**, a
  different mechanism from every plan-side scan;
- `categories.py` had its own `_target_has_guid` / `_find_target_obj_by_guid` /
  `_resolve_target_pos`.

The two opposite failure modes 038 exists to remove -- create-anyway
duplicating starter content, resolve-only dropping the analysis -- are exactly
what you get when the plan and the executor answer that question differently.

`preview.plan_match_decision()` now runs both steps and returns the whole
`MatchDecision`; `matcher` owns the ordering and this module owns only the
wiring. `NaturalKeyAmbiguityError` is deliberately allowed to propagate -- an
ambiguous key is a harness error the operator must see, not something to absorb
into a silent miss -- and a destination scope that cannot be enumerated becomes
an **accounted miss** rather than "no candidates, so create".

### The cross-project writing-system bug, caught before it could be written

`resolve_match` took one `ws_handles` mapping. That is right for a
single-project caller and for the T029/T030 unit tests, and **wrong for a
transfer**. A writing-system handle is a per-project integer, so reading a
destination object's name through the *source* project's handle does not raise
-- it returns `None`. Every candidate key would have evaluated to "this object
has no key", the natural-key step would have matched nothing at all, and the
run would have looked like a clean set of misses rather than a broken
comparison. That is the worst possible failure shape for this feature: it is
indistinguishable from correct behaviour in the report.

`resolve_match` now takes `source_ws_handles=` separately, defaulting to
`ws_handles` so all 100 T029/T030 tests are unchanged. Four tests across two
files pin it from both directions, including the deliberately perverse one that
puts the destination's name under the *source* handle and requires a miss.

### What deliberately gets NO record

`_emit_present_outcome` attaches a `MatchBasisRecord` when the caller names the
class **and** the match really was by GUID or `identity_remap` -- FR-001 treats
a previous run's remap entry as identity, not as a substitution.

It attaches nothing for `match_via="fingerprint"`. `MatchBasis` has three
members and none means "matched by fingerprint". Recording one as IDENTITY
would claim a GUID hit that never happened; recording it as NATURAL_KEY would
corrupt `CategoryReport.identity_substitution`, whose entire purpose is to
count roster-admitted name matches. Absent is the honest answer, and `report.py`
already accounts for it under `matches_unattributed`.

### An import-mode bug this surfaced

`census.py` imported `.models` unconditionally, so it was importable **only**
as part of the `gramtrans.Lib` package, while every sibling module supports
both. That was invisible for exactly as long as nothing in the flat
`site.addsitedir("Lib")` load path reached it -- and it stopped being invisible
the moment `preview.py` gained a module-level dependency on `census`, because
the standalone FlexTools entry module loads `preview` flat. It surfaced as
`ImportError: attempted relative import with no known parent package` in **ten
feature-034 standalone-contract tests, ten files away from the change**.
`census.py` is now dual-mode like the rest.

---

## T032 / T033 -- the 2,088-MSA path

`_resolve_target_pos` was the `None`-returns-and-caller-abandons path that lost
**all 2,088 MSAs**. Two separate defects lived in it.

**T032: it matched by GUID only.** Whether that works is not something a
linguist can see or control. Catalog-sourced categories share GUIDs across
projects (`Noun` is `a8e41fd3-...` in both `Ejagham Mini` and `Mbugwe LizzieHC
practice`); categories created any other way do not (Esperanto's `Noun` is
`e09a4354-...`). census-evidence.md records the consequence exactly: "Ejagham
escaped total loss only by accident: its 5 target POSes happened to be
GUID-identical to the source's", while Ngoreme matched none.

Identity is still first and still short-circuits. The fallback is inert unless
both halves of the basis are present, and returns `None` rather than raising
for every reason a key cannot decide.

**The landing-safety property, and the first test in the new file.**
`src_pos` and `source_handle` are keyword-only and default to `None`, so every
un-swept two-positional caller keeps its exact pre-038 behaviour. The test
proves it the hard way: with the roster admitting the class and a name that
*would* have matched, a two-positional call still returns `None`.

**T033: four of the eight call sites abandoned silently** --
`inflection_classes`, `pos_inflectable_feats`, `slots`, and `affix_templates`
execute actions. The last was the worst because its abandon was **implicit**:
there was no `else`, so an unresolved owner fell past the ~50-line
create-and-wire body to the shared `return None`, leaving nothing to
distinguish "template written" from "template silently discarded".

"Silent" is not an overstatement. `transfer.py` discards every
`execute_action` return value and then increments `leaf_succeeded`
unconditionally -- so the item vanished **and the run counted it a success**.
All four now pass the source category object (without which the key is not
computable at all) and report a `Skip(DEPENDENCY_UNRESOLVED)` through
`context._exec_skips`, reaching the report via `RunReport.extra_skips`. The
reporting helper no-ops when the context carries no skip list rather than
raising: the condition it describes is already a degraded run and must not
become a crash.

The other four sites needed no conversion, and that is recorded so the next
reader does not re-audit them: `resolve_or_create_target_pos` and
`resolve_or_create_inflection_class` already report through `owned.py`'s
`DroppedItemRecord` path, `_resolve_or_none` is the already-converted MSA path,
and `can_create_inflection_class` is a read-only Preview-parity predicate --
which does mean any future change here must be mirrored in it or the documented
CREATE-vs-REPORT parity (G6) breaks.

---

## T037 -- the report could not say "the matcher ran and found nothing"

FR-006 was already satisfied on the **counting** layer.
`_count_substitution` has fed `CategoryReport.identity_substitution` from
`MatchBasis.NATURAL_KEY` since the foundational phase. It was satisfied on
**neither reporting surface**, and the defect was already on record as a live
measurement: on the Ejagham/Ngoreme pair the report carried
`matched_to_source.total == 1806` beside `identity_substituted == 0`, and
nothing in either surface distinguished *"the matcher ran and substituted
nothing"* from *"the matcher never ran"*.

1. The console section was gated on a non-zero count, so a run where everything
   matched by GUID printed **no match-basis line at all**. Silence is the one
   rendering that cannot be read.
2. When substitutions did occur it printed a bare "N total" with no
   denominator. "1" beside 3 matches and "1" beside 1,806 are different
   fidelity claims.
3. The JSON `matched_to_source` block carried no basis split, so a reader had to
   derive it by subtracting a value from another block **that is omitted when
   empty**.

`not_by_natural_key` is deliberately not named `by_identity`: it is a remainder
that includes matches carrying no basis record at all, and naming it after a
basis nothing recorded would manufacture the very claim FR-006 exists to
prevent.

**A second defect found while reading `models.py`.** `PlannedOverwrite` records
natural-key-ness twice -- as the structured `match_basis` and as the
`match_via` string, whose documented legal values include `"natural_key"`, a
value feature 038 itself added. `_count_substitution` read only the record, so
a producer setting just the string would have had its substitution silently
counted as an ordinary match: the report asserting a GUID-strength claim the
matcher never made. There is now a fallback consulted **only** when
`match_basis` is absent and **only** on the overwrite path, so it can neither
contradict nor double-count.

**The `identity_substituted <= matched_total` invariant is structurally safe,
and is now pinned.** It cannot fire from `build_from_plan`, because
`MatchBasisRecord.__post_init__` forbids a non-NONE basis with an empty
`target_guid` -- so every object `_count_substitution` counts also satisfies
`_action_matched_existing`'s `bool(basis.target_guid)` guard. That is
structural, not accidental, and a test now makes a future guard added to one
counter but not the other fail loudly. No `models.py` change was needed.

**Standing note for the remaining producer tasks**: setting
`match_via="natural_key"` without also attaching a `MatchBasisRecord` is now
counted, but the record is what carries `object_class`. Without it the match
lands in `matches_unattributed`, which spoils `matched_class_is_complete` and
blocks the census's `baseline_matched` subtraction basis for every class in the
run. Set both.

---

## Blocking item for T038/T039, recorded now rather than discovered later

**The code worktree is 53 commits behind `main`, and one of them is the
roster.** `matcher.NATURAL_KEY_ROSTER_PATH` resolves relative to the module, so
in the worktree it reads that worktree's copy of
`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json` --
which still has **3 entries**. The six landed on `main` at `d8635d9`.

Consequence: **every natural-key path in the worktree is currently inert at
run time.** That is by design and is why the unit tests build the appended
roster in `tmp_path` rather than reading the shipped file -- but it means the
T038/T039 census gates cannot pass until `main` is merged into the branch. Do
that merge *before* attempting T038, and re-run the unit suite immediately
after, because those 53 commits include at least two that touched `src/`
(`feat(038 T024h)` and `feat(038): live two-mode delta driver`), not only
`specs/`.
