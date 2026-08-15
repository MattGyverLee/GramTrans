# Quickstart / Validation Guide: Complex Forms & Variants (027)

Proves feature 027 end-to-end: `LexEntryRef` complex-form / variant relationships are
reproduced on the target (issue #30 fix; issue #28 LexEntryRef `0 → N` acceptance).

## Prerequisites

- Implementation worktree `../GramTrans-027-complex-forms-variants` on branch
  `027-complex-forms-variants`, built against `main` (which carries the issue #28 layer-1/2
  fixes).
- flexicon (`pyflexicon>=4.1`) installed (`pip install -e D:/Github/_Projects/_LEX/flexlibs2`).
- For the live proof: FLExToolsMCP active, a **freshly-restored** disposable target
  (`Target` or `Ejagham Full GT-Test`), and `Ejagham Mini` as source. **Attended only** —
  never under an unattended loop.

## 1. Offline suite (autonomous, gating)

```powershell
cd D:/Github/_Projects/_LEX/GramTrans-027-complex-forms-variants
python -m pytest tests/unit/test_027_entryref_reproduction.py tests/unit/test_027_entry_type_resolve.py tests/unit/test_027_never_silent.py tests/unit/test_phase3c_post_pass_a.py -q
```

**Expected**: all pass. Covers C1–C7 (create, wire, resolve, drop-policy, parity), the fake
`ICmObjectRepository` fallback branch, and the `_Bare`/`_Typed` cast tripwire. Then the full
suite for non-regression:

```powershell
python -m pytest tests/unit -q
```

**Expected**: green modulo the one documented pre-existing baseline failure
(`test_wizard_pos_grammar_wiring::test_plan_emits_pos_action_for_picked_pos`).

## 2. Preview parity (read-only, autonomous)

Run `build_run_plan` (Preview) over `Ejagham Mini` and assert:
- 6 variant `LexEntryRef` reproduce-decisions (Add) surface, each naming its component.
- 0 writes to source or target (byte-unchanged; Principle III).
- The Preview drop set equals the Move drop set for the same selection (C5).

## 3. Live `0 → N` proof (attended, needs_human) — SC-001

Driver: `debug/run27_live.py` (restore → diagnose → Move → re-Move → diagnose), modeled
on `debug/run031_live.py` + the `run28_live.py` FLExToolsMCP re-resolution probe.

Steps (all attended):
1. **Restore** the target from a clean backup (0 `LexEntryRef` on target). Confirm no FLEx
   GUI open, no `.lock`.
2. **Diagnose (pre)**: confirm source `Ejagham Mini` has 6 entries each with 1 variant
   `LexEntryRef` (1 ComponentLexeme; comp_total=6, prim_total=0); target has 0 `LexEntryRef`.
3. **Move** `Ejagham Mini → Target` (full selection incl. STEMS), code @ the 027 branch.
4. **Diagnose (post) via FLExToolsMCP re-resolution** (authoritative, correct casts —
   `ILexEntry(obj).EntryRefsOS`, `ILexEntryRef(ref).ComponentLexemesRS`): the target now
   holds **6 `LexEntryRef` objects** (up from 0), each `RefType`=variant, each with its 1
   component lexeme wired, and each carrying its resolved variant-type (SC-002).
5. **Re-Move** and re-diagnose: still 6 refs / 6 memberships, **0 duplicates** (SC-003).

**Pass criteria**: SC-001 (`0 → 6` LexEntryRef), SC-002 (variant-type wired), SC-003
(idempotent), SC-004 (out-of-closure refs reported as drops, 0 silent).

## 4. Deferred — US3 complex-form live proof (tracked follow-up)

`Ejagham Mini` has 0 complex-form entries, so `RefType`=complex-form cannot be live-proven on
the standard pair. US3 ships with offline coverage (§1). Its live proof is deferred to a
constructed complex-form fixture and tracked as a follow-up issue (parallel to issue #31's
MSA→slot live source). Record the follow-up in `STATUS.md` and file it on merge.

## Evidence to capture

- Offline suite output (pass counts, cast tripwire RED-when-reverted).
- Preview byte-unchanged proof + Preview/Move drop-set equality.
- Live pre/post FLExToolsMCP diagnosis (`LexEntryRef 0 → 6`, memberships, re-Move 0-dup),
  written to `specs/027-complex-forms-variants/verification-log.md`.
