# QC Report: GramTrans PR #92 (closes #55)

**Score: 88/100. Verdict: APPROVE.** There are no P0s. The P1s are follow-ups or evidence housekeeping, not blockers for this fix.

## Answers

**1. `_is_dotnet_object` (texts.py:77-100).**
- It does `import System` and then `isinstance(obj, System.Object)`. Both steps are wrapped, so it never raises.
- Pure-Python fakes, `MagicMock` and `SimpleNamespace` classify as False. If pythonnet is absent it returns False.
- The live test asserts `_is_dotnet_object(tgt_ms)` is True on a real multistring (integration test line 188), which covers the pythonnet proxy case. I did not run it.
- A fake classifies as .NET only if a test stubs `sys.modules["System"]`, or a fake subclasses a .NET type. Neither is present.
- A .NET object classified as fake could only occur if `import System` fails after pythonnet has been loaded. That is unlikely.
- Residual gap: no unit test asserts the helper itself returns False for the fakes. Tests 1-3 only show it indirectly.

**2. The NameError fix (transfer.py:4270-4283).**
- Yes, it is correct. `ws_handle` is now `tgt_handle`, so a failed `set_String` warns per slot and the loop continues.
- `filled_count += 1` sits after `set_String`, so a failed slot is not counted.
- The final Info line still reads "filled N", which is accurate, with a Warning per failure.
- Pre-existing quirk: the ImportError early `return` at line 4269 aborts the remaining slots and skips the summary line.

**3. Pattern-audit MED items.**
- **~2480-2490, confirmed.** Two `except Exception: pass` blocks.
  - The `PartOfSpeechRA = None` swallow can leave a non-null POS, contradicting the EXCL-LOSSY intent.
  - The `SlotsRC.Add` swallow silently drops slot wiring with no report.
- **~4035-4047, confirmed.** The `AttributeError` swallow around `ApplySyncableProperties` drops the write. When `src_env is None`, nothing is written at all. Both cases still log "PhEnvironment overwritten" at line 4050.
- **P1 or not.** A false success report on a write path is P1 by shape. It is narrow (`AttributeError` only) and latent, so it is not a blocker for #55. File a follow-up issue.
- **~2466 `ILexEntry(target)`.** This casts a project object and would raise in production. The branch is only reachable when `OwnerOfClass` is absent, so it is dead or latent. Rate it P2.

**4. Live test.**
- **FAIL vs skip.** Under `FLEXLIBS_REQUIRE_LIVE=1`, a missing backup or a failed open calls `pytest.fail`, and an init error raises. All of these fail rather than skip.
- **Hardcoded target.** `TARGET_NAME` is hardcoded at line 35. Recommend `os.environ.get("GT055_TARGET_NAME", "GT055 Target")`, with a refusal for protected names (Esperanto, Ejagham Mini, Sena 3, Target). `restore_target` overwrites whatever project carries that name.
- **Writes outside the throwaway.** None found. The source opens read-only and only the target is written.
- **Open-failure leak.** If the target open fails at lines 156-157, the source is never closed, because both opens sit before the `try`.

**5. Unit tests.**
- The non-.NET branch is well covered (tests 1-3), including the NameError regression.
- The .NET branch is covered through a stubbed `TsStringUtils` (test 4), plus the ImportError case (test 5).
- Not covered:
  - a .NET target where `MakeString` raises;
  - a direct assertion that the helper returns False for the fakes.

## Findings

**P1**
- transfer.py:4035-4050. Swallowed `AttributeError`, then a false "overwritten" report. File a follow-up.
- transfer.py:2482-2490. Silent swallows that drop slot and POS handling.
- The live evidence artifact `specs/<feature>/evidence/live-<task>.md` is not listed in the PR files, and its pre-state value is never printed. Add it, with `tests/live_status.json` showing `run_mode: live`.

**P2**
- Integration test line 35: add the env override and a protected-name guard.
- Integration test lines 156-157: move the opens inside the `try`.
- Unit tests: add the two missing cases above.
- transfer.py:2466: the `ILexEntry(target)` fallback.
- transfer.py:4260: `is_live` is recomputed per slot. Hoist it per field.

Pattern audit: present. I did not spot-check a HIGH sibling, because the PR lists none.
