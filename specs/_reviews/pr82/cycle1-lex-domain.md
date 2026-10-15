# PR #82 cycle 1 -- LEX domain review

(Saved by the main session: lex-domain had no Write tool. Main-session note on
the `en` question: there is no unconditional `en` skip in the code. In the live
test, `en` was simply an already-ACTIVE tag in Target, which `ws_create_state`
classifies as WS_ACTIVE. Any active tag is treated the same way.)

Summary: A PASS on the three states / FAIL on stored-but-inactive policy (BLOCKED
is stale against flexicon #250, where Create() activates). B PASS with additions.
Live-fixture candidates: Esperanto (es, id, pt, hbo, grc stored-but-inactive).

## A. WS state model -- PASS (states) / FAIL (policy for stored-but-inactive)
- The three states match FLEx. Active = CurVernWss/CurAnalysisWss (what GetAll() and the UI list). The LDML store (WritingSystemStore/*.ldml) holds more. Checked against fwdata and the store folders.
- BLOCKED is stale. The local flexicon CHANGELOG (issue #250) says Exists() is now active-only (BREAKING; it used to scan the whole store), and Create() reuses a stored-but-inactive tag and just activates it, with no duplicate. ExistsInStore() and Ensure() are new.
- So the `ws_create_state` docstring and the comment at api.py:937 are wrong for that flexicon. Exists() returns False for a stored-but-inactive tag, which falls through to WS_CREATE, so BLOCKED is unreachable.
- On an old flexicon, BLOCKED gives a data-loss warning where activation would have worked.
- A FLEx user expects activation: a stored-but-inactive WS is just an unticked one in the normal "add existing WS" flow. "Activate in FLEx and re-run" is a needless workaround.
- `en` skip: defensible only when `en` is already active in the target; treat it like any other tag (see main-session note above: the code already does).

## B. Drop severity -- PASS with additions
- The info/warning split is right: warning = a whole WS or reversal index lost; info = per-field drops. Listing [WARN] first is good.
- WS-create failure as a warning is correct (`ws_create_failure` already sets it). Reversal-index-level drops as warnings are correct.
- Other candidates, not checked in code: unmapped-WS content drops, and any whole-owner drop (an entire entry or rule lost). config_views already uses warning.
- A Preview warning is actionable only if there is a remedy. Today the remedy is "activate in FLEx", which is possible but unnecessary. After the fix, only genuine failures (e.g. an unparseable tag) deserve a warning, and Preview cannot predict those. Show stored-but-inactive tags as info ("will activate stored WS 'x'").

## Recommendations
- P0: Pin the pyflexicon floor to the release containing #250. Replace BLOCKED with a WS_ACTIVATE outcome via ExistsInStore()/Ensure(). Fix the docstring and the api.py:937 comment.
- P0: If the floor stays lower, check `hasattr(tgt_ops, "ExistsInStore")` and fail loudly rather than silently dropping content.
- P1: Show stored-but-inactive tags in Preview as info ("will activate").
- P1: Confirm `en` handling is not unconditional.
- P2: Audit other whole-entity drops for warning severity.

## Live fixture (read-only projects; store vs Cur*Wss in fwdata)
- Esperanto: active en, fr (analysis), eo (vernacular). Stored but inactive: es, id, pt, hbo, grc. Best candidate, but read-only, so reads only.
- Ejagham Mini: active en, etu. Stored but inactive: fr, es, zh-CN, etu-fonipa, etu-x-Eastern.
- Mbugwe LizzieHC practice: none (store is exactly the five active WSs).
- For a write test: restore Target and drop an .ldml (e.g. es) into its store without activating it.
