# Cycle 14 -- the gross-basis CmPossibility question

**Tree:** `GramTrans-038-transfer-fidelity-gaps`, HEAD `6811894` (read-only this
cycle -- `Lib/census.py`, `Lib/models.py`, `census_cli.py` are another
programmer's live edit surface; every line/function cited below is quoted as
it stands at that commit and nothing here changes it).

**TL;DR of the recommendation (see part c for the full case):** flip
`starter_subtraction_basis` away from `baseline_gross` when the T048d audit
proves `destination_only == 0` (every destination GUID of the class is found
in the source -- a strictly stronger, zero-ambiguity trigger than the existing
"narrowed difference >= 0" test), and let the already-landed T081
owning-list rulings do the rest. This closes ejagham's row to exactly 0 using
only mechanisms that exist today. It does **not** close ngoreme's or fully
close mbugwe's -- and the reason it can't is itself the finding for part (e).

---

## (a) How `unexplained_shortfall` is computed, and what P5 reads

The chain, cited at tree+HEAD:

1. `census_cli.py:2412-2432` -- the row's basis-selection `else` branch. When
   the T048d audit narrows the shortfall but the narrowed figure is still
   negative (`audit_resolves` is False), the code takes the **gross** branch:
   `basis = "baseline_gross"` and `starter_excluded = baseline_count` (line
   2414), and the narrowing is written **only** into `notes` (2415-2432) --
   never into a field any predicate reads.
2. `census_cli.py:2449-2459` builds `models.ClassCensusRow(... difference=
   destination_count - starter_excluded - source_count ...)`. On the gross
   branch this is `destination_count_total - baseline_count - source_count`,
   i.e. the full starter baseline is subtracted regardless of how much of it
   the audit actually corroborated.
3. `Lib/census.py:3105` -- `shortfall, surplus = unexplained_counts(
   row.difference, lines)`, then `census.py:3109` writes
   `block["unexplained_shortfall"] = shortfall` into the artifact. The formula
   (`census.py:2872-2884`) is `max(0, -difference) - sum(shortfall lines)`; it
   takes `row.difference` as given and has no basis awareness of its own.
4. **P5's read**, `Lib/census.py:4729` (`_phase_5`) through `4761-4768`:
   ```python
   if (int(row.get("unexplained_shortfall", 0) or 0)
           or int(row.get("unexplained_surplus", 0) or 0)):
       failures.append("P5: " + _row_label(row) + " still has unexplained " ...)
   ```
   This reads the artifact field directly. `_phase_5` never calls
   `census.is_gross_basis_row`, never reads `starter_subtraction_basis`, and
   never reads `notes`. The row-level pass predicate `row_passes`
   (`census.py:4380-4398`) does exactly the same thing, same field, same
   absence of a basis check.
5. **What `is_gross_basis_row` (`census.py:4085-4131`) actually gates**:
   `gross_basis_suppressions` (`census.py:4157-4172`) and, through it,
   `recompute_verdict`/`stamp_verdict` -- the **artifact-level** `verdict`
   field only (`census.py:4304-4327`, `4348-4370`). That is the mechanism
   contract 5.2 describes as "the run verdict only."

So the "discard into a note" at step 1 and the "gate reads the raw figure" at
step 4 are two different code paths reading two different fields
(`notes` vs `unexplained_shortfall`) that happen to derive from the same
underlying arithmetic. There is no bug in the sense of a broken formula --
`unexplained_shortfall` is exactly `max(0, -difference)` as designed. The gap
is that **the gross `difference` itself is the wrong number to have fed it**,
and 5.2's cap was written to compensate for that at the run-verdict layer only,
by design (quoted in full in part b, route 1).

Verified against the artifact, not assumed: `census-038-t131-ejagham.json`'s
`CmPossibility` row carries `"difference": -308`, `"unexplained_shortfall":
308`, `"accounted_for": []`, `"starter_subtraction_basis": "baseline_gross"`,
and a `notes` entry stating the audit narrows the same row to "AT MOST 6" --
the note and the gating field disagree by 302, and only the gating field is
read by P5.

---

## (b) Three candidate routes, measured

All three numbers below are re-derived from the actual snapshots, not copied
from the task's opening figures (which the task itself flagged as unverified).
**Correction found in verification:** the T048d audit's *narrowed* figure is
**not** close to `difference_raw` on all three pairs -- it coincides with it
on ejagham and is close on mbugwe, but is wildly different on ngoreme. This
matters for every route below.

