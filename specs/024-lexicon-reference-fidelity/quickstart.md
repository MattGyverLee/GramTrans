# Quickstart: Validating Lexicon Reference & Owned-Object Fidelity

A run/validation guide proving the feature end-to-end. Implementation details live in
`tasks.md` + the contracts; this file is how you *check* it works.

## Prerequisites

- flexicon installed (`pip install -e D:/Github/_Projects/_LEX/flexlibs2`).
- A **source** FLEx project and a throwaway **target** (pattern: Ejagham Mini → a
  disposable `*-GT-Test` copy, per STATUS.md).
- Custom/modified fixtures: since Ejagham Full/Mini reference only factory defaults, build a
  fixture where a sense references **(a)** a custom sense-type and **(b)** a *renamed* default
  translation type, and a target that lacks (a) and holds the stale (b).

## Scenario 1 — Referenced items survive (US1, SC-001)

1. Preview the transfer of the fixture entry.
2. **Expect** in Preview: the custom sense-type shows `CREATE` (with any ancestor chain); the
   renamed default shows `LINK` + a divergence record (shared/default, not mutated).
3. Run Move.
4. **Expect** in target: custom sense-type exists (same GUID) and the sense references it;
   the shared default is unchanged but the divergence appears in the report.

## Scenario 2 — Nothing is blanked (US2, SC-002)

1. In the target, set `SenseTypeRA` and a publication on the matching entry/sense.
2. Run an OVERWRITE-mode transfer of the source entry.
3. **Expect**: those fields hold a correct value afterward — never blank. (Regression target
   for the dropped-on-apply bug.)

## Scenario 3 — Owned children come along (US3, FR-009/009a)

1. Transfer an entry owning an example (+translation), a pronunciation, an etymology, and a
   sense with a sub-sense and an allomorph carrying an environment + APR.
2. **Expect** in target: example + translation (type resolved), pronunciation, etymology
   (LanguageRS resolved), the sub-sense (recursively, with its own refs), the allomorph
   environment linked, and the APR reproduced — or any unresolved piece listed as dropped.

## Scenario 4 — Never-silent report (US4, SC-003)

1. Force an unresolvable reference (e.g. a shared-default divergence, or an APR whose other
   member is not in the copy set).
2. **Expect**: the Preview and post-run panel each list a record naming owner, field, source
   item name + GUID, and reason. No unreported loss.

## Scenario 5 — Fidelity census (US5, SC-004)

Run the offline harness over the copied pairs:

```
pytest tests/verification/fidelity_census.py
# or invoke run_census(src, tgt, guid_pairs) for a deep audit
```

**Expect**: zero *unexplained* gaps — every populated-source-but-empty-target owning/
reference field is matched by a `DroppedItemRecord`. An unexplained gap fails the harness and
points at a missing field-map entry.

## Regression gate (SC-006)

Transfer a no-custom-lists project (plain Ejagham Mini → target). **Expect**: `dropped_items`
empty and all other report output identical to pre-feature behavior.

## Unit tests to run

```
pytest tests/unit/test_reference_resolver.py \
       tests/unit/test_blanking_fix.py \
       tests/unit/test_owned_object_walk.py \
       tests/unit/test_allomorph_hung_data.py \
       tests/unit/test_dropped_item_report.py
```
