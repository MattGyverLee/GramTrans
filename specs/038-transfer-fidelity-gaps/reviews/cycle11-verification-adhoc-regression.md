# Cycle 11 — MoMorphAdhocProhib "regression" on mbugwe: NOT the T123 cast fix

**Tree:** worktree `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
**HEAD:** `73552e47231c4e40ddffaca7ce4da6a635e10d37` (branch `038-transfer-fidelity-gaps`)
Read-only: no edits, no live LCM open, no FLEx open. One filesystem `stat` on the
source `.fwdata` (metadata only, no LCM).

## Headline finding — the SOURCE project drifted, not the code

`projects.source.fwdata_sha256_before/after` and `object_count_total` from the
committed/working census artifacts, same pair name+path throughout:

| tag | date | source sha256 (first 8) | source object_count_total | MoMorphAdhocProhib source_count |
|---|---|---|---|---|
| t078/t124/t126 | 08-22→08-28 | `fb6aadab` | 23760 | 2 |
| t123c | 09-18 | `3fb29a29` | **48622** | **39** |

`source_count` is computed by `census.py`'s `I<Class>Repository.AllInstances()`
exact-class filter (`census.py:1317-1367`, `_repository_interface` +
`objects_in_class`), a raw repository count against whatever `.fwdata` is
opened at `handle.ObjectRepository` — **independent of `_rules_enumerate_all`/
`_recurse_adhoc` entirely**. `census.py` itself only changed in unrelated
regions (T081 roster wiring, `UNREFERENCED_IN_SOURCE`) between t126 (`efa57b5`)
and HEAD — no `AdhocProhib` hit in that diff. The source object population
nearly doubled (23760→48622) between three independent runs that agreed at
`source_count=2` and this run. Filesystem corroboration:
`Mbugwe LizzieHC practice.fwdata` `LastWriteTime = 2026-09-06 22:43:41`, inside
the t126→t123c window — the file changed on disk although the harness opens it
"read only" (read-only in-process ≠ immutable on disk).

**This makes the T078-vs-t123c comparison apples-to-oranges by construction.**
`MoMorphAdhocProhib 2→35` was never a same-source regression; the census
artifact's own `run038_t124_recensus.py:43-55` already carries a standing
caveat that mbugwe's baseline comparability to T078 is broken for exactly this
reason (different starter-baseline provenance), and the drift compounds it.

## Strong first lead — examined, ruled NOT CAUSAL

`categories.py:4270-4293` (`_recurse_adhoc`) — commit `16ade93` changed
`members = getattr(obj, "MembersOC", None)` to
`getattr(_cast_rule_concrete(obj), "MembersOC", None)`. But `obj` at that
point is already `_unwrap(raw)` = `_cast_rule_concrete(...)`-cast (line 4276,
unchanged either side of the diff — confirmed via `git show 16ade93^:...`).
Re-casting an already-cast `MoMorphAdhocProhib`/`MoAdhocProhibGr` proxy is
idempotent (`ICmObject`→interface QI succeeds identically twice); `getattr`
on a leaf `MoMorphAdhocProhib` (no `MembersOC` slot) returns `None` before and
after. **Predicted population effect on `MoMorphAdhocProhib`: zero. Counted:
zero** — `t078/t124/t126` all read `2` against the *stable* source; the only
count change tracks the source drift, not this commit.

**Incidental confirmation the fix is real and working**: `MoAdhocProhibGr`
went `source_count 0` (all three T078-era pairs) → `4` in t123c (first project
ever to carry a grouping node) and reads **MATCHED 4/4** — exactly the
"latent, correct the day it arrives" case the commit's docstring named.

## Ranked hypotheses for the genuine `-4`

1. **NOT-A-REGRESSION (source drift)** — settles the "regressed=1" framing.
   Evidence: sha/size/mtime above. Confidence: high.
2. **Newly-exposed group-child creation shortfall** (real, separate defect) —
   4 `MoAdhocProhibGr` groups now exist with real children; 4 of 39
   `MoMorphAdhocProhib` fail to arrive. Falsify/settle with a **destination-side
   GUID diff**: for each of the 4 `MoAdhocProhibGr` in
   `GT038 T124 Mbugwe`, read `IMoAdhocProhibGr.MembersOC` GUIDs and diff
   against the corresponding source group's `MembersOC` GUIDs (`t123d`
   candidate query, read-only). If the 4 missing GUIDs are all group-children,
   this is the live defect to chase in `_rules_enumerate_all`'s create/T009
   wiring (`categories.py:4650` `MoMorphAdhocProhib` execute leg).

## Recommendation

**NOT-A-REGRESSION** for the "T078 MATCHED→SHORTFALL" framing — the source
population changed underneath the comparison, confirmed by sha256 + object
count + disk mtime, independent of any 038 code change.
**LIVE READ** (t123d, low incremental risk): diff `MembersOC` GUIDs on
`GT038 T124 Mbugwe`'s 4 `MoAdhocProhibGr` against source, to settle whether
the `-4` is a real group-child creation gap worth its own task.
