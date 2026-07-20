# Finding #2 root cause — Esperanto Move#2 re-adds 146 actions

## Data limitation (be upfront)
`scratchpad/fullcopy_results/Esperanto.json` only records **totals**
(`move1.added=146`, `move2.added=146`, `skipped=25` both runs, and an
*identical* `dropped_breakdown`, 29211 items both runs). `run_fullcopy_live.py`'s
`_summarize()` sums `report.per_category` into `added`/`skipped` ints and
discards the per-category `Counter` — no category-level breakdown was
persisted. `counts_base/post1/post2` track only `pos` (4/4/4) and `phonemes`
(23/23/23), which rules out GRAM_CATEGORIES/POS and PHONEMES as sources of net
growth, but says nothing about the other ~20 categories. **A definitive 146-
by-category split requires re-instrumenting `_summarize()` and re-running** —
out of scope for this read-only pass.

## Code audit result
I read every `plan_action` in `categories.py`'s `LEAF_CATEGORIES` registry
(GRAM_CATEGORIES, INFLECTION_FEATURES, CUSTOM_FIELDS, INFLECTION_CLASSES,
FEATURE_STRUCT_TYPES, POS_INFLECTABLE_FEATS, PHON_FEAT_TYPES, STEM_NAMES,
EXCEPTION_FEATURES, VARIANT_TYPES, COMPLEX_FORM_TYPES, ADHOC_COMPOUND_RULES,
PHONOLOGICAL_FEATURES, PHONEMES, NATURAL_CLASSES, PH_ENVIRONMENT,
PHONOLOGICAL_RULES, STRATA, SEMANTIC_DOMAINS, AFFIXES, SLOTS,
AFFIX_TEMPLATES). **Every one of them has a working by-GUID (or, for
CUSTOM_FIELDS, by-identity) find/skip** — either via `_target_has_guid` /
`_find_target_obj_by_guid`, or the shared `_plan_gold_reserved_edit` helper
(`categories.py:194-300`), and their `execute_action`s create with
`factory.Create(parsed_guid)` (`_create_with_guid`, `categories.py:7376`),
preserving the source GUID. ENTRY/SENSE/MSA/ALLOMORPH have no dispatcher at
all right now — `preview.py:152` and `transfer.py:230` both set
`_VERB_VERTICAL_ENABLED = False`, so selecting those categories currently
plans zero actions; they cannot be the 146 leaking through a broken check.

## The one confirmed real gap: TEXTS (`Lib/texts.py`)
TEXTS is **not** in `LEAF_CATEGORIES` — it has its own walk in `texts.py`.
`_resolve_or_create_text` (texts.py:701-720) creates via
`text_ops.Create(plan.title or "(untitled)", None)` — **no `Create(Guid,...)`
overload is used**, so every created Text gets a fresh, unrelated GUID with
no source→target back-map persisted anywhere.

The disposition decision, `_text_disposition` (texts.py:356-382), does try a
GUID-first check, then falls back to `text_ops.Find(title)` — **but only
`if find is not None and title:`** (line 375). If a source text's title is
empty/blank (`_best_str` returns `""` for genuinely-untitled or `"***"`
texts — common for glossed/interlinear practice texts), the title fallback
is skipped entirely, the GUID check can never match (GUID was never
preserved), and disposition is unconditionally `CREATE` on every re-run.
This is exactly the "find-key differs from create-key, no back-map" shape
described for the 026 fix, concretely demonstrated in live code (not
inferred). It plausibly explains at least part of the 146 (Esperanto's
`Text create failed: FP_ParameterError` x1 and 1207 `StTxtPara` create
failures confirm Esperanto has non-trivial interlinear text content).

## Fix approach
1. Preserve GUID on text create: use the `Create(Guid, ...)` overload if
   flexicon's `Texts` ops factory exposes one (mirror `_create_with_guid`);
   this alone fixes idempotency without needing the title fallback.
2. If no GUID-preserving factory exists, drop the `and title` guard and add
   a structural fingerprint fallback (paragraph-count + first-baseline-text
   hash) per the 026 pattern, so empty-titled texts still match.

## Sibling sweep (same "Create() has no Guid overload + name-only fallback" shape)
Grep `Lib/*.py` for `\.Create\(` calls NOT using `DotNetGuid.Parse` — flag
any hit outside `categories.py`'s already-audited factories. Prime
candidates by structure: `Lib/wordforms.py` (WfiWordform/WfiAnalysis
provisioning — `FINDINGS.md`'s `WfiGloss` WS-mapping note suggests a
similar identity-matching layer) and any `_apply_segment_notes`/tag-wiring
helper in `texts.py` that creates CmAnnotation-like objects by content
rather than GUID.
