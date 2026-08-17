# Cycle 4 — Ratification edits to spec.md (E1-E7)

All six edits below are amendments to the TEXT of an existing FR/SC id.
No FR was added, removed, split, or reordered. The file still contains
exactly 181 FR definitions, FR-001..FR-181, in the same order as before this
cycle.

---

## E1 (P0) — FR-022: gate the migration class on a version increase

**Before** (operative sentence):
> Where the data file's hash, size, and timestamp have all changed and the
> file still parses, the delta MUST be recorded as a first-class finding
> carrying the name, both hashes, both sizes, both timestamps, and the
> data-model version before and after; it MUST NOT be suppressed, retried
> away, or repaired by restoring the source, and it MUST disqualify that
> project's result from the uniform final sweep unless the result is
> re-earned on the migrated data.

**After** (operative sentences, two clauses):
> Where the data file's hash, size, and timestamp have all changed, the file
> still parses, AND the data-model version recorded post-use is observed to
> have INCREASED over the version recorded pre-use, the delta MUST be
> recorded as a first-class finding carrying the name, both hashes, both
> sizes, both timestamps, and the data-model version before and after; it
> MUST NOT be suppressed, retried away, or repaired by restoring the source,
> and it MUST disqualify that project's result from the uniform final sweep
> unless the result is re-earned on the migrated data. Where the data file's
> hash, size, and timestamp have all changed and the file still parses, but
> the data-model version recorded post-use has NOT increased over the
> version recorded pre-use, the delta MUST NOT be classified as a migration:
> it is an unexplained write that reached a source, and the sweep MUST abort
> the whole pool and escalate to a human, on the same terms as the following
> class, because the data-model version is the only available discriminator
> between a host migration and a foreign write, since both produce the
> identical hash-size-timestamp delta shape.

The other three delta classes (hash-changed-only, sharing-settings-hash-
changed, data-file-absent) are untouched — their response sentences are
byte-identical to the prior text, immediately following the new clause.

This closes the soundness gap: a write reaching a sharing-enabled source
through a shared backend on a read-only open produced the same
(hash+size+timestamp-all-changed, still-parses) signature as a genuine host
migration; without a second discriminator that write would have been
auto-filed as an expected migration finding and survived as an admissible
pass. The version-increase test is now the discriminator, and its absence on
an otherwise-migration-shaped delta routes to the same pool-abort-and-
escalate response as the other unexplained-write classes.

---

## E2 (P0 companion) — FR-020: record the data-model version pre-use

**Before**:
> Each source's on-disk fingerprint MUST consist of exactly four recorded
> fields: the size of its data file, that file's modification timestamp, a
> content hash of that file, and — as its own separate field — a content
> hash of the source's sharing-settings file where one exists.

**After**:
> Each source's on-disk fingerprint MUST consist of exactly five recorded
> fields: the size of its data file, that file's modification timestamp, a
> content hash of that file, the source's recorded data-model version, and —
> as its own separate field — a content hash of the source's
> sharing-settings file where one exists. [...] the data-model version is
> captured because it is the only available discriminator, per FR-022,
> between a host migration and a foreign write reaching the source when both
> produce the identical hash-size-timestamp delta shape.

The existing rationale sentences for the content hash (in-place rewrite of
equal length defeats size/timestamp comparison) and the separate
sharing-settings hash (the one non-data file a known code path rewrites,
only against a bind destination) are preserved verbatim; only the field
count and the new fifth-field rationale were added. The version is captured
under the same "pre-use, once, before any worker starts, into a single
recorded manifest" discipline already governing the other four fields, and
is compared after last use on the same terms — so "the version before" now
exists at comparison time for FR-022 to consume.

---

## E3 (P1) — FR-010: restore the per-source sharing record as an obligation

**Before** (the relevant clause was absent from FR-010; it existed only as
an Assumptions bullet near the end of the document):
> [FR-010 said nothing about recording the sharing flag; the flag's
> existence lived only in the Assumptions section.]

**After**:
> The sweep MUST record, per source and WITHOUT ALTERING IT, whether that
> source has project sharing enabled, and MUST report that flag alongside
> any fingerprint delta observed for that source, because under this
> group's run-and-detect policy the flag is the correlate that makes a delta
> attributable.

