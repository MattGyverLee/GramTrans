# cycle1 -- lex-domain ruling (batch 141-142-144-145-146-147)

> Saved by the main session verbatim from the lex-domain hand-back (the lex-domain agent has no Write tool).
> Basis noted by the agent: Grep hits from the impl reports only, not full reports or code.

## A. Link to an item this run will create -- NEEDS HUMAN DECISION (exact wording); split-count is BLOCKING for #147/#160 as written
Rationale: "already in the target" would be false for these items, so they must read differently from existing-item links.
Rule: Link means the item exists now; a link to something this run creates is labelled as such.

- (i) Itemized row:
  `Link  <Field> '<name>' {<guid>}  (<n> senses)  -- links to the item created above in this run`
- (ii) Collapsed count line: count planned-create links separately, in two lines; omit the second when K = 0.
  - `Link  <Field>: N items already in the target  (M senses)`
  - `Link  <Field>: K items created by this run, linked from later references  (P senses)`
  - Keeping the lines separate is the point: a user must not read K new items as K existing ones.
- (iii) #144 note: `(New in this run: created once, and the other references link to it.)`
  - Keep it on multi-owner Create rows only; drop "the other references link to it" when the row has one owner.

## B. LINK collapse threshold of 25 -- YES, NON-BLOCKING
Below the cap a FLEx user can audit every link by name and GUID; above it a per-field count with the sense count is more
useful than the first 25 sorted rows. 25 matches the existing `_LIST_ITEM_LIMIT` and the "+N more" convention elsewhere in
Preview. Unconditional collapse would hide which items get linked, and the existing itemized-Link test depends on that detail.
Condition: the collapsed line must still show the planned-create count from A(ii).

## C. Empty LexRefType left when all its relations are dropped -- NON-BLOCKING (follow-up)
Announcing the create in Preview satisfies Principle III for this batch. Reordering Move's guards is a write-path change needing
the full crew cycle and the live-LCM gate (`FLEXLIBS_REQUIRE_LIVE=1`).
- Follow-up issue: create the type lazily, only when at least one relation survives the guards; afterwards Preview must stop
  announcing the create for types with no surviving relations.
- Until then Preview should keep an explicit note, e.g. `Create RelationType 'X' (no relations will be linked: all dropped)`.
