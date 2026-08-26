# T113 — a guard that only looks one way

**Closed** 2026-08-26. Filed by T109, whose derivation from the spec's
Assumptions produced 14 classes where the roster it sat beside held 9 of them.

## What T113 asked

`models.CENSUS_REPORT_ONLY_RESIDUE` decides one word in the console state
column: `report_only` rather than `matched` or `accounted`, for a class this
feature measures, reports and does not undertake. T109 derived a *second*
roster, `CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES`, from `spec.md:372-374` —
"Sense pictures, reversal indexes, and the texts/wordforms path are governed by
their own features" — and landed 14 classes.

Nine of them were on the residue roster. Five were not:

| class | on the governed roster | on the residue roster (pre-T113) |
|---|---|---|
| `Text` | yes | **no** |
| `TextTag` | yes | **no** |
| `ReversalIndex` | yes | **no** |
| `ReversalIndexEntry` | yes | **no** |
| `CmPicture` | yes | **no** |
| `StText`, `StTxtPara`, `Segment`, `CmTranslation`, `PunctuationForm`, the four `Wfi*` | yes | yes |

So one feature's classes were split across two states — `StText` rostered and
the `Text` that **owns** it via `ContentsOA` not — and two of the three named
paths (reversals, sense pictures) had no entry at all.

## The consequence, measured on all three sanctioned pairs

T109's emitter now stamps a `GOVERNED_BY_OTHER_FEATURE` accounting line on
these rows, which takes their `unexplained_shortfall` to 0. That is what makes
the gap visible: with the loss accounted, `report._census_row_tier` no longer
lands the row in the `unexplained` band, so it falls through to `matched` or
`accounted` — one band away from the `report_only` its own path reads.

T078's three committed censuses, with T109's line applied in memory (nothing
re-emitted, nothing written):

| class | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `Text` | `matched` → `report_only` | **`accounted` → `report_only`** | `matched` → `report_only` |
| `TextTag` | `matched` → `report_only` | `matched` → `report_only` | `matched` → `report_only` |
| `ReversalIndex` | `accounted` → `report_only` | `accounted` → `report_only` | `accounted` → `report_only` |
| `ReversalIndexEntry` | `accounted` → `report_only` | `matched` → `report_only` | `matched` → `report_only` |
| `CmPicture` | `matched` → `report_only` | `matched` → `report_only` | `matched` → `report_only` |
| `StText` (control) | `report_only` — unmoved | `report_only` — unmoved | `report_only` — unmoved |

`ReversalIndex` is the sharpest of them: **-2 on all three pairs**, the only
class on any governed path of which that is true, reading as merely
`accounted`. And most of the `matched` readings above are *vacuous* greens —
`TextTag` and `CmPicture` have `source_count` 0 on every sanctioned pair — which
is precisely the inversion T079 built the state for.

## The finding is the BLIND SPOT, not the five names

`report.report_only_roster_defects()` had four checks:

1. `CENSUS_PHASE_GATED_CLASSES` still mirrors the phase predicates.
2. No rostered class is phase-gated.
3. Every entry names both an owner and a reason.
4. No rostered class is one the artifact already excludes from the delta.

Every one of them asks *"is a class wrongly **ON** the roster?"*. Not one could
ask *"is a class **MISSING** from it?"* — so the roster could be silently short
of a path the Assumptions name and the audit returned `()`, which is exactly
what it did.

That is T079's own lock inverted, and the **thirteenth appearance** of this
feature's recurring shape: a guard that covers the direction it was written for
and is structurally blind to the other. (T048b/T048f/T048g/T086 are the
bounding-rule family; T110 is the same shape in the excusing direction.)

Adding the five names without the check would have closed this instance and
left the next path just as free to go missing. **The check is the fix; the five
names are what it found.**

## Check 5, and why its carve-out is guarded too

```
governed ⊆ residue          # the rule
governed ≠ residue          # deliberately NOT equality
```

The converse is **not** required, and that asymmetry is load-bearing. The
phonology family, the Fs* cascade and `CmFile` are report-only under an owner
that names no feature that exists — T079 called that "a claim someone must own
before it can be an accounting line" and T109 kept them off the governed roster
for exactly that reason. Requiring equality would either launder those rows
onto a gate-bearing roster or force them off a display roster where they
belong. `residue - governed` is 14 classes and stays that way.

