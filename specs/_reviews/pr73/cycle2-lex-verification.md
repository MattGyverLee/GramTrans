# PR #73 follow-up (draft PR #79) live verification, cycle 2

Branch fix-ws-followup tree, commit bb7208e. FLEXLIBS_REQUIRE_LIVE=1. flexicon resolves to
D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py. Standalone driver (scratchpad drive2.py, not committed),
flat `models` module for WSMapping/WSChoice-kind values. Target restored from
`Target 2026-07-06 0218.fwbackup` (harness restore_target) before EVERY scenario and at the end.
Only Target written. Sources (Mbugwe LizzieHC practice) read-only. Fault-injection used a COPY of
the source ConfigurationSettings (scratchpad stage_SWAP / stage_COLL, compute_config_dirs patched);
no source project file was touched, so nothing to revert.

## 1 Regression A_nat + BC (mgz->etu): PASS (natural)
A_nat: Target WS [en,etu] -> [en,swh,mgz-fonipa-x-etic,etu]; 573 drops (same as cycle 1). Target
Dictionary Root/Lexeme/Hybrid diff vs source: 838/412/676 changed lines, 0 lines other than
`Option id` mgz->etu (419/206/338 options, equals the mgz count under WritingSystemOptions). Reversal en
OVERWRITE with .gtbak, as before.

## 2 Swap (mgz->etu, etu->mgz): PASS (FAULT-INJECTED)
No natural case. Staged Root with `etu` Option after `mgz` (isEnabled mgz=true, etu=false) in 2 lists.
Target: `etu true, mgz false` in those lists (exchanged, not cascaded); other 417 lists plain mgz->etu;
no corruption, no stray mgz. Chain not run separately (the swap is the harder simultaneous case; unit-tested).

## 3 Collision (mgz->etu, etu already present): PASS (FAULT-INJECTED)
Same staging, mapping mgz->etu only. Target: one `etu isEnabled="true"` per list (enabled merged),
Root total etu Options 419 (== unstaged result), mgz 0. Plan/report carry ConfigView record:
"duplicate writing-system option 'etu' merged (2 -> 1) after renaming" (x2 lists-files, Root.fwdictconfig).

## 4 Reversal rename swh->sw create: PASS for the stated claim (natural), with a FINDING
Target ReversalIndex: sw.fwdictconfig present, swh.fwdictconfig absent; root writingSystem="sw"; 16
`Option id="sw"`, 0 "swh" left; byte-exact vs source with only those substitutions. Target WS [en,sw,etu].
FINDING (regression vs #73 behaviour): Dictionary files keep `swh` in `<WritingSystemAndParaOptions>`
(analysis lists; Root 40, Lexeme 24, Hybrid 32 stale `Option id="swh"`). The new scoped rewrite and
_scan_missing_refs only recognise `WritingSystemOptions`. Rename of an ANALYSIS ws leaves these dangling and
no drop is reported for them. Vernacular (mgz) unaffected (none in those blocks). Suggest including
WritingSystemAndParaOptions in both scan and rewrite.

## 5 Stored-inactive WS (emic ldml staged): PASS (natural-staged)
RunReport has `WritingSystem | mgz-fonipa-x-emic | create_in_target` drop (574 total vs 573); swh/etic
created, emic not active afterwards; Move completed. Reason text came from Create() raising
(ArgumentException id already exists), not the new "stored but not active" wording (Exists() path not hit).

Target restored at end. Mock suite not run.
