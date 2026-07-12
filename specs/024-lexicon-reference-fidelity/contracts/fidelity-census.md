# Contract: Model-Driven Fidelity Census (`tests/verification/fidelity_census.py`)

Covers FR-011 / US5. A **development/CI harness**, not runtime code (Q4). It is the
independent check that the resolver's hand-curated field map (data-model.md) is complete.

## `populated_ref_owned_fields(obj, cache) -> set[FieldKey]`

Enumerate, directly from the LCM model, the owning + reference fields populated on one object.

- `mdc = IFwMetaDataCacheManaged(cache.MetaDataCacheAccessor)`
- `flids = mdc.GetFields(obj.ClassID, includeSuperclasses=True, kgrfcptAll)`
- keep `flid` where `GetFieldType(flid)` ∈ {23 OwningAtom, 24 ReferenceAtom, 25 OwningColl,
  26 ReferenceColl, 27 OwningSeq, 28 ReferenceSeq} (includes custom fields)
- populated test via `ISilDataAccess` (`cache.DomainDataByFlid`):
  - atomic (23/24): `get_ObjectProp(obj.Hvo, flid) != 0`
  - coll/seq (25/26/27/28): `get_VecSize(obj.Hvo, flid) > 0`
- returns `{(class_name, field_name, kind)}`

## `census_pair(src_obj, tgt_obj, cache) -> CensusResult`

- `gaps = populated(src) − populated(tgt)` restricted to fields that *should* carry
  (owned + reference; value/string fields are covered by syncable-props and excluded here).
- `CensusResult`: `{src_guid, gaps: list[FieldKey], matched: int}`.

## `run_census(src_project, tgt_project, guid_pairs) -> CensusReport`

- For each copied (source→target) object pair, run `census_pair`.
- **Assertion (US5 / SC-004)**: every gap MUST correspond to a `DroppedItemRecord` from the
  transfer run; an unexplained gap fails the harness.
- Emits a report grouped by class, with total gaps and the reconciled-vs-unexplained split.

## Usage

- Runs offline over test fixtures (constructed with custom/modified list items, since the
  Ejagham corpora have none) and, opt-in, as a deep audit against a real transfer.
- **Not** invoked during a live transfer; per-transfer fidelity is the FR-010 report's job.
- Maintenance trigger: an LCM model upgrade may introduce new owning/reference flids — re-run
  the census to catch any the field map should adopt.