**The carve-out is itself checked**, because an unguarded carve-out would be
this same defect a second time. Check 4 forbids rostering a class the artifact
already excludes from the delta, so check 5 must exempt one — and an exemption
nothing watches is a way for a governed class to vanish from *both* checks. The
combination is therefore reported in its own right: a class cannot be both
governed-by-another-feature-and-reported and excluded-before-it-is-measured.
Today the two sets are disjoint (`NOT_EVALUATED_CLASS_REASONS` holds
`CmAnthroItem`, `MoForm`, `MoMorphSynAnalysis`), so the branch is exercised by
a test that forges the contradiction rather than by live data.

## The five entries are measured, not asserted

Every residue reason carries its measured figures in (ejagham, ngoreme, mbugwe)
order, read off T078's committed censuses, and a test parses them back out:

| class | measured |
|---|---|
| `Text` | 0, -14, 0 |
| `ReversalIndex` | -2, -2, -2 |
| `ReversalIndexEntry` | -14, 0, 0 |
| `TextTag` | `source_count` 0 on all three — a vacuous 0 → 0 |
| `CmPicture` | `source_count` 0 on all three — a vacuous 0 → 0 |

`TextTag` and `CmPicture` say **in their own reason strings** that they are
vacuous rather than quoting a difference, for the same reason T109 admitted
them as promises: no committed census can measure a class no sanctioned pair
holds. They stay on the roster because dropping the only class the "sense
pictures" clause names would make the derivation unfalsifiable — and because a
green with no code behind it is the exact state `report_only` exists to say out
loud.

`CmFile` stays where T109 put it: on the **residue** roster under "the
media/pictures path -- not 038", and **off** the governed roster. With no
`CmPicture` anywhere on any pair, the 2176 objects `CmFile` and `CmFolder` lose
between them cannot be sense-picture content. A display word is the right home
for that claim; a gate-bearing accounting line is not.

## What did NOT move

**The roster is still gate-inert, now with five more classes on it.** Emptying
it changes not one verdict, exit code, gate failure, `gate_scope`,
`verdict_class` or tally — re-run in T113's own test over `ReversalIndex` (a
real loss) and `CmPicture` (a vacuous green), because five more classes on a
roster that *could* turn a red row green would be five more ways in.

Measured on all three T078 artifacts: verdict `DUPLICATE_IDENTITY`, `passed`
False, before and after. The report-only **block** grows, and nothing else
does:

| pair | pre-T113 (total, differing, agreeing) | post-T113 |
|---|---|---|
| ejagham | 23, 14, 9 | 28, 16, 12 |
| ngoreme | 23, 19, 4 | 28, 21, 7 |
| mbugwe | 23, 17, 6 | 28, 18, 10 |

The agreeing group grows by more than the differing one, which is the group
`report_only_residue_lines` orders first precisely because the console
truncates at 20 rows — the note "the run-report JSON artifact lists all of
them" was already true at 23 and is more true at 28.

No schema bump: `report_only` is a run-report state, not a census-artifact
property, and nothing here emits an artifact field. No new reason token. No
census artifact re-emitted.

## Tests

`tests/unit/test_038_t079_report_only_residue.py` — 12 new tests in
`TestT113TheRosterCannotBeSilentlyShort`, unit 3731 → **3743 passed** / 79
skipped / 14 xfailed. Integration **718 passed** / 75 skipped, unmoved.

The mutation directions that matter, all pinned:

- remove `ReversalIndex` from the residue → check 5 names it;
- empty the residue → check 5 names **all fourteen** governed classes, so the
  check cannot be satisfied by a roster that merely happens to be non-empty;
- reconstruct the pre-T113 roster (23 entries) → **exactly one** defect, naming
  exactly the five. That is the claim T113 makes about the four earlier checks,
  stated as a test: that roster passed every one of them;
- forge the carve-out contradiction → check 5 stays silent about the missing
  class and reports the contradiction instead;
- poison the roster three ways at once → checks 2, 3 and 4 all still fire, so
  check 5 is an addition and not a relaxation.

`tests/integration/test_object_census.py::test_the_roster_is_not_the_report_only_residue_and_says_so`
is **amended, not deleted**. As written it recorded the five as evidence the
two rosters are different sets; T113 re-reads the same five as the gap. The
test's real argument — neither roster is derivable from the other, and a later
hand that collapses them into one list fails here — is unchanged and now rides
on `residue - governed`, which is where it always belonged.
