# QC Report — Cycle 5 (feature 025-full-reversals)

**Date:** 2026-07-12 | **Quality Score:** 78/100 | **Status:** ISSUES

## Pattern-Audit Gate
N/A — this is a feature-cycle QC pass over new US1-3 code, not a bugfix PR. Gate does not apply.

## P0/P1/P2 Issue List

**P0-1 (fail-soft posture / contract violation):** `config_views.py:115-129 resolve_config_dirs` calls `os.makedirs(exist_ok=True)` on **both** the source and target `ConfigurationSettings/Dictionary|ReversalIndex` dirs. `plan_config_views` (line 311-312) calls it for `src_project` too, so Preview mutates the **source** project's directory tree — not just target, and not sanctioned by contract `config-view-copy.md:13` ("create target subdirs if missing" — target only). This directly contradicts `preview.py`'s module docstring ("READ-ONLY on both source and target — MUST NOT mutate anything") and `plan_config_views`'s own docstring ("Decision pass... No writes."). `tests/unit/test_preview_no_writes.py`'s `_FakeProject` never exercises this path because its `_project_dir` raises `ValueError` before reaching `makedirs` — a real coverage gap, not a passing safety net.

**P0-2 (docstring accuracy / Principle III):** `render_reversal_decisions`/`render_config_view_records` (preview.py:403, 450) are dead code in production — `Lib/ui/main_window.py` never calls either (confirmed by grep). `categories.py:4028`'s docstring for `reproduce_reversal_entries` states writes happen "after the plan has already been shown to the user (Principle III)" — false as currently wired. `models.py:718,729` repeats the same false claim.

**P1-1:** `reproduce_reversal_entries` (categories.py:4034) recomputes `plan_reversals` from scratch at Move time rather than reusing `RunPlan.reversal_decisions` from Preview — consistent with this codebase's existing "recompute" convention for relations, but doubles the walk and risks Preview/Move divergence if source state changes mid-session. Not unique to 025; flag as tech debt.

**P1-2:** `_target_ws_ids` is duplicated near-verbatim in `reversals.py:133-142` and `config_views.py:141-145` (DRY violation, low risk, cross-module).

**P2-1:** `import dataclasses` performed locally twice (reversals.py:345, 753) rather than at module top — minor style.

**P2-2:** `_rules_missing_ref_warnings` (preview.py:486-655) is long/deeply-nested with several bare `except Exception`/`except: pass` — pre-existing (018-rules-page), not part of this diff, noted only.

## 5-Item Adjudication Table

| # | Item | Verdict | Rationale |
|---|------|---------|-----------|
| 1 | US2 decide `source=None` vs apply `target=target_project` | **ACCEPT** | `_fields_identical` (references.py:513-528) builds each side's fingerprint from `_project_handle_to_id(source/target)`. At decide-time `target` is the index (no `.WritingSystems`) so its resolver is always `{}`; passing a real `source` project there would make one side Id-keyed `((id,text),)` and the other positional `(text,)` — structurally incomparable, forcing spurious UPDATE (confirmed empirically per T021 note). `source=None` keeps both sides on the same positional fallback — correct. At apply-time, `apply_reference`'s UPDATE/CREATE arms need `target.PossibilityLists`/`target.Cache`/`target.GetFactory`, which only a project exposes; the *action* (LINK/CREATE/UPDATE/DROP) was already fixed at decide-time, so passing the real project+source here only affects how a decided write is WS-keyed, not which action fires. Asymmetry is deliberate and does not corrupt category selection. |
| 2 | T021 per-index tripwire (LangProject never touched) | **ACCEPT** | `_apply_pos_decision`'s `apply_spec.target_list_path` (reversals.py:757) is a closure ignoring its argument, always resolving to the already-bound `target_index.PartsOfSpeechOA`. Even if misused with the static spec against a project, `project.PartsOfSpeechOA` doesn't exist and fails soft rather than silently writing `LangProject`. Enforced structurally, not just by convention; `test_target_list_binds_to_index_never_to_lang_project` locks it. |
| 3 | UI-wiring gap (render_* uncalled) | **MUST-FIX** | Grep-confirmed no call site in `main_window.py`. `RunReport`/stats panel only surfaces `dropped_items` (missing-refs), never the Add/Link reversal-entry plan or the config-view Add/Overwrite/Skip list — these are real bulk writes (`reproduce_reversal_entries`, `apply_config_views` at transfer.py:474,495), not drops. Nothing else channels this plan to the user. Docstrings claiming Principle III compliance are currently false. |
| 4 | US3 Preview-mutation (makedirs) | **MUST-FIX** | Worse than the narrow "target only" framing in cycle4-programmer.md: `plan_config_views` calls `resolve_config_dirs` on **both** projects, so Preview creates directories on the **source** project too — unsanctioned by contract and by preview.py's own explicit guarantee. Needs a real read-only path-computation split (compute intended path, defer `makedirs` to apply). |
| 5 | US3 `ConfigView` missing_refs channel | **ACCEPT** | Confirmed single path: `_scan_missing_refs` -> `ConfigViewRecord.missing_refs` -> folded into `_dropped`/`dropped` in both `preview.py:344-346` and `config_views.py:369-370`, rendered generically by `report.py` (no owner_kind allow-list). No separate channel. |

## Final Assessment
**Recommendation:** FIX ISSUES — remediate P0-1 and P0-2 (items 3 & 4) before Polish; items 1, 2, 5 stay green.
**Reviewed By:** lex-qc (cycle 5)

---

Files reviewed (all read-only, no edits made): reversals.py, config_views.py, preview.py, references.py, categories.py (~3995-4049), models.py (~700-731), residue.py, transfer.py (grep), ui/main_window.py (230-329), tests/unit/test_preview_no_writes.py (grep), contracts/{reversal-walk,reversal-category-resolution,config-view-copy}.md, reviews/{cycle3,cycle4}-programmer.md.