| pair | source | dest_total | baseline | `difference` (gross) | `difference_raw` | audited (T048d) | `destination_only` = baseline − audited | narrowed (audited) shortfall |
|---|---|---|---|---|---|---|---|---|
| ejagham | 308 | 302 | 302 | −308 | **−6** | 302 | **0** | 6 |
| ngoreme | 398 | 303 | 302 | −397 | **−95** | **19** | **283** | **378** |
| mbugwe | 338 | 305 | 302 | −335 | **−33** | 300 | **2** | 35 |

(Read directly from `notes` in `census-038-t131-ejagham.json`,
`census-038-t131-ngoreme.json`, `census-038-t133-mbugwe.json`.)

Ngoreme's audit only GUID-proves 19 of the 302 baseline objects -- its
narrowed ceiling (378) is *worse* than the naive floor (95), not close to it.
This is very likely the identity audit's known blind spot: `census.py:2276-2296`
(`starter_matched_lower_bound`) counts only GUID coincidence between
`destination_guids` and `source_guids`; an object legitimately matched by
**natural key** (FR-002/FR-006) keeps its own pre-existing destination GUID,
which will *not* appear in the source's GUID set, and is counted as a
`destination_only` orphan even though it was never lost. Ejagham and mbugwe's
near-zero `destination_only` says their CmPossibility population was matched
almost entirely by identity; ngoreme's 283 says the opposite, or that
something else is wrong with that pair's list. Either way this is squarely a
"needs t134" finding -- see part (e).

**A first fact that kills two intuitive routes before they're written down:**
no accounted-for line, of any size, can close this row by itself. The row's
`difference` on the gross basis already has the full 302-object baseline
subtracted into it by construction (`destination_count_net = destination_total
− baseline_count`); `unexplained_shortfall = max(0, -difference) −
accounted`. To reach 0, `accounted` would have to reach `baseline_count +
true_loss` (≈308 for ejagham), not `true_loss` (6) -- an accounted-for line
sized at the true loss only gets the row from 308 down to ~302, nowhere near
matched. **Only a change to `starter_excluded` (i.e. the *basis*) can remove
the phantom 302-unit subtraction; accounted-for lines are the wrong tool for
that job, no matter which reason token backs them.** This constrains every
route below.

### Route 1 -- teach P5/`row_passes` to read a basis-aware quantity

**Change, one sentence:** `_phase_5` and `row_passes` check
`census.is_gross_basis_row(row)` and treat a gross-basis row's shortfall as
non-failing, mirroring the run-verdict cap.

**Contradicts, verbatim** (`contracts/fidelity-census.md` 5.2):
> The cap is also the **run** verdict only -- `row_passes` and
> `evaluate_phase` are untouched, so a phase cannot declare itself done on
> gross-basis arithmetic.

This is not a clause this route "amends" -- it is the clause this route
deletes. It would have to be struck from the contract, not reinterpreted.

**Measured effect:** all three CmPossibility rows pass P5 immediately (308,
397, 335 → all read as non-failing). So does **every other** `baseline_gross`
row in the artifact with a non-zero shortfall, on every phase, forever -- this
is a global predicate change, not a per-row one.

**How it could be wrong:** a class with **zero** real matching -- the engine
dropped every single object of some class and the destination shows only
starter content, no run report, no audit -- is *also* `baseline_gross` with
no other evidence. Route 1 cannot distinguish "302 objects over-subtracted
because they really did match" from "0 objects match because the transfer is
broken." That is precisely the asymmetry 5.2's authors named when they wrote
the sentence being deleted, and precisely the asymmetry that made T048d worth
building in the first place (an audit that can tell those two cases apart).
Widest possible route; recommend against.

### Route 2 -- an accounted-for line sized by the T048d audit's `audited` bound

**Change, one sentence:** in the unresolved branch (`census_cli.py:2412`),
also emit `AccountedLine(reason=<token>, count=audited, direction=
"shortfall", ...)`, landing `unexplained_shortfall` at exactly the narrowed
figure (308→6, 397→378, 335→35 -- confirmed algebraically: crediting
`audited` objects off `max(0, -difference)` reproduces the note's "AT MOST"
number exactly, since `narrowed = destination_total − destination_only −
source = destination_total − (baseline − audited) − source`, and
`max(0,-difference) − audited = (destination_total − baseline − source) +
audited = destination_total − (baseline − audited) − source`, the same
expression).

