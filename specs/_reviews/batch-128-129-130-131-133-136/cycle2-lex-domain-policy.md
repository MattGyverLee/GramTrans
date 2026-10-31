# Cycle 2 FLEx-domain policy rulings (batch 128-129-130-131-133-136)

> Saved by the main session: the lex-domain agent had no Write tool and returned this ruling as its final message.
> **Basis (stated by the agent):** impl-128/129/130/133 reports plus FLEx UI behaviour. FLExToolsMCP was not called, and the code at the cited SHAs was NOT read (the agent had no git access).

**Overall:** PASS-WITH-FOLLOWUP

1. **#130, SlotsRC all-or-nothing on OVERWRITE: PASS.**
   - A partial slot set silently changes which affixes the template accepts. Slot membership drives parsing and template position, so a half-written set is a worse, hidden error.
   - Keeping the known-good target set, with a loud SLOT_MISSING report per slot, is what a user expects.
   - *Follow-up:* the report should say the whole SlotsRC write was skipped, not only list the missing slots. It should also point to the fix: include the slot's template, or the POS slots, in the run.

2. **#129, create-arm fallback into the DEFAULT ANALYSIS WS: PASS-WITH-FOLLOWUP.**
   - In principle, putting text from language X into the slot for WS Y is wrong, because in FLEx the WS tag is the identity of the text. It misleads spellcheck, sort, font and export.
   - The default analysis WS is the least harmful target. Descriptions are analysis-language prose, and users expect a visible Description over a blank one.
   - It is acceptable only because a drop is recorded.
   - *Follow-up:* make the drop message say explicitly that the text was relocated to WS Y. Consider skipping the field when the best alternative's source WS is a vernacular WS.

3. **#129, fingerprint ignores `[GT-Tag]:` residue for ALL reference decisions: PASS.**
   - The residue is GramTrans bookkeeping, not user content. Comparing it caused spurious UPDATEs. Idempotence requires ignoring it, and real text differences still count.
   - *Follow-up:* confirm the strip is anchored to the exact `[GT-Tag]:` line format, so a user-typed line that merely resembles it is not swallowed.

4. **#133, POS to inflectable-feature link written whenever the feature exists in the target by GUID: PASS.**
   - The correct reading is "link to what exists". Writing the link neither creates nor modifies the feature, and the link is a property of the POS, which is in scope.
   - Skipping it would leave the POS inflection-feature set unmatched to the source, which is the very defect #133 fixes.
   - *Condition:* features are never created or edited when INFLECTION_FEATURES is not selected. Add a test or doc line that states this boundary.

5. **#128, AFFIXES without STEMS now run the LexEntryRef C1/C2 passes: PASS.**
   - Affixes are lexeme entries, and complex-form and variant references legitimately live on them. A user selecting AFFIXES expects affix entries to arrive complete.
   - *Condition:* the passes touch only refs whose owner is an in-scope affix entry, and they never create stem entries. Component targets resolve only if they already exist in the target.
   - C3 (entry-type refs) is unchanged, so its CREATE-arm-only gap remains. This is not a regression, but note it.

6. **#128, text-only compare (formatting-only edits don't propagate): PASS-WITH-FOLLOWUP.**
   - Accept it for now. Formatting-only Summary edits are rare and low-stakes, and the create path and text-changing edits do preserve runs.
   - *Follow-up issue:* compare runs, including props and WS ids, with the same normalisation. Care is needed to avoid churn on re-runs. Not a blocker.
