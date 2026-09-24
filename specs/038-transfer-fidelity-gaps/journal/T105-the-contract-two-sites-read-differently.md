# T105 — the contract two sites read differently

**Closed** 2026-08-22. Successor to T092. **No successor filed.**

## What T105 asked

T092 measured that `preview.plan_match_decision` had zero production callers
while the question it answers was answered four more times in `categories.py`
by open-coded `matcher.resolve_match` calls, and kept the seam on that
evidence. T105 was the routing: point the four bypasses through the seam, **or
record per site why not**, with the explicit warning that an unexplained entry
in the approved-site list is how T092's condition returns.

Two constraints came with it. Only two of the four bypasses hold a
`RunContext` and can reach the seam at all. And the two that can hold
**incompatible readings of one contract**: the seam propagates
`NaturalKeyAmbiguityError` because "an ambiguous key is a harness error the
operator must see", while `_process_referent_by_natural_key` swallows it
because "guessing between two same-named destination phonemes is how a rule
silently comes to match the wrong segment". Both readings are argued for in
their own docstrings. T105 required one to be picked, and named, per site.

## Outcome: two routed, two documented

**ROUTED.** `_process_referent_by_natural_key` and `_plan_natural_key_match`,
the two context-bearing sites — exactly the reachable scope T092 pinned. Both
go through a lazy `categories._plan_match_decision` wrapper, the same
cycle-avoiding idiom `_lcm_class_for_category` already uses (`preview` imports
`categories`, so a module-level import would close the cycle).

**NOT ROUTED, DOCUMENTED**, with the reasons written into the seam's docblock
in words rather than left to a commit message:

- `_match_collection_child` (T044). Six of the seven POS-owned collections hold
  classes with **no natural-key binding at all** — `MoInflAffixSlot`,
  `MoInflAffixTemplate`, `FsFeatDefn`, `MoStemName`, `MoInflClass`, and
  `ReferenceFormsOC`, whose target type is `IFsFeatStruc` (verified read-only
  via FLExToolsMCP against `IPartOfSpeech`). Only `SubPossibilitiesOS` carries
  one, and even that slot is *declared* `ICmPossibility` with `PartOfSpeech`
  children at runtime. The seam returns None for an unbound class — correctly,
  that is its documented contract — so routing this site would answer None for
  six collections in seven, its caller would stop matching existing children,
  and run 2 would re-add every child run 1 wrote. **That is the exact SC-008
  re-run defect T044 exists to prevent.**
- `_resolve_target_pos_by_natural_key` (T032). It enumerates with `_iter_pos`,
  i.e. `handle.POS.GetAll(recursive=True)`, which both a live host and the
  host-free fakes answer. The registered scope for `PartOfSpeech` is
  `census.objects_in_class`, which needs a live `SIL.LCModel` repository
  interface and raises `CensusError` without one; through the seam's candidate
  branch that becomes "no candidates", so routing it with the default scope
  would **turn every host-free POS key match into a miss**. It is also the only
  site that reports `parent_divergence`, and its `_resolve_target_pos` entry
  point is a pre-038 API with ten call sites whose 038 parameters are
  keyword-only opt-ins — threading a context in is a sweep, not a re-point.

A **handle-pair entry point on the seam** was the design decision T105 flagged.
Considered and **rejected**: each of those two sites needs the seam to skip two
of the four services it exists to provide (binding lookup, registered-scope
resolution with its warning, per-project handle reading, ambiguity
propagation), which leaves the seam nothing to do but forward its arguments.
Building an entry point to buy that is how an abstraction acquires callers
without acquiring a purpose.

## The ambiguity contract: both readings survive, because they were never the same question

This is the part T105 called "the interesting part", and the resolution is that
the conflict was **mis-stated**. The seam's contract is about what it
**raises**; the call site's is about what it **does with a raise**. The seam
never promised callers must not catch it.

So `_process_referent_by_natural_key` keeps its absorb, and the `except
NaturalKeyAmbiguityError` now sits **visibly at the call site** instead of
being implied by a divergent copy of the seam's body. `_plan_natural_key_match`
propagates, agreeing with the seam, and no `except` was added — a
`PlannedOverwrite` proposes to reuse ONE specific destination object, so an
ambiguous key has no defensible object to name.