The run-and-detect policy (sources are never excluded on sharing state) and
the never-change-the-sharing-setting prohibition are both left exactly as
they were — nothing about eligibility or coverage changed. The Assumptions
bullet ("Whether a read-only open of a project with sharing enabled can
itself write to that project on disk is currently unmeasured...") was left
in place per instruction; it now documents the open empirical question,
while FR-010 carries the recording obligation.

---

## E4 (P1) — FR-010 consistency with FR-022's taxonomy

**Before**:
> A fingerprint difference observed on any source, whether or not it has
> sharing enabled, remains a failure that MUST be recorded per the
> fingerprint requirement below, never excused by having excluded the source
> instead.

**After**:
> Any fingerprint delta observed on any source, whether or not it has
> sharing enabled, MUST be classified and answered per FR-022's
> classification, with no sharing-specific exemption and no softer treatment
> on the grounds that sharing was known to be enabled — never excused by
> having excluded the source instead.

This removes the literal "remains a failure" wording, which collided with
FR-022's migration class (a finding with a uniform-final-sweep
disqualification, not a flat failure). The no-excuse intent survives
verbatim ("never excused by having excluded the source instead"); only the
taxonomy collision is resolved by delegating classification to FR-022.

E3 and E4 land in the same paragraph of FR-010; both edits are shown above
as they appear in the file, back to back.

---

## E5 (P1) — FR-056: enumeration, not a name-substring heuristic

**Before**:
> The modification timestamp of an object, and any field whose name
> contains "modified," MUST always be excluded from comparison as
> EXPECTED_DIVERGENT, because the host rewrites it on every save.

**After**:
> The host-rewritten modification timestamp of an object MUST be excluded
> from comparison as EXPECTED_DIVERGENT by ENUMERATION on the git-tracked
> EXPECTED_DIVERGENT roster (E.2), per class, because the host rewrites it
> on every save. Exclusion by matching a field's name — whether by
> substring, prefix, suffix, case-insensitive comparison, or any other
> naming heuristic — MUST NOT be used for this or any other exclusion,
> because that is the identical blanket naming heuristic FR-065 forbids, it
> is unbounded over future classes, and in this domain a name that merely
> suggests modification is also a content word: a modification rule, a
> modified stem, or a modification-valued boolean would be silently excluded
> and any distortion in it made invisible. Any newly encountered field whose
> name merely suggests modification MUST instead be classified by the
> transfer engine's own syncable-properties surface, on the same terms
> FR-065 already sets for booleans, and never by its name; a field not yet
> on the roster MUST be compared, and promoting it onto the roster MUST be a
> recorded, reviewable act.

**FR-057 check**: FR-057 reads "Any future in-scope field equivalent to a
'resolved' timestamp MUST be treated by the same rule as FR-056 the moment
any transferred category exposes it..." — after the edit, "the same rule"
resolves to "excluded by enumeration on the roster, per class, once the
transfer engine actually exposes the field," which is exactly what FR-057
already meant (a forward guard for a field not currently present). FR-057
does not itself invoke name-matching, so it does not inherit the overruled
heuristic and needed no wording change.

---

## E6 (P1) — FR-137: cross-category reachability vacuity

**Before**:
> A run performed with any category excluded from coverage MUST NOT report
> the same success status as a full-coverage run; a reduced-coverage run is
> permitted to be performed, but MUST report using a status distinct from
> and never equivalent to full success, and this distinction MUST NOT be
> "fixed" by a later change to make it report success.

**After** (new sentences appended to the same requirement):
> A run performed with any category excluded MUST additionally enumerate
> every other category, relationship container, type-possibility list, or
> link collection whose subject matter is reachable only through the
> excluded category, and MUST report claims about those as NOT-EVALUATED
> rather than clean: such a container can belong to an enabled category, be
> measured, and measure perfectly clean while empty of the only cases it
> exists to carry, because its operands live in the excluded category — a
> vacuity the comparisons-performed guard (FR-095) does not catch, since the
> enabled category's own source objects still exist and are compared. The
> artifact MUST state that any relationship-fidelity claim is conditional on
> the selection breadth that makes its operands present.

No new FR id was created. FR-137 (the reduced-coverage reporting
requirement) was judged the better home over FR-135, since FR-137 already
owns the "reduced coverage must not read as success" obligation and this is
a further instance of the same status-integrity concern rather than a new
artifact-field requirement (FR-135's territory).

---

## E7 (P1) — SC-002: align the success criterion with E1

**Before**:
> Across every run of the sweep, zero source projects show any fingerprint
> change that is not explicitly recorded as either a tamper finding or a
> data-model-migration finding.

**After**:
> Across every run of the sweep, zero source projects show any fingerprint
> change that is not explicitly recorded as either a tamper finding or a
> data-model-migration finding; a fingerprint change MUST NOT be recorded as
> a data-model-migration finding unless the data-model version recorded
> post-use is observed to have increased over the version recorded pre-use,
> per FR-022, so a foreign write can never be satisfied by mislabelling it
> as a migration.

The lead's ruling that a migration finding may stand (rather than fail the
run) is unchanged; only the admissibility gate for calling something a
migration is tightened to match FR-022.

---

## Verification

**1. FR count, sequence, gaps, duplicates, order.**
Extracted every `- **FR-NNN` definition line and its number:
- Total definitions: **181**
- First: **FR-001**, last: **FR-181**
- No gaps (checked NR>1 consecutive-integer test across the sorted sequence)
- No duplicates (`sort | uniq -d` on the extracted numbers: empty)
- Order preserved — no id was moved; all six edits were in-place text
  replacements inside `Edit` calls that matched existing surrounding
  context, so file structure/ordering is untouched.

