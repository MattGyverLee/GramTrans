# PR #82 cycle 2 - lex-programmer report

Commit: b22a99b on fix-ws-followups. Push to origin succeeded (no force).
Unit suite: python -m pytest tests/unit -q -> 5020 passed, 0 failed, 81 skipped, 14 xfailed.

## Files changed
- pyproject.toml, CLAUDE.md (floor pyflexicon>=4.8.0 + why; 4.5.x history kept)
- src/gramtrans/Lib: ws_mapping.py, api.py, models.py, report.py, categories.py, owned.py, pictures.py
- src/gramtrans/gramtrans.py (debug log of first ImportError before fallback)
- tests/unit: _fakes_ws.py (new shared fake), test_ws_followups_75_80.py, test_ws_path_fidelity.py, test_ws_path_followup.py, test_ensure_writing_systems.py
- tests/integration/test_ws_followups_live.py

## States (ws_mapping.ws_create_state)
- WS_ACTIVE: tag in GetAll set (or Exists() True when active set is None). Nothing to do.
- WS_ACTIVATE: not active, ExistsInStore() True. Move calls Create (activates). Preview: one INFO record.
- WS_CREATE: absent everywhere. Move creates. Preview: nothing.
- WS_UNDETERMINED: active set AND Exists() both failed. Warning in Preview; Move still attempts Create.
- WS_BLOCKED removed. Missing ExistsInStore raises RuntimeError naming >=4.8.0 (Move and Preview both loud).
- New: ws_is_active (fresh re-check), ws_activate_notice, models.merge_dropped_records (info->warning upgrade).

## Notes
- Move re-checks activity after Create; if still inactive it emits the ws_create_failure warning.
- Preview dedupes per tag and stays read-only (fake Create asserts).
- Items 6-10 done: three-way collision tests, behavioural #77 test (sys.modules["api"]=None), dropped_identity at all three sites (safe: GUID'd keys unchanged), DROP_SEVERITIES moved, _dropped_dedup_key inlined. getattr(d,"severity","info") left in place.

## Not done
- Live test not run (lex-verification will). It stages es.ldml (copied from Ejagham Mini/Esperanto, read-only donors) into Target after restore.
- ruff has ~138 pre-existing findings; not addressed.
- Dedupe in report.py enrichment path uses dropped_identity only (no severity upgrade); merge helper used only in api._attach_dropped_items.