The caller's reading wins at the referent leg **on measured grounds, not
taste**: ambiguity in these three classes is the NORMAL condition on real
pairs. T098's re-census of two live pairs found 12 duplicate-name groups / 21
extra objects in `PhNCFeatures` on Ngoreme and 1 / 3 on Ejagham; T043's live
run measured 21 duplicate phoneme names in a single destination. A plan-time
referent walk that propagated would abort whole runs over the common case,
where the leg exists precisely so one rule can skip with a reason while the
rest of the transfer proceeds.

## The census T092 required, and why it was not needed

T092 filed the routing as "a live-behaviour change across every category that
plans a roster-admitted class, needing its own census". **Measured against the
code, the two routed sites needed none** — and that is a finding, not a
shortcut, because it is exactly why they were the routable two:

- `_process_referent_by_natural_key` reproduced the seam's candidate branch
  **line for line**. Same binding lookup, same
  `NATURAL_KEY_SCOPE_FNS[scope_fn_id]`, same handle pair. The `if not
  candidates: return None` early-out it loses is equivalent: the seam calls
  `resolve_match` with `[]`, which returns basis NONE, which the site already
  reads as no match.
- The dropped `[_unwrap_lcm(c) for c in scope(target)]` is a **no-op**, and this
  was checked rather than assumed: the scope fn is
  `census.objects_in_class` → `handle.ObjectsIn(iface)` →
  `iter(repo.AllInstances())` (flexicon `FLExProject.py:3209-3210`), i.e. raw
  LCM objects straight from the repository, never a flexicon wrapper.
- `_plan_natural_key_match` supplies its caller's own enumeration through
  `candidates=`, which is that parameter's purpose, so nothing changes about
  which objects are offered.

**One behaviour is added, deliberately**: the seam's `_log.warning` when the
destination scope cannot be enumerated. That is the drift T092 measured — the
site had copied the seam's body *minus* its report — and recovering it is a
strictly additive report on a path whose answer (None) is unchanged.

## Verification

`tests/unit/test_038_plan_match_decision.py`: **30 passed** (25 → 30). Full
unit suite **3641 passed, 79 skipped, 14 xfailed**; `tests/integration`
**512 passed, 76 skipped**. No live LCM run was performed and none was
required — see above. (Collecting `tests/unit` and `tests/integration` in one
pytest invocation errors on a duplicate `test_038_process_rules.py` basename;
verified pre-existing by reproducing it on the stashed tree.)

The pins were updated, not loosened, and each was **seen to fail** — T092's own
standard, that a pin never observed red is a claim rather than an instrument:

- `_APPROVED_RESOLVE_MATCH_SITES` 5 → 3 entries, each surviving bypass carrying
  its one-line reason; the floor in
  `test_the_pin_can_see_every_site_t092_measured` 5 → 3.
- `test_the_seam_still_has_no_production_caller` **inverted** into
  `test_the_seam_has_exactly_the_callers_t105_routed`: the seam now has
  callers, and *which* is the fact worth pinning. A caller that disappears
  means a routing was undone, which is how T092's condition returns.
- `test_only_two_bypasses_can_reach_the_seam_today` became
  `test_the_unrouted_bypasses_still_hold_no_context` — the recorded reason for
  not routing, as a test, so it expires loudly if a context arrives.
- Five new behavioural tests exercise both routed sites, including each one's
  ambiguity reading and the added warning.

**Probes, all three reverted:**

1. A production module with one open-coded `resolve_match` call plus one seam
   call turned **all four structural pins red**, each naming the probe by file
   and function.
2. Removing the `except NaturalKeyAmbiguityError` from the referent leg turned
   `test_the_referent_leg_absorbs_ambiguity_rather_than_propagating` red with
   the raise itself — precisely the failure T105 warned of, a skip-with-a-reason
   converted into a raised run.
3. Neutering the seam to return None turned **all four** routed behavioural
   tests red, proving they run through the seam rather than a leftover path.

## The shape, for the running tally

Filed as the **twelfth** appearance of this feature's recurring shape —
*something that exists and is read at a level where it cannot do its job* — and
the first where the thing at the wrong level is a **contract two sites hold
incompatible readings of**. The close sharpens that: the two readings were not
incompatible, they were answers to two different questions that a duplicated
implementation had fused into one. The divergence was never the disagreement;
it was that the disagreement had nowhere to be stated. It now has two places —
a raise in the seam and a catch at the caller — and a test on each.
