# T097 -- the fix that was already written

**Date:** 2026-08-24
**Task:** T097 (US2)
**Branch commit:** `2c5d797` on `038-transfer-fidelity-gaps`
**Evidence:** `035-fullsweep-fidelity` at `7011b5b`; the file's own history.

---

## The one-line version

T097 was right that the stub's premise had expired and right that the taxonomy
had been ratified. It was wrong about who owed the fix: `035` had already
written it, and this branch is carrying a stale skeleton of another feature's
instrument.

## What the filing said

`debug/run_fullcopy_sweep.py:846` carried
`TODO(035-verdict-taxonomy): replace this stub once Groups E-P leave review`,
with its context recording the premise verbatim -- *"still in review as of
2026-08-18; cycle3-amendments.md ... not yet folded into spec.md"*. T096's
sweep found it, and T096 ran precisely because a rebase had proved this branch
had been **48 commits behind** and therefore blind to contracts that had
already landed.

The premise had indeed expired: 035's `spec.md` now carries Groups E, F, G, H
and P, and `contracts/artifact-schema.md:95-96` settles
`RESOLVED | RESOLVED-BY-EQUIVALENCE | DANGLING | SILENTLY_UNSET`.

## What was actually true

The same blindness, one layer up. **T097 filed a defect against a file whose
fix had already landed on another branch**, and the filing could not see it
for exactly the reason T096 existed to expose.

| | this branch | `035-fullsweep-fidelity` |
|---|---|---|
| commits touching the file | **1** (`8c72bdc`, the skeleton) | many, incl. `66fe390`, `58cc970` |
| `compare_objects` | present, the stub | **absent** |
| replacement | -- | `reconcile_project_objects`, `findings_from_accounting`, `payload_never_compared`, `drop_records_from_artifact` |
| `debug/fullsweep/` package | **does not exist** | `compare.py`, `census.py`, `artifact.py`, `allowlist.py`, ... |

035's own comment names this stub by its behaviour:

> "Its TODO said the verdict taxonomy was still in review; the ratified spec
> settled it, and `fullsweep.compare.reconcile_objects` implements it (T031)."

And it went further than the filing asked. `payload_never_compared` returns
`None` for every object rather than a cheerful `True`, which
`reconcile_objects` turns into
`unaccounted: present-under-matching-identity-but-never-compared` -- FR-097's
reading that an object merely present with no payload comparison is unexplained
loss. `findings_from_accounting` carries each bucket's own detail string as the
verdict, so a reader sees WHICH failure mode applied "instead of the stub's
single undifferentiated token".

## Two corrections the filing needs, worth keeping

1. **The four-valued vocabulary is not this seam's.** In
   `artifact-schema.md` it is `link_findings[].classification` -- a claim about
   a LINK. `findings[]` carries `kind` (e.g. `value-mismatch`) over
   class/category/field/source_value/target_value. `compare_objects` receives
   `{class_name: {guid, ...}}` inventories, which contain no links and no
   fields, so it could not have been upgraded to that vocabulary without a
   different input. 035 did not upgrade the stub's verdict; it replaced the
   stub's whole question.
2. **The stub's rows already violate a SETTLED requirement**, not merely an
   unratified one. FR-145 requires every finding to carry the concrete source
   value, target value, class, category and field, and says a finding whose
   labels are "empty, placeholder, or identical regardless of subject MUST
   itself fail the run". Every row the stub emits has
   `category=None, field=None, target_value=None` and the subject-invariant
   token `NOT_YET_CLASSIFIED_MISSING_FROM_TARGET`. This is why the fix could
   not have waited on Groups E-P in the first place.

## What was done, and what deliberately was not

Not re-implemented here. Re-implementing the comparator in this worktree would
fork another feature's instrument, duplicate finished work, and conflict with
the branch that is ahead -- against a package this tree does not even contain.
CLAUDE.md's rule for spec files ("do not edit another feature's ... from an
unrelated worktree") is the same principle.

The TODO is **not deleted** -- the task line forbids it, and on this branch it
is still TRUE of the code beneath it. It now says where the fix lives, with
commit ids, so the next sweep of `PROVISIONAL`/`TODO(contract)` markers does
not file this a third time. No behaviour changed, so no before/after is owed:
that requirement in the task line attaches to REPLACING the stub, which is
exactly what did not happen here.

## The shape

Thirteenth appearance of this feature's recurring shape, and a new variety of
it. Every earlier one was a signal read at the wrong LEVEL. This one was read
at the wrong **repository state**: a correct observation about a file, made
against a copy of it that was 48 commits behind the branch that owns it. The
filing's own instrument -- a text sweep for `TODO(contract)` markers -- cannot
see across branches, which is exactly the blindness it was written to expose.
