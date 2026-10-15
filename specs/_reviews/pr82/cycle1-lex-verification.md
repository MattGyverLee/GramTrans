# PR #82 cycle 1 -- lex-verification (static + unit; no live run, no FLEx writes)

Note: FLExToolsMCP was not available to this agent; flexicon was read directly
(D:/Github/_Projects/_LEX/flexicon, v4.13.0 = installed editable). Unit tests:
33 passed (test_ws_followups_75_80 + test_ensure_writing_systems).

## Task 1 -- Behavioural equivalence: PASS (create/activate/skip outcomes unchanged)
Old vs new `_ensure_writing_systems` (api.py ~892-960):
- Already active: skip -- same. Absent: Create -- same. Stored-not-active: failure
  "stored but not active" -- same. active=None + stored: "not verifiably active" -- same.
- Exists() raising -> treated absent -> Create attempted -- same.
- Duplicates: `active` is updated after Create, so 2nd duplicate skips -- same.
- skip/map choices never reach to_create (create_in_target False) -- same filter.
- Create exception handling block untouched.
Intentional, non-outcome divergences (P2): failure record `item_guid` tag -> "" and
severity "warning" (ws_mapping.py ws_create_failure); `_attach_dropped_items` now
dedupes on dropped_identity; is_vern compares enum by .value (fixes foreign-path
WSKind; a legacy/malformed raw value that is not "vernacular" now -> analysis,
same as before for non-matching values; a raw string equal to the value now
-> vernacular, previously analysis).

## Task 2 -- Preview/Move parity: PASS on construction, with P0 caveat below
preflight_ws_creates uses the same ws_entries_to_create / active_ws_ids /
ws_create_state as Move. Calls made: GetAll() (reads AllWritingSystems + current
lists), Exists() (read-only _GetWSByTag + current lists). No Create, no factory,
no UOW, no AddToCurrent*. Never raises. Gap (P2): Preview does not simulate the
`active.add` after Create, so duplicate create entries for one blocked tag yield
two identical records (Move yields one); dedupe in report likely hides it.

## Task 3 -- Coverage gap: FAIL (unit fakes do not model real LCM)
P0 (ws_mapping.py ws_create_state, ~l.690; api.py ~l.945): real flexicon 4.13.0
`WritingSystemOperations.Exists` (code/System/WritingSystemOperations.py:1035) is
ACTIVE-ONLY (doc cites flexicon issue #250 Defect 1); store-wide check is the
separate `ExistsInStore`. Therefore in production a stored-but-inactive tag gives
Exists()==False -> WS_CREATE, and `Create` (same file:194, #250 Defect 2) simply
ACTIVATES the stored WS. WS_BLOCKED is unreachable with real flexicon, so:
 (a) preflight_ws_creates (#78) can never emit a record -- the feature is inert;
 (b) the comment "Exists() scans the whole LDML store" (#44) is stale; the
     "stored but not active -- cannot create" failure text is wrong and the
     condition it guards no longer exists. Move's actual behaviour is
     create-or-activate, unreported by Preview.
Both unit fakes (test_ws_followups_75_80.py:~60 `Exists` = store membership;
test_ensure_writing_systems.py:53 `Exists` = tag in "existing") model the OLD
store-scanning semantics and are separate from GetAll, so they pass while
describing a flexicon that no longer exists. Not a regression from main (main had
the same dead branch) but PR #82 builds new feature + tests on it. pyproject floor
is pyflexicon>=4.5.2, so older flexicon where Exists scanned the store may
still apply -- a floor decision is needed.
Recommended fix: use `ExistsInStore` (present on >=4.13) for in_store, and either
treat inactive-stored as WS_CREATE-with-activation (report "will be activated") or
keep blocked; update fakes so Exists==active-only and ExistsInStore==store.

Live fixture that closes the gap (do NOT run here): restore Target, via flexicon
add a TEST_ WS (e.g. "qaa-x-testws"), then deactivate it (remove from
CurrentVernacular/Analysis, keep LDML) -- or use a Target backup containing an
inactive WS. Map a source WS create_in_target to that tag. Assert before: Exists
False, ExistsInStore True, tag not in GetAll; run preflight (expect per fix) and
`_ensure_writing_systems`; assert after (re-queried) tag in GetAll and
ExistsInStore, no duplicate WritingSystemDefinition, DB restored.
Run with FLEXLIBS_REQUIRE_LIVE=1, then check live_status.json run_mode == live.

## Verdicts
Task 1 PASS | Task 2 PASS (structure) | Task 3 FAIL
P0: stale Exists semantics make blocked branch / preflight dead (above).
P1: live gate does not cover the inactive branch; claim #78 unverified.
P2: item_guid/severity/dedupe changes; duplicate preflight records.
