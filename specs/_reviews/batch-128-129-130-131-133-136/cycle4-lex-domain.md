# Cycle 4 FLEx-domain ruling, batch 128-129-130-131-133-136

> Saved by the main session. The lex-domain agent has no Write tool and returned this as its final message.
> **Basis (stated by the agent):** the cycle 2 ruling and the cycle 3 #133 report only. It did not read `references.py` or the PR #158 report, so rulings (a) to (c) rest on the behaviour described in the brief plus FLEx conventions. FLExToolsMCP was not called.

**Blocking merge:** none.

## Ruling A (PR #158)

**(a) PASS (follow-up only).**
- A FLEx user would rather see a Description or Name in the default analysis WS than a blank field. That matches the cycle 2 reasoning.
- "Relocated" is the right disposition, not a loss, because the text survives.
- It is still a fidelity change. The WS tag is the text's identity, so the report must show source WS X, target WS Y and the field.
- It must not be counted as lossless. A separate "relocated" line item is the honest middle ground.

**(b) PASS (follow-up only).**
- Skipping vernacular text is correct. Putting vernacular text into an analysis slot corrupts the data's language identity and its spellcheck.
- The same reasoning extends to analysis WSs in a different script or language family, but the test should be looser:
  - Relocating from a national-language analysis WS into English is ordinary FLEx practice. For example, a Swahili or Indonesian gloss going into English is far better than nothing.
  - Future refinement: skip when the script differs from the target default analysis WS, because such text renders wrongly and can't be read.
  - Do not use language family as the test. A cheap script check is the only extra rule worth adding.
- Not blocking.

**(c) Follow-up only.**
- `relocated:` records should be reported separately from drops, so a user triaging losses doesn't have to wade through relocations.
- A distinct category or report section is enough. This is a presentation issue.

## Ruling B (PR #152)

**(d) Acceptable for merge (follow-up only).**
- Each named pair is reported as a drop, so the loss is loud, not silent.
- The user did not pick that POS, so it falls outside the requested scope.
- **Consequence:** real but limited.
  - A closure-created POS arrives with an empty Inflection features list in the Category tab.
  - Subcategories that inherit from that parent POS can lose inherited inflectable features.
  - The feature chooser for stems of that category can then offer fewer features.
- Nothing is corrupted, and templates and slots are unaffected. The user can fix it by re-running with the POS picked directly.
- File "link closure-created POS" as a follow-up issue.

**(e) No human decision needed.** The drop-and-report behaviour is safe by default. Linking closure-created POS is a feature improvement, not a merge condition.
