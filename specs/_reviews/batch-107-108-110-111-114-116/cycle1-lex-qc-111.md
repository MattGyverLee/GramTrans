# cycle1-lex-qc-111

> Saved by the main session: lex-qc has no Write tool and returned this text verbatim.

PR #120 (closes #111): Score 84/100. Verdict APPROVE for #111's scope, with P1 follow-ups. Gate 2 live evidence is in impl-111.md and shows a mutation giving WRITE_FAILED 128 and a clean run giving LINKED 128, with pre/post pairs 0/128. I did not verify the artifact path `specs/<feature>/evidence/live-*.md` exists, and no live run was done by me.

**Q1: read-back comparison.** Correct. categories.py:11159-11162 compares `p is slot` OR a GUID set built from `_guid_str_from` (ICmObject cast, lowercased). Identity is only an offline-fake fast path. GUID is the real test, so unstable pythonnet proxies are harmless. The cast slot (:11032) differs from the proxies read back, which the GUID path covers. Minor: if `slot_g` is empty, :11034 falls back to the source GUID. That is fine for GUID-preserved slots.

**Q2: precedence and consumers.** Correct, no breakage found. `_affix_slot_link_block` (report.py:905-949) counts WRITE_FAILED in `attempted`, not in LINKED, and not in `not_in_run`. It lists it in `failures` (:939-940) with `getattr` defaults. The console row is at report.py:2568. The only other readers of `affix_slot_links` are models.py, report.py and transfer.py:694/1067, and none branch on the outcome. The model invariants (models.py:3255-3278) are consistent. The existing tests at test_038_affix_slot_links.py:159-188 pin by_outcome to {LINKED, SLOT_MISSING}, so they are unaffected.

**Q3: Add raises but the slot is present on read-back.** P2. Read-back is the source of truth, so LINKED is right. The swallowed exception should at least be `log.debug`/`warning`ed at categories.py:11049. It is not a correctness issue.

**Q4: OVERWRITE sibling.** Confirmed on c088d16 (main) at transfer.py:4204-4209. `new_ia.SlotsRC.Clear()` is followed by `Add(tgt_slot)`, with no try, no read-back, and silent drops for slots absent from `target_slots_by_guid`. A failed write therefore deletes existing membership. This is P1 as a follow-up issue, not a blocker for #120, because it is a separate code path, a separate report channel and needs its own live proof. File the issue now, labelled `bug` and data-loss.

**Q5: `_wire_msa_infl_feats` / `_wire_prod_restrictions`.** P2 follow-up. They are still unguarded at categories.py:11101 and :11136. A raise from either still reaches the log-only `_ensure_171_subpass` handler. This is pre-existing and orthogonal. On the tail path a raise now loses only those two passes, not the SlotsRC records, which is an improvement.

**Q6: test_issue31 edit.** Safe. At :143 `startswith("GT-Sandbox-") and != SOURCE_NAME` still excludes Target, Esperanto and the real projects. The env var is the only new input. Lines 53 and 142 are verbatim `TARGET_NAME = "GT-Sandbox-31"` and `== "GT-Sandbox-31"` in the fix-107 and fix-110 worktrees. #125 or any sibling touching those two lines will conflict textually, and the resolution is trivial. I did not see #125's own diff.

**P0:** none.

**P1:**
- File an issue for the OVERWRITE `Clear()+Add` path (transfer.py:4204).
- The four `_ensure_*` safety nets only log (transfer.py ~177 onward). Follow-up.

**P2:**
- categories.py:11049: log the swallowed Add error when the read-back shows the slot present.
- :11063: the inline `import logging` is stylistically off; use a module logger.
- categories.py:11034/:11044: empty-GUID equality could false-positive "already present". Pre-existing.
- DEPENDENCY_UNRESOLVED is a semantically loose Skip reason for WRITE_FAILED. Acceptable and documented.
- models.py: WRITE_FAILED is described as additive to the artifact schema (specs/035-fullsweep-fidelity/contracts/artifact-schema.md), which should list the new outcome and the two new keys.
