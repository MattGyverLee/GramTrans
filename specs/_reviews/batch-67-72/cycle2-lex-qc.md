# Cycle 2 QC review (batch 67-72)

> Saved by the main session on lex-qc's behalf (the agent had no Write/shell tool, so it
> could not run `git diff` or pytest; it reviewed worktree files directly). Pattern-audit
> gate and live-LCM gate were NOT evaluated by QC: re-check both before approving.

**Score: 80/100. Recommend FIX ISSUES (no P0).**

## P1

- `categories.py:12832` (stems_execute_action): `src_entry is None` falls through to `return new_entry` (None), which counts as added. affixes_execute_action (`:12274`) got the skipped outcome, so the sibling is inconsistent. Same when `_walk_lex_entry_closure` declines. Only the reconcile backstop catches it, and it reports failure rather than skip. Return `ActionOutcome.skipped` for the missing source.
- `transfer.py:702-706, 1463-1476`: reconcile expects `action.source_guid` when no planned destination exists. A handler creating under a remapped GUID (`_create_with_guid` with identity_remap) would be flagged `UnverifiedWrite` although it wrote. Consult `context.identity_remap` before declaring missing, or add a test proving leaf handlers never remap.
- `transfer.py:1465-1468`: any lookup exception is swallowed with no log. A broken lookup silently disables the #49 check for the whole run. Log at warning level and count actions left unverified.

## P2

- Hard-coded `recorded=True` at `categories.py:1444, 2495, 3145, 12427, 12651`. `_report_owner_pos_unresolved` (`:5306`) is a no-op when `_exec_skips` is None, so such a decline produces no Skip. Sites `1758, 1843, 1874` correctly use `recorded=exec_skips is not None`. Make the POS sites match.
- `categories.py:1353`: already-present path returns None (documented) and so overcounts "added"; reconcile cannot flag it.
- `preview.py:1372-1380`: a `plan_action` exception becomes a `PlannedAction` with empty `intended_target_guid`, so Preview shows an add. Adjacent to this change but worth a Skip.
- `preview.py:1348-1355` acceptable (failures become Skips). POS empty-picks skip at `:1356` can add a second skip when enumeration failed; KeyError catch at `:1339` could mask a KeyError raised inside `for_category`. Minor.
- Tests: none for reconcile resolved-destination expected-GUID branch (`transfer.py:704`), none for the real `_lookup_target_guid` repo path (`:1439-1445`), none for recorded=True vs engine double-counting inside `execute`. The seven legacy tests now assert `status == "skipped"` (stronger), but not reason or `recorded`.
- Conftest guard (`conftest.py:110-147`): inert when HKCU/HKLM `SIL\FieldWorks\9` RootCodeDir exists. 32-bit Python is redirected to WOW6432Node and could misdetect (risk). Failure-to-skip conversion is bounded to two symptom strings and only when FieldWorks is absent, so cannot mask dev-machine failures. Add a CI floor on the skip count: a green run can now mean "mostly skipped".
- `known-failures.txt` emptied: justified by CI evidence; baseline script still fails if a listed test starts passing.
- `regression.yml:82`: scoping the shared-code check to `034-*`/`039-*` is a correct narrowing but a real weakening: `fix-*` PRs no longer run it, and the push trigger lists main and 034 only, so on main it is skipped too. FlexTools contract test still runs. Record the decision in the PR.

## Consistent

Of 35 decline sites in categories.py, none left a stray `return None` apart from the documented exceptions (gram_categories already-present, custom_fields stub, affix_templates tail, now returning `_outcome`) and the stems hole above. affix_templates skipped outcomes (`12649`, `12702`) are correct.
