# PR #73 live-LCM verification (cycle 1)

Worktree GramTrans-ws-path, branch fix-ws-path @ 55b3fd0. flexicon 4.13.0 resolves to
D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py (not site-packages).
All runs: FLEXLIBS_REQUIRE_LIVE=1, standalone driver scripts (not pytest), so tests/live_status.json
was not produced; liveness is shown by real Target reads/writes below. Target restored from
`backups\Target 2026-07-06 0218.fwbackup` via harness restore.restore_target before EVERY scenario
and once more at the end. Only Target was written. Sources: `Mbugwe LizzieHC practice`, `Ejagham Mini` (RO).
Drivers (not committed): scratchpad drive.py <A_nat|A_inactive|A_fault|BC|C2|B>, driveD.py.
Command pattern: `python <scratchpad>\drive.py A_inactive` (full selection, STEMS included, api.initialize_run ->
bind_target -> compute_preview(ws_mapping=...) -> execute_move).
Restored Target has WS [en, etu] only. Mbugwe has swh, mgz, mgz-fonipa-x-emic/etic.

## (a) Writing systems (#44) -- PASS
Mapping: mgz->etu, en->en, swh->swh(create), mgz-fonipa-x-etic(create).
* A_nat (natural): plan entries swh/etic create_in_target=True. Post-run Target WS (re-read, GetAll =
  active) = [en, swh, etu, mgz-fonipa-x-etic]. No WritingSystem drop. Move completed.
* A_inactive (natural-staged): copied Mbugwe's mgz-fonipa-x-emic.ldml into Target's WritingSystemStore
  after restore (stored but not active) and mapped emic create. swh and etic created+active; emic NOT active
  afterwards and RunReport.dropped_items contains:
  `WritingSystem | mgz-fonipa-x-emic | create_in_target | item_guid=mgz-fonipa-x-emic | target writing system
  'mgz-fonipa-x-emic' could not be created (ArgumentException: ... id already exists ...)`. Move completed (574 drops total vs 573).
  Note the stored-inactive case is detected only because Create() raises; the explicit "stored but not active"
  branch text ("activate it in FLEx and re-run") was NOT what surfaced (Exists() returned False for it), but
  the outcome (reported drop) is correct.
* A_fault (fault-injected): Create patched to raise for mgz-fonipa-x-etic. Produced WritingSystem drop
  "RuntimeError: injected create failure"; Move completed; Target WS = [en, etu]. CAVEAT: my wrapper also
  broke swh (AttributeError ... writeEnabled) -- a harness artifact of the monkeypatch, not a src defect;
  swh creation is proven by A_nat.

## (b) Reversals (#46) -- PASS, FAULT-INJECTED (alt injection)
No natural case exists: scanned all fwdata with reversal entries; every Mini/Mbugwe reversal entry has a single
`en` alt (only Yi Sichuan, out of allowed sources, has multi-alt). Source Ejagham Mini; patched
reversals._reversal_form_alts to add alt `fr` (absent in Target) and `etu` (present) per entry.
Report: 144 `ReversalIndexEntry | ReversalForm | item_name=fr | item_guid=fr | writing system 'fr' absent in
target` drops (134 top-level decisions + sub-entries); Move completed (no ArgumentNullException abort).
Target post-state: reversal index en has 134 entries; sample entries carry en and etu alts, e.g.
{'en':'strength','etu':'TEST_etu_strength'}; no fr alt. Lexicon entries 252.

## (c) Config views (#53) -- PASS
Source Mbugwe, mgz->etu (BC run, restored before). No config-view drop mentions 'mgz' (only absent
unmapped swh / mgz-fonipa-* and custom fields, which are genuinely absent). Target
ConfigurationSettings/Dictionary/{Root,Lexeme,Hybrid}.fwdictconfig: diff vs source shows only
`<Option id="mgz" ...>` -> `<Option id="etu" ...>` (Root 419 lines, Lexeme 206, ReversalIndex/swh 16); no stray
mgz-only ids remain (remaining mgz hits are unmapped mgz-fonipa-*). Root `writingSystem=` attribute exists only
on reversal configs, so C2 run mapped swh->sw(create): Target ReversalIndex/swh.fwdictconfig root changed
`writingSystem="swh"` -> `"sw"` and 16 `<Option id="swh">` -> `"sw"`; Target WS now includes `sw`.
Existing target en.fwdictconfig was overwritten with a .gtbak backup (expected OVERWRITE).

## (d) phase2_interactive_move (#69) -- PASS (headless, real Target)
Drove gt.phase2_interactive_move(target_handle, report, True, "Mbugwe LizzieHC practice", ws_resolver=double)
with Ejagham Mini used only to build the bind stub. Resolver: mgz MAP etu; swh/etic/emic CREATE.
Observed: `_ensure_writing_systems` ran (instrumented wrapper) -> returned [etic, swh], failures [emic]
(emic staged stored-inactive again); report.Info "Created 2 target writing system(s)"; report.Warning "target
writing system 'mgz-fonipa-x-emic' could not be created"; returned RunReport.dropped_items has the
WritingSystem record. Target WS afterwards [en, swh, etu, mgz-fonipa-x-etic].
Harness gotcha (not a defect): gramtrans.py imports flat modules (`models`, `ws_mapping`), so enum
WSChoice from `gramtrans.Lib.models` compares unequal; my first run silently folded NO CREATE choices
until I built choices from the flat `models`. Dual-module enum identity is a latent trap for any non-host caller.

## Defects in src
None found affecting #44/#46/#53/#69.
Observation: gramtrans.py:586 `from api import ...` is a flat import (works only with Lib on sys.path, as in host).
Mock suite was not run (supplementary, not requested).
