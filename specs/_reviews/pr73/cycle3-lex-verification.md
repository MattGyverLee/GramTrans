# PR #73 follow-up (PR #79) live verification, cycle 3

Worktree GramTrans-ws-followup, commit 7cd69fb (confirmed, not bb7208e). FLEXLIBS_REQUIRE_LIVE=1.
Cycle 2 driver (scratchpad drive2.py/drive3.py), source Mbugwe LizzieHC practice read-only. Target
restored from `Target 2026-07-06 0218.fwbackup` before every scenario and at the end (final restore
confirmed: WS store en, etu; ReversalIndex en only). Only Target written.

## 4 Reversal/analysis rename swh->sw on create: PASS
(a) Target Dictionary Root/Lexeme/Hybrid: `Option id="swh"` = 0 in BOTH WritingSystemOptions and
WritingSystemAndParaOptions (sw: Root 510+40, Lexeme 286+24, Hybrid 424+32; matches source swh counts
550/310/456). Normalised compare vs source: identical except Option ids (multiset equal, 8008 lines).
(b) Reversal unchanged from cycle 2: sw.fwdictconfig present, swh absent, 16 `Option id="sw"`, 0 swh;
Target WS [en, sw, etu]; 573 drops (same as cycle 2).
The cycle 2 FINDING (stale swh in WritingSystemAndParaOptions) is FIXED.

## (c) Fault injection, WritingSystemAndParaOptions-only id: PASS
Staged COPY of source Root.fwdictconfig with `Option id="zzq"` inserted in one
WritingSystemAndParaOptions block only (no target WS). Plan note and RunReport list
`ConfigView | Root.fwdictconfig | writingSystem | zzq | writing system 'zzq' absent in target`;
drops 574 (573 + 1). Source project untouched.

## 1 Regression A_nat: PASS
Target WS [en,swh,mgz-fonipa-x-etic,etu]; 573 drops; Root/Lexeme/Hybrid diffs 838/412/676 lines, 0 non-Option-id
lines (identical to cycle 2).

## 5 Stored-inactive WS: PASS (unchanged)
574 drops; `WritingSystem | mgz-fonipa-x-emic | create_in_target` drop present (ArgumentException path, as cycle 2).

Mock suite not run.