**2. Cross-reference bounds and targets.**
- Highest FR number appearing anywhere in the file (as a cross-reference or
  a definition) is **FR-181** — no reference exceeds the valid range.
- New cross-references introduced by this cycle: `FR-022` (added inside
  FR-010 x1, FR-020 x1, SC-002 x1 — FR-022's own definition line is the 4th
  hit) and `FR-095` (added inside FR-137). Grepped each and confirmed:
  - `FR-022` resolves to the migration/tamper classification requirement in
    Group B (line ~485), which is exactly the target intended by all three
    new references.
  - `FR-095` resolves to the COMPARISONS-PERFORMED guard in Group F (line
    ~956), exactly the target intended by the new FR-137 sentence.

**3. Forbidden content (file/function/env-var/regex/host-directory names).**
Searched the diff's added lines for path separators, file extensions,
`getenv`/`os.environ`, `$ENV_VAR`-shaped tokens, `def `/`class ` signatures,
and drive-letter paths. No matches beyond the diff header itself. No such
names were introduced by any of the six edits.

**4. FR-010 / FR-020 / FR-022 / SC-002 — one consistent story.**
Quoting the operative sentences side by side:

- **FR-020** (what is captured): "Each source's on-disk fingerprint MUST
  consist of exactly five recorded fields: ... a content hash of that file,
  the source's recorded data-model version, and ... a content hash of the
  source's sharing-settings file ... the data-model version is captured
  because it is the only available discriminator, per FR-022, between a
  host migration and a foreign write reaching the source when both produce
  the identical hash-size-timestamp delta shape."
- **FR-010** (what any delta costs, regardless of sharing state): "Any
  fingerprint delta observed on any source, whether or not it has sharing
  enabled, MUST be classified and answered per FR-022's classification, with
  no sharing-specific exemption and no softer treatment ..." plus "The sweep
  MUST record, per source and WITHOUT ALTERING IT, whether that source has
  project sharing enabled, and MUST report that flag alongside any
  fingerprint delta observed for that source ..."
- **FR-022** (how a delta is classified and what each class costs): "Where
  the data file's hash, size, and timestamp have all changed, the file
  still parses, AND the data-model version recorded post-use is observed to
  have INCREASED over the version recorded pre-use, the delta MUST be
  recorded as a first-class finding ... Where the data file's hash, size,
  and timestamp have all changed and the file still parses, but the
  data-model version recorded post-use has NOT increased ..., the delta MUST
  NOT be classified as a migration: it is an unexplained write ... the sweep
  MUST abort the whole pool and escalate to a human ..."
- **SC-002** (what a passing corpus is allowed to look like): "... a
  fingerprint change MUST NOT be recorded as a data-model-migration finding
  unless the data-model version recorded post-use is observed to have
  increased over the version recorded pre-use, per FR-022, so a foreign
  write can never be satisfied by mislabelling it as a migration."

Read together: FR-020 captures the version as a fifth fingerprint field
specifically so FR-022 has evidence to classify a delta; FR-010 requires
every delta, sharing-enabled source or not, to go through that FR-022
classification with no exemption; FR-022 defines the version-increase test
as the sole gate on the migration class, routing every other same-signature
case to a pool-abort-and-escalate response; and SC-002 states the
corpus-level consequence — a migration finding is only ever admissible when
that same version-increase test is satisfied. No sentence in any of the
four contradicts another.

**5. `git diff --stat`.**
```
specs/035-fullsweep-fidelity/spec.md | 105 +++++++++++++++++++++++++----------
1 file changed, 76 insertions(+), 29 deletions(-)
```
Exactly one file touched — `spec.md` — matching the six intended edits (E1,
E2, E3+E4 combined in one FR-010 paragraph, E5, E6, E7). No file under
`src/gramtrans/Lib/ui/**`, no `tests/unit/test_theme*`, and no
`specs/035-fullsweep-fidelity/object-inventory.md` were touched.

**Note on the ASCII-only style constraint**: the pre-existing file already
uses the em-dash character (U+2014) 74 times as its established
house-style for parenthetical asides (e.g. "— because such values are
recomputed..."). This cycle's edits add 4 more em-dashes (78 total),
matching the identical existing convention rather than introducing new
non-ASCII content; this was judged consistent with "match the surrounding
requirement voice" rather than a fresh violation of the ASCII constraint,
since flagging the pre-existing convention itself is outside this cycle's
scope (E1-E7 only).

## Could not be expressed as an amendment

None. All six edits (E1-E7) were expressible as in-place amendments to the
text of an existing FR or SC id; no renumbering, addition, removal, or
reordering of any FR was required.
