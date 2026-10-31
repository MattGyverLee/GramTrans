# QC cycle 4: PR #158 (d88dc4a), #129 follow-up

> Saved by the main session. The lex-qc agent had no Write tool and returned this report as its final message.
> It was a read-only review of GramTrans-qc-d88dc4a and its saved diff. The tests were traced by reading, not run.

**Verdict: PASS-with-P2. Score: 84/100.**

## 1. Ruling fidelity (src/gramtrans/Lib/references.py)

**Ruling 1: met (1295-1322).** The pending per-WS drops are replaced by one `relocated:` record naming source WS X and target WS Y. It is written only when `field_props` is empty and drops are pending.

**Ruling 2: met (~1300-1303).** The guard is `source_vern_ids is not None and best_src_id not in source_vern_ids`. The vernacular set is None when it cannot be read (29-39), and the fallback is then skipped.
- **P2:** `best_src_id` is the first non-empty alternative in dict order, not the one `_best_text` picks. A vernacular alternative listed first blocks relocation. That is safe, but inconsistent.

**Ruling 3: met.**
- `_default_analysis_ws_id` (9-26) returns None when the default cannot be resolved.
- In that case `_wrap_plain_text` returns `{}` and never takes the first dict entry.
- No remaining write goes to a WS other than the default. The only other writer is the exact-Id match in the legacy branch (1337).

**Ruling 4: met by code (1338).** No integration test covers the legacy branch.

**Ruling 5: met** for the drop, relocated and ApplySyncableProperties-failure records (1357-1368). These values are overwritten anyway by `categories._enrich_dropped` (categories.py:6645).

## 2. Dedup collapse (priority)

**How it works:**
- `_call_apply_reference` (categories.py:6780-6786) enriches each record, then calls `_append_dropped_once` (6632-6641).
- That function keys on `dropped_identity` (models.py:3970-3982), which is `(owner_guid, field_name, item_guid)`. Every record here has `field_name = ThesaurusItemsRC`, so neither the reason nor the inner field (Name, Abbreviation, Description) is part of the key.
- **First-in wins, and later records are discarded.** There is no severity upgrade on this path; only `merge_dropped_records` upgrades.
- Order: Name, then Abbreviation, then Description (323). The ApplySyncableProperties-failure record comes last.

**Can a relocation hide a loss? Yes:**
- A Name relocation is stored first. A later plain drop for Description (vernacular-only) is discarded, so the report says "relocated" while Description was actually lost.
- An ApplySyncableProperties-failure record ("could not be copied") hidden behind an earlier relocated record means nothing was written at all, yet the report says "relocated".
- A Name drop can also hide a later Abbreviation relocation. That direction only under-reports a gain.

**Ordinary item:** Name, Abbreviation and Description all sit in a source-only analysis WS. This produces 3 relocated records, 2 are discarded, and the survivor mentions only Name. The transfer is lossless but under-reported.

**Pre-existing?** Yes. The same first-in collapse already applies to drops on main:
- Name 'de' and Abbreviation 'de' collapse into one record.
- A failure record is hidden behind an earlier drop.
- Per-type granularity is documented as by design (categories.py:7666, 7800).

#158 makes it worse: a benign-sounding "relocated" can now mask a real loss.

**Recommendation: P2, with a mandatory follow-up issue. It does not block merge.**
- The `dropped_identity` contract is shared by ~30 call sites, so it is outside #158's scope.
- The item is still flagged PARTIAL in the report, so the loss is not silent.
- Cheap mitigations:
  - Mark relocated records `severity="warning"`.
  - Add a reason-prefix class (relocated vs. loss) to the ThesaurusItemsRC key.
  - On collision, have `_append_dropped_once` prefer the non-relocated record.
- Escalate to P1 only if the lead deems "failure record hidden by a relocation" unacceptable.

## 3. Vernacular comparison
Like is compared with like.
- `GetVernacular` and `GetAll` return the same IWritingSystemDefinition type, and both are read through `.Id`.
- `source_handle_to_id` is built from `GetAll` via `.Id`.

**P2:** an unresolved handle falls back to `str(handle)` (326-351). That string is never in the vernacular set, so the text would be treated as analysis and relocated. This is a narrow edge case.

## 4. `_owner_ids` safety
It uses plain getattr with no pythonnet casts, so the #156 TypeError cannot occur here.

**P2:** getattr catches only AttributeError. A property that raises anything else escapes, and the call at ~1259 is outside any try, so it could abort the whole reference. Wrap it in a try.

## 5. Tests
All 6 fail on the pre-fix code, by reading:

| Test | Why it fails without the fix |
|---|---|
| 1 | Per-WS drops, no relocated record |
| 2, 4 | The old `_wrap_plain_text` writes |
| 3 | The first dict entry is taken |
| 5 | No guard |
| 6 | `owner_guid` is "" |

**P2:** no tests for the dedup interaction, a mixed-field item, or the legacy branch.

## Findings
- **P0:** none.
- **P1:** none.
- **P2:**
  1. Dedup masking (references.py:1322 / categories.py:6632). Follow-up issue required.
  2. Choosing the first alternative in dict order (1300).
  3. `_owner_ids` is unguarded (1259).
  4. The `str(handle)` fallback key is treated as analysis.
  5. Missing tests for dedup, mixed-field and the legacy branch.