**Which token, and is it admissible under R-1/R-2 (asked explicitly):**

- `STARTER_CONTENT` is documented in the reason table (fidelity-census.md
  7.1) as **surplus**-direction only ("Explained by the new-project starter
  inventory... surplus"). This row's problem is a shortfall, not a surplus --
  using this token here is not a widening of its use, it is a *misuse* of its
  documented meaning: the claim isn't "the destination has extra starter
  objects beyond what the source needed," it's the opposite, "some starter
  objects were wrongly charged as loss." `AccountedLine.__post_init__`
  (`census.py:2736-2781`) does not enforce reason/direction pairing at
  construction, so nothing *stops* this token/direction combination from
  being built -- but nothing in R-1/R-2 makes it *true*, either; it would
  validate while asserting something the reason table says it doesn't mean.
- The semantically honest token is `MATCHED_EXISTING_IDENTITY` ("The source
  object matched a destination object by GUID... Not a loss" -- shortfall).
  But it is **not** in `REASONS_NOT_REQUIRING_REPORT_REF` (only
  `STARTER_CONTENT`, `ABSENT_BY_CONSTRUCTION`, `OUT_OF_SCOPE_CLASS`,
  `GOVERNED_BY_OTHER_FEATURE` are R-1-exempt). T048d's audit is a **live GUID
  read taken during the census**, not run-report content -- there is no
  `report_ref` to attach, so `AccountedLine.__post_init__` (`census.py:2765-
  2772`) raises `CensusError` at construction. **A `MATCHED_EXISTING_IDENTITY`
  line sized by the audit cannot be built at all under the current R-1.**
- The only way to make Route 2 constructible without misusing an existing
  token is a **brand-new** reason token (e.g. `MATCHED_BY_IDENTITY_AUDIT`),
  added to the closed 18-token `REASON_TOKENS` enum (a schema change --
  `census-artifact.schema.json`'s `accountedLine.reason` enum is closed) *and*
  added to the tiny `REASONS_NOT_REQUIRING_REPORT_REF` set. That is a bigger
  surface than either other route touches: a new enum member plus a new
  report_ref exemption is exactly the shape of thing 7.1 was written to
  forbid ("there is deliberately no `UNEXPLAINED` token and no `OTHER` token
  ... unexplained is the absence of a line and cannot be laundered into
  one") -- a report_ref-exempt token backed only by an internal computation
  is one step from that.

**Measured effect if built (any of the three ways):** identical numbers to
the narrowing table above -- 308→6, 397→378, 335→35.

**How it could be wrong:** the `audited` count is a **lower bound**, and the
row's own docstring (`census.py:2267-2296`) states the one residue it does not
close ("a run that deleted one starter of a class AND created one object of
the same class... lets the bound overstate by one"). Baking a lower bound into
a permanent `accounted_for` line converts "at most this much is lost" into "of
this class, N are matched, full stop" -- silent rather than advisory, which is
the reverse of T023c's rule ("a capped number is never silent"). On ngoreme
specifically it would enshrine 19 as "the matched count" when the true count
is almost certainly much higher (natural-key blind spot, see above) -- turning
a weak audit into a strong-looking accounted-for fact.

### Route 3 -- fix `accounted_for_owning_lists`'s `room` ceiling

**Change, one sentence:** compute the shared `room` for per-list (and
class-level) shortfall claims from something narrower than the gross
`difference`.

This route is analysed fully in part (d) because it turns out **not** to be a
route to closing the row at all (per the "first fact" above -- accounted-for
lines, however capped, cannot cancel the phantom baseline subtraction). It is,
however, a real and currently-unexploited **R-2 weakness** worth fixing on its
own merits regardless of which of the other two routes is chosen -- see (d)
and the recommendation's lock 1.

---

## (c) Recommendation, and its two locks

**Recommendation: extend the *existing* T048d basis-reassignment mechanism
(`census_cli.py`'s `audit_resolves` branch, currently `narrowed >= 0`) to a
second, independently-conclusive trigger: `destination_only == 0`** -- i.e.
`len(set(destination_guids) - set(source_guids)) == 0` for the class, meaning
**every single destination object's GUID is provably present in the source**.
When that holds, set `basis = "baseline_matched"` and
`starter_matched_to_source = audited` exactly as the existing resolved branch
already does, even though the resulting `difference` is still negative.

Why this is the least-widening of the three, and why it is not Route 1 or a
variant of Route 2:

- It touches **zero** gate predicates. `_phase_5` and `row_passes` are
  unchanged, unread, untouched -- literally satisfying 5.2's clause rather
  than confronting it. The row simply stops being `baseline_gross`, and every
  downstream reader (P5, `row_passes`, the run-verdict cap) does exactly what
  it already does for any `baseline_matched` row.
- It introduces **no new reason token, no schema change, no report_ref
  exemption**. It reuses the field (`starter_matched_to_source`) and the
  basis label (`baseline_matched`) the artifact already has a defined meaning
  for.
- It is *stricter* than the audit's own existing threshold, not looser: today
  the code trusts `audited` completely (flips basis, no further scrutiny)
  whenever `narrowed >= 0`; this proposal trusts it under a *different*,
  narrower condition (`destination_only == 0`) precisely because `narrowed >=
  0` and "fully corroborated" turn out to be different properties --
  ejagham's audit is total corroboration (`destination_only = 0`) yet
  `narrowed = -6 < 0`, so today's rule leaves the *strongest* evidence on the
  table while mbugwe (`destination_only = 2`, `narrowed = -35 < 0`) is
  almost as strong and also left out. The zero-orphan trigger is the T110
  carve-out's own standard applied one level down: T110 requires "a
  `starter_baseline_count` that is an integer 0 ... requiring the positive
  corroboration rather than inferring it from key presence" before exempting
  a row from the cap; `destination_only == 0` is the identical shape of
  claim -- a **positive, GUID-proven zero**, not an absence -- applied to
  "no starter object of this class went unaccounted for," rather than to "the
  baseline itself was empty."
- It does not resurrect the exact bug T048d's own docstring warns against
  (promoting an *unresolved* interval to a fact): `destination_only == 0` is
  not an unresolved interval, it is the strongest possible audit outcome
  short of full resolution -- literally the same evidence quality the code
  already trusts when it happens to also make `narrowed >= 0`.

**What it actually does to the three pairs, worked through the arithmetic
(no new code executed -- this is `unmatched_starter`/`net_destination_count`/
`signed_difference` applied by hand to the measured numbers above), combined
with the *already-landed* T081 owning-list rulings (`census_cli.py:2541-2547`,
`OWNING_LIST_RULINGS` in `Lib/models.py:1594-1644`):

- **Ejagham**: `destination_only = 0` → basis flips. `unmatched_starter = 302
  − 302 = 0`; `destination_count_net = 302`; `difference = 302 − 308 = −6`.
  The already-ruled `LangProject.GenreList` shortfall for this pair is
  exactly 6 (measured directly: `recensus-038-t131-ejagham.json`'s
  `t122_per_owning_list`, `GenreList: source=35, dest=29`, and it is the
  **only** non-zero list on this pair -- every other of the 17 owning lists
  balances exactly). `accounted_for_owning_lists` claims `min(6, room=6) = 6`.
  `unexplained_shortfall = max(0,6) − 6 = 0`. **The row reaches MATCHED-basis,
  fully accounted, zero unexplained -- closes cleanly, using only mechanisms
  that already exist and are already committed.**
- **Mbugwe**: `destination_only = 2`, so the strict `== 0` trigger as stated
  **does not fire**; the row stays `baseline_gross`. Two honest options: (i)
  leave it gross this cycle (least-widening, but doesn't close it), or (ii) if
  a live re-measurement confirms the 2 orphaned destination objects are
  something benign and nameable (see part e) rather than genuinely-lost
  starter content, widen the trigger by exactly that corroborated amount. Do
  not guess which from an offline reading -- see (e).
- **Ngoreme**: `destination_only = 283` -- nowhere near the trigger, correctly
  stays gross and advisory. Even applying the *unresolved* audited figure
  (378) plus every ruled list (126) only reaches `unexplained_shortfall =
  378 − 126 = 252`. This row is not closeable from any of the three routes
  with the evidence in hand.

**Two locks, T109/T081-style, both at module scope so a `-k` selection cannot
skip them:**

1. **Import-time disjointness lock**: assert, at `Lib/census.py` module scope
   beside the existing T109/T081 locks, that `OWNING_LIST_CLASSES`
   (`CmPossibility`, `LexEntryType`, `LexEntryInflType` -- `census.py:2513-
   2514`) is disjoint from both `RULED_RESIDUE_CLASSES` and
   `GOVERNED_BY_OTHER_FEATURE_CLASSES`. Today that separation is asserted only
   in prose (`cmpossibility-list-rulings.md` 5: "CmPossibility is NOT a
   roster problem and must not be made one") -- nothing in the executable
   locks (`census.py:4472-4494`, T109; `census.py:4536-4562`, T081) forbids
   `CmPossibility` from being added to either class-keyed roster, and if it
   ever were, `accounted_for_governed_class` (`census_cli.py:1899-1900,1934`)
   claims `count = room` with **no cap at all**, and `accounted_for_ruled_
   residue` (`census_cli.py:1993`) claims `room if max_claim is None else
   min(room, max_claim)` -- an open-ended (`max_claim=None`) entry claims the
   **full** `room`. On a gross-basis row `room = -difference`, i.e. up to
   397/335/308 -- the exact R-2 failure mode named in part (d). This is
   currently prevented by nobody adding such an entry, which is exactly the
   "rule a `-k` selection can skip past" this feature's own T109/T081 doc
   comments warn about for the other two rosters.
2. **Emptying-the-mechanism restores the artifact byte-for-byte**: a test
   (mirroring `tests/unit/test_038_t081_owning_lists.py::
   test_emptying_the_roster_emits_nothing`) that disables the new
   `destination_only == 0` trigger (monkeypatch it back to the old
   `narrowed >= 0` condition, or feed a destination_only of 1) and asserts the
   ejagham/ngoreme/mbugwe artifacts are byte-identical to today's -- proving
   the new trigger is strictly additive and inert unless its precondition is
   met, the same proof obligation T081's roster tests already discharge for
   the owning-list roster.

---

## (d) The per-list lines and R-2 -- with the code, not an opinion

`accounted_for_owning_lists(object_class, difference, ...)` is called at
`census_cli.py:2541` with **`row.difference`** (the gross, baseline-inflated
figure -- `-308`/`-397`/`-335`), not `difference_raw` and not the audited
narrowing:

```
census_cli.py:2541-2542
    lines = lines + accounted_for_owning_lists(
        entry.object_class, row.difference, per_list, lines, notes)
```

Inside, `census_cli.py:2175-2176`:
```
    claimed = census.accounted_in_direction(existing, "shortfall")
    room = -difference - claimed
```
so `room` is `308`/`397`/`335` minus whatever class-level lines already
claimed (currently 0 for CmPossibility, since it carries no
`GOVERNED_BY_OTHER_FEATURE`/`RULED_RESIDUE` entry).

**For the per-list lines *themselves*, this is not exploitable today**: each
line's count is `min(short, room)` (`census_cli.py:2107`) where `short` is a
**live re-measurement** (`source_count − destination_count`) for that
specific owning list, recomputed fresh every run from `_merge_owning_lists`
(`census_cli.py:2022-2043`) -- not a static document-asserted cap. Because
`OWNING_LIST_CLASSES` (`census.py:2513`) partitions the class exactly
(`count_by_owning_list`'s own docstring, `census.py:2578-2580`: "the per-list
counts therefore SUM to the class row's own count"), summing several
individually-true per-list shortfalls can never claim an object that wasn't
really missing from that specific list -- there is no shared, scarce
resource for two lines to double-claim. Measured: ejagham's ruled-list sum is
6 (all of it, from `GenreList`), well under its true room; ngoreme's is 126,
mbugwe's is 31 -- all comfortably under the (inflated) room ceilings of
397/335, so no over-claim is *currently* happening.

**The R-2 failure mode is real, but it lives one level up, in the two
class-level siblings, and it is unconditional there:**

- `accounted_for_governed_class` (`census_cli.py:1899-1900, 1934`):
  ```
  room = -difference - census.accounted_in_direction(existing, "shortfall")
  ...
  return (census.AccountedLine(
      reason=GOVERNED_BY_OTHER_FEATURE_TOKEN, count=room, ...
  ```
  There is **no `max_claim` at all** for this roster (`GOVERNED_BY_OTHER_
  FEATURE_CLASSES` is a 2-tuple, `(owner, reason)` -- `census.py:107`). If
  `CmPossibility` ever acquired an entry here, the line claims the **entire**
  room, i.e. the entire gross-inflated shortfall, in one shot.
- `accounted_for_ruled_residue` (`census_cli.py:1993`):
  ```
  count = room if max_claim is None else min(room, max_claim)
  ```
  An entry with `max_claim=None` behaves identically to the governed case.

And the runtime R-2 validator that is supposed to catch over-claiming reads
the **same** inflated number it was capped by: `Lib/census.py:3909-3920`
checks `claimed = _line_sum(row, direction); if claimed > room:` where `room`
there is `max(0, -difference)` -- literally `row.get("difference")` again
(`census.py:3843, 3854-3855` confirm `difference` is read straight off the
row, no basis adjustment). **The cap and the auditor share one corrupted
number by construction, so no discrepancy between "claimed" and "room" can
ever be observed on a gross-basis row, no matter how large the claim.** This
is R-2's exact failure mode as stated in the task: over-accounting is defined
relative to `difference`, and `difference` is precisely the quantity 5.2
already admits can be wrong by the whole starter baseline.

Today this is inert for `CmPossibility` only because (a) it holds no entry in
either class-keyed roster and (b) the one mechanism that *is* wired for it
(owning-list) happens to be self-limiting by construction. Lock 1 in part (c)
converts (a) from a convention into an enforced invariant, closing the gap
before a future roster edit opens it.

---

## (e) What cannot be settled offline, and needs the t134 live re-census

1. **Ngoreme's identity-audit weakness (19/302 matched) is unexplained.**
   Working hypothesis in this memo (natural-key matches don't preserve the
   destination's pre-existing GUID against the source's, so
   `starter_matched_lower_bound` counts them as orphans) is plausible given
   the magnitude, but it is a hypothesis, not a measurement. If true, the true
   ngoreme shortfall is much closer to the 95-object naive floor than to the
   378-object audited ceiling, and the row's true health is being
   systematically understated by more than 250 objects. This needs either (a)
   a natural-key-aware variant of the audit for this run, or (b) reading the
   run report's per-class natural-key tally (`match_basis`) for CmPossibility
   if one exists, to corroborate or refute the hypothesis. Nothing offline can
   distinguish "the audit is blind to real matches" from "ngoreme genuinely
   lost 283 starter CmPossibility objects."
2. **Mbugwe's 2-object `destination_only` orphans -- benign new creations, or
   real unmatched starter content?** If they are objects the engine created
   fresh (with new, non-source GUIDs, e.g. by some default-content path),
   `destination_only == 0` was in fact false only because of objects that
   were never starter content to begin with, and the trigger in part (c)
   should probably be phrased against `destination_only` restricted to the
   **starter-eligible** subset rather than the whole class -- a real
   refinement that needs live provenance data (creation timestamps / a
   `run_report`'s `created_new` tally for this class) this memo does not
   have.
3. **A reconciliation gap in the artifacts on hand for mbugwe.** The
   per-owning-list diagnostic (`recensus-038-t131-mbugwe.json` and the
   identically-valued `recensus-038-t133-mbugwe.json`) sums to
   `source_sum=335`, `dest_sum=305`, net `-30` -- but the **class row** for
   the matching pin (`census-038-t133-mbugwe.json`) reports `source_count=
   338`, `difference_raw=-33`. That is a 3-object gap on the source side this
   memo cannot place (an unresolved `"(no owning list)"` bucket the stored
   diagnostic doesn't show, or a genuinely stale per-list pin). The module
   header comment at `census.py:2506-2508` itself claims the per-list deltas
   "reconcile to `difference_raw` EXACTLY on all three sanctioned pairs (-6 /
   -96 / -33)" -- note that figure for ngoreme (-96) is *also* off by one
   from the current live `-95` (almost certainly explained by the
   `MoMorphData.ProdRestrict` fix landing since that comment was written,
   since this memo's ngoreme dump shows `ProdRestrict` now balanced at 0
   where the `OWNING_LIST_RULINGS` comment's own historical note says it was
   `-1`). **Neither of these staleness questions can be resolved by reading
   stored snapshots of different vintages against each other** -- this memo
   already tripped over exactly that trap once (see the note in part (b)
   about verifying rather than trusting the task's opening figures) and a
   fresh, single t134 run against all three pairs is the only way to get a
   self-consistent set of numbers to design the final threshold against.
4. **Whether the owning-list partition is complete for all three pairs
   under the *current* code** (zero residual in `OWNING_LIST_UNRESOLVED`,
   `census.py:2521`). If any pair leaves objects unattributed to a list, the
   sum of ruled-list claims can never reach the row's true total no matter
   how the basis is fixed, and the recommendation's "ejagham closes cleanly"
   result should be re-verified against a live run rather than the stored
   `t131` snapshot before it is treated as settled.
