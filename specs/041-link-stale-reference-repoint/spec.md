# Spec 041: LINK stale-reference re-point (issue #15)

Status: DRAFT, spec only. No code in this slice. Refs MattGyverLee/GramTrans#15.
Origin: deferred from 022 (amendment-disposition-model.md section 8, open question 2).
Governing text: constitution v6.0.0 Principle IV (mode vocabulary; LINK writes nothing)
and Principle I (cross-references must resolve to real objects or fail loudly).

## 1. Decision: why spec-only

A minimal safe implementation does not fit yet. Reasons:

1. "Stale reference" has no definition. Today nothing identifies which reference on
   an existing target object is "wrong or obsolete". A target ref that differs from
   the source ref is indistinguishable from a deliberate local edit (the 3-way
   baseline limitation, amendment section 4). Without a predicate, any re-point is a
   guess, and a wrong guess silently rewrites user data.
2. It contradicts LINK's contract. LINK is "reference the existing target object;
   write nothing" (Principle IV, `conflict.py:763`, `transfer.py:835`,
   `preview.py:497`). A repair that writes to existing objects is, by definition,
   UPDATE-class behaviour restricted to reference fields. Overloading LINK would
   break the Preview/Move agreement the mode relies on.
3. UPDATE already covers the safe half. For reference fields on objects that diverge
   from source, UPDATE's non-destructive source-preferring write is the existing
   re-point mechanism. What is missing is only the narrow case in section 3 below.
4. Failure modes are graph-level (dangling ref, cycle, cross-category target, ref to
   an object that is itself being skipped) and need a per-field-kind inventory of
   reference properties before any code is safe. That inventory does not exist.

## 2. Problem restated

After a first transfer, a target object T (matched by GUID, so LINK skips it) may
hold a reference R that no longer resolves to the object the source intends, because
the originally-linked referent was later deleted, replaced, or re-created under a
different GUID (e.g. a category re-added via ADD_NEW, a slot re-created). LINK leaves
T untouched, so R stays pointing at the wrong or obsolete object.

## 3. Recommended minimal slice (for a later feature)

Make it a ref-only, opt-in sub-behaviour, not a change to LINK semantics:

* Trigger only when ALL hold: (a) T is present by GUID and selected; (b) the field is
  a single-valued or collection reference in an explicit allow-list of reference
  properties (start: affix->slot, slot->template, allomorph->environment, APR->category);
  (c) the target ref is provably stale: it is null, dangling, or points to an object
  with a different class than the source referent's class; (d) the source referent
  has exactly one GUID-matched counterpart in the target.
* Otherwise: clear SKIP with a reported reason ("reference differs, not provably
  stale"). A ref that points to a valid same-class object that merely differs is NOT
  stale and is never re-pointed (that is UPDATE's job).
* Surface as a new disposition label (e.g. `REPOINT`) in Preview, computed by the same
  function Move consumes, so Preview and Move agree by construction. Never emitted
  under ADD_NEW.
* Fail loudly (Principle I) if the intended referent cannot be resolved in the
  target; do not leave a half-repaired graph.

## 4. Open questions

1. Is a user-visible new mode needed, or is `LINK + repair refs` a checkbox on the
   category? (Leaning: checkbox, default off, so LINK stays write-nothing by default.)
2. Constitution: does Principle IV need an amendment (LINK is "write nothing") or does
   a distinct REPOINT disposition sit under UPDATE without one?
3. Which reference properties are in the allow-list, and which need cycle protection?
4. Does the residue baseline (feature 040) let us distinguish "stale" from "user
   re-pointed on purpose", making auto-repair safe enough?
5. Reporting: should repaired and not-provably-stale refs appear as separate run
   report lines?

## 5. Verification (when implemented)

Write-path change: full crew cycle and a live-LCM gate with `FLEXLIBS_REQUIRE_LIVE=1`
on a restored `Target` are required; unit tests alone are insufficient. Unit tests
should cover: stale ref repaired; valid-but-different ref untouched; ambiguous
referent -> SKIP with reason; Preview/Move agreement; idempotent re-run.
