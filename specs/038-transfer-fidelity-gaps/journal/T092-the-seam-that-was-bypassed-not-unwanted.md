# T092 — the seam that was bypassed, not unwanted

**Closed** 2026-08-22. **Successor filed**: T105.

## What T092 asked

T031 landed `preview.plan_match_decision` under the recorded decision that
*the plan decides and the report tells*. T091's trace then measured that its
only importer is `tests/unit/test_038_plan_match_decision.py`. T092 framed the
consequence sharply, and correctly: **"a seam with no callers and no plan to
acquire them is dead code that reads as coverage"** — structurally identical to
**Defect G2**, where `closure.py`'s only importer was its own unit test. The
task's instruction was to land T091 first and then *decide on the evidence*
whether the seam earns its callers or should be deleted.

## The measurement

The zero-callers half is **confirmed**: no production path calls
`plan_match_decision`.

The framing's implied conclusion is **wrong**, and the evidence is what
reverses it. The question the seam answers is being answered **four more
times, in production**, by open-coded calls straight to
`matcher.resolve_match`:

| site (`Lib/categories.py`) | candidate scope | deviation from the seam |
|---|---|---|
| `_match_collection_child` (T044) | the owning collection — deliberate | receives `ws_handles`/`source_ws_handles` **already resolved**; adds a GUID-only fallback for an unkeyable child |
| `_resolve_target_pos_by_natural_key` (T032) | recursive `_iter_pos` walk, **not** the registered scope fn | the only site that reports `parent_divergence`; hardcodes `"PartOfSpeech"` |
| `_process_referent_by_natural_key` | `NATURAL_KEY_SCOPE_FNS[binding.scope_fn_id]` — **the seam's own branch, line for line** | **drops the seam's `_log.warning`** on an unenumerable scope, and **swallows `NaturalKeyAmbiguityError`** where the seam propagates it |
| `_plan_natural_key_match` | caller-supplied `target_iter` | the only site that builds a `PlannedOverwrite` from the decision |

So the seam is **bypassed, not unwanted**. Its own docblock exists because
"three implementations of one question" is how the two opposite failure modes
038 removes — create-anyway duplicating starter content, resolve-only dropping
the analysis — get reintroduced. The measured count is **four**, and one of the
four has *already* lost the seam's enumeration-failure report and inverted its
ambiguity contract: an ambiguous key reaches the operator at one site and is
silently converted to "unresolved" at the other. Deleting the seam would
**ratify** that divergence rather than end it.

**Decision: the seam earns its callers.** Not by deleting the test — T092
forbade that — and not by a mechanical re-point either.

## Why the routing is T105 and not T092

T092 already said it: routing the plan paths through the seam is a
**live-behaviour change across every category that plans a roster-admitted
class, and needs its own census**. Two further facts sharpen the scope:

- **Only two of the four bypasses can reach the seam at all today.**
  `plan_match_decision` takes a `RunContext` and reads both project handles off
  it. `_match_collection_child` receives handles already resolved and
  `_resolve_target_pos_by_natural_key` takes `target` + `source_handle` —
  neither holds a context. Routing those two needs a **handle-pair entry point
  on the seam**, which is a design decision, not a re-point.
  `_process_referent_by_natural_key` and `_plan_natural_key_match` do hold a
  context and could be routed today.
- **The two reachable sites carry contracts that conflict with the seam's.**
  `_process_referent_by_natural_key`'s ambiguity-swallowing is *argued for* in
  its own docstring ("guessing between two same-named destination phonemes is
  how a rule silently comes to match the wrong segment"), and the seam's
  propagation is argued for in its own ("an ambiguous key is a harness error
  the operator must see"). Both readings are defensible; the routing task has
  to pick one and say which, per site.

That is the same reasoning that kept T089's re-pointing out of a registration
and T092 out of T091 in turn.

## What T092 landed instead: the count stops growing

`tests/unit/test_038_plan_match_decision.py` gains four tests, in the idiom
T094 used for `_resolve_target_pos` — read the tree with `ast`, key by
enclosing function name rather than line number, so a site reachable only with
a live LCM host is still visible and the pin survives edits above it:

- `test_no_new_production_site_bypasses_the_seam` — the set of production
  functions calling `resolve_match` must equal the five named
  (`plan_match_decision` plus the four bypasses). A **new** open-coded call
  fails it; a bypass that *disappears* also fails it, so a routing commit must
  update the list in the same change.
- `test_the_pin_can_see_every_site_t092_measured` — the floor, so an `ast` walk
  that stopped matching cannot make the pin vacuously green. This is the
  failure mode a source-reading test actually has.
- `test_the_seam_still_has_no_production_caller` — the other half of the
  measurement, as an assertion rather than a note, so the day a production path
  *does* call the seam this goes red and forces T105's census to be recorded
  instead of arriving as a silent green.
- `test_only_two_bypasses_can_reach_the_seam_today` — T105's reachable scope. If
  a `RunContext` arrives at one of the other two sites, the routing task just
  got bigger, and this is where that is noticed.

**Verified live, both directions**: 25 passed on the file; then a probe module
adding one open-coded `resolve_match(context, obj)` call under
`src/gramtrans/` turned three of the four red (naming the probe by file and
function) and was removed. A pin that has never been seen to fail is a claim,
not an instrument.

No engine file was touched, so no `lockout` claim on `categories.py` or
`transfer.py` was needed and no census was required.

## The shape, for the running tally

T092 was filed as the **eighth** appearance of this feature's recurring shape —
*something that exists and is read at a level where it cannot do its job*. The
close refines it rather than confirming it: the seam is not read at the wrong
level, it is **not read at all**, while the thing it exists to prevent happens
four times beside it. The nearest relative is not G2 (dead code with a test)
but the **divergence G2's premise describes** — and this is the first instance
in 038 where the correct response to "this abstraction has no callers" was
*keep it and pin the bypasses*, rather than delete it.
