# Contract: Verdict Identity, Severity Ordering, and Exit Codes

**Feature**: `035-fullsweep-fidelity` | Source: spec.md Section G (FR-110..FR-114),
research.md D-04.

Three separate things, deliberately not conflated: the machine token the artifact
stores and tests assert on, the human label the console and report print, and the
process exit code. A fourth, the severity ordering, is distinct from all three.

## The ten verdicts

| Machine token | Human label | Exit code | Success? |
|---|---|---|---|
| `CLEAN_PASS` | `Clean pass` | 0 | yes |
| `PASS_WITH_ALLOWLIST` | `Pass with allowlist` | 0 | yes |
| `UNEXPLAINED_LOSS` | `Unexplained loss` | 1 | no |
| `NON_IDEMPOTENT` | `Non-idempotent` | 2 | no |
| `COVERAGE_REDUCED` | `Coverage reduced` | 3 | no |
| `VACUOUS` | `Vacuous` | 4 | no |
| `HARNESS_ERROR` | `Harness error` | 5 | no |
| `PREFLIGHT_MISMATCH` | `Preflight mismatch` | 6 | no |
| `INCOMPLETE` | `Incomplete` | 7 | no |
| `ALLOWLIST_INVALID` | `Allowlist invalid` | 8 | no |

Exactly two verdicts report success (FR-111). Every other verdict reports a
DISTINCT non-success status; collapsing them onto one non-zero code is forbidden
(FR-111, FR-112).

## Assignment rules (FR-110: exactly one per project run)

| Verdict | Assigned when |
|---|---|
| `CLEAN_PASS` | Zero loss, zero extras, all fifteen guards `pass`, no allowlist entry consumed. |
| `PASS_WITH_ALLOWLIST` | As clean pass, but one or more losses each matched to a VALID allowlist entry within its cap. |
| `UNEXPLAINED_LOSS` | `TOTAL-ACCOUNTING`, `PLAN-CONSERVATION`, `NO-EXTRA`, or `NO-ENGINE-BUG-AS-LOSS` failed; or a loss with no matching allowlist entry; or a count over an entry's cap. |
| `NON_IDEMPOTENT` | `IDEMPOTENCY-IN-WRITTEN-CLASSES` failed. |
| `COVERAGE_REDUCED` | `CATEGORY-COVERAGE` failed - any excluded category, any unmeasured enabled category. |
| `VACUOUS` | `BASELINE-DELTA` or `COMPARISONS-PERFORMED` failed, OR any guard is `not-evaluated`. |
| `HARNESS_ERROR` | `ACCESSOR-INTEGRITY`, `NO-TRUNCATION`, or `CLEAN-CLOSE` failed; or any accessor/restore/close/artifact-write failure; or an unhandled exception. |
| `PREFLIGHT_MISMATCH` | The capability preflight found a difference from the pinned expectation. |
| `INCOMPLETE` | `ARTIFACT-INTEGRITY` failed - any corpus project not run, skipped, or without an artifact. |
| `ALLOWLIST_INVALID` | An allowlist entry is malformed, expired, unowned, capless, over-broad, or stale. |

The verdict formerly used to mean "loss occurred but is not itself a failure"
(`DROPS_REPORTED`) is RETIRED. There MUST be no verdict meaning "loss reported,
review advisable, exit success" (FR-112).

## Published severity ordering (FR-111, FR-113)

Most severe first. This ordering is NOT the exit-code integer and MUST NOT be
derived from it.

```
HARNESS_ERROR
PREFLIGHT_MISMATCH
ALLOWLIST_INVALID
VACUOUS
INCOMPLETE
UNEXPLAINED_LOSS
NON_IDEMPOTENT
COVERAGE_REDUCED
PASS_WITH_ALLOWLIST
CLEAN_PASS
```

Rationale (D-04): "the measurement cannot be trusted" ranks above "the
measurement is trustworthy and reports loss". An `UNEXPLAINED_LOSS` report is
actionable information; a `HARNESS_ERROR`, `PREFLIGHT_MISMATCH`,
`ALLOWLIST_INVALID` or `VACUOUS` run means the loss number in front of the
operator means nothing yet. Sorting by exit code would rank `UNEXPLAINED_LOSS`
above `HARNESS_ERROR` and send an operator chasing a figure a broken instrument
produced.

## Corpus aggregation

- Corpus status = the single MOST SEVERE per-project verdict under the ordering
  above. Never the last project run, never the first (FR-113).
- If ANY project's verdict is `INCOMPLETE`, the corpus run MUST NOT report
  success even if every project that did run was a clean pass (FR-114).
- The corpus process exit code is the exit code of that most-severe verdict.

## Test surface

Tests assert on the machine token, never on the human label and never on the
message text (FR-176 bans distinguishing failure categories by matching message
text). `tests/unit/test_035_verdict_order.py` MUST assert: the ten tokens exist
and are distinct; the exit-code map is total and injective over non-success
verdicts; the severity ordering is a total ordering covering exactly the ten
tokens; and corpus aggregation returns the maximum under that ordering.
