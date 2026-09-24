# T127 and T128, measured read-only — and the larger defect the census cannot see

**Date:** 2026-09-18
**Tasks:** T127, T128 (feature 038, Phase 10 / US6), plus **T130**, a new row
**Method:** read-only `.fwdata` XML parse of `Mbugwe LizzieHC practice` (source)
and `GT038 T124 Mbugwe` (destination). **No project was opened, no LCM import
happened, nothing was written.**
**Pins:** source `3fb29a29…7cd5436d`, destination `0f46c9f5…25660360`.

> **REVISION 1, same day.** The first version of this document was measured with
> a probe that called `elem.clear()` on every element as `iterparse` fired its
> `end` event. `end` fires for children before their parent, so every `<Name>`,
> `<AUni>`, `<Members>` and `<objsur>` was emptied **before** the owning `<rt>`
> was read. Anything taken from an `rt` ATTRIBUTE (`class`, `guid`, `ownerguid`)
> was unaffected and stands; anything taken from a CHILD element read as empty.
>
> Two conclusions were wrong and are **struck below, not quietly edited**:
>
> 1. That T128's `MembersOC` query is "structurally blind" because `.fwdata`
>    records ownership only on the child. **False.** `<Members>` is serialised
>    with `<objsur t="o">` entries exactly as expected, the query works, and it
>    returns the right answer.
> 2. That T127's empty `Name` was empty in the source too. **False.** The source
>    name is present; the loss is real.
>
> The core T128/T130 finding was read from `ownerguid` attributes and is
> unaffected. It is now corroborated a second way, by the `<Members>` field
> itself.

---

## 1. T127 — CONFIRMED, and scoped to exactly one object of sixteen

`LexEntryType` / `LexEntryInflType`, source 16 → destination 16, every GUID
present on both sides.

| | source | destination |
|---|---|---|
| objects | 16 | 16 |
| carrying a `Name` | **16** | **15** |
| lost its `Name` in transfer | — | **1** |

The one is T127's object, `Periphrastic Form`
(`99e0cab9-f284-45fb-84a5-4cb2516d0bf4`):

| field | source | destination |
|---|---|---|
| `Name` | `en` = "Periphrastic Form" | **absent** |
| `Abbreviation` | `en` = "per." | **absent** |
| `Description` | absent | `[GT-Tag]: GT\|GT-20260918-131640\|…` |
| `ownerguid` | `bb372467-…` | `bb372467-…` (same) |

So the object was **created by this transfer** — it carries the run's own
`[GT-Tag]` stamp — with the correct GUID and the correct owner, and **none of
its multistrings were copied.** T127's reading of `None` in all six writing
systems and `BestAnalysisAlternative` rendering `'***'` is confirmed: the fields
are not merely unrendered, they are not there.

**Why the other 15 look fine is the informative part.** In the raw XML the lost
object is `IsProtected val="False"`; the canonical FLEx types around it are
`IsProtected val="True"`. The protected ones are starter content already present
in the destination by GUID, so their names were never this transfer's job. This
object is the one that had to be **created**, and the create path did not carry
its `Name`/`Abbreviation` across. That makes T127 a create-path multistring gap
rather than a rendering or writing-system problem — consistent with T127's own
elimination of both of those — and it predicts that the defect is invisible on
any project whose entry types are all canonical.

**A class-count census can never see this.** The row is 16 → 16, MATCHED.

## 2. T128 — the `-4` is genuine, and its query was fine

Read from the source's `<Members>` field and corroborated by every child's
`ownerguid`:

| | source | destination |
|---|---|---|
| `MoMorphAdhocProhib` total | 39 | 35 |
| …owned by a `MoAdhocProhibGr` | **37** | **0** |
| …owned by `MoMorphData` | 2 | **35** |
| `MoAdhocProhibGr` | 4 | 4 (GUID-identical) |
| group `Members` populations | 11, 7, 10, 9 | **0, 0, 0, 0** |

The four missing children, each owned in the source by a *different* group:

| missing child | source owner (`MoAdhocProhibGr`) | group size |
|---|---|---|
| `056d9746-06aa-4dfd-9558-c2ff666ecbd5` | `c2be0b70-c590-4ef2-81c1-c8298183e78f` | 9 |
| `068da9c3-992b-49ab-aeb2-5549dd292633` | `74c09f36-e9e6-4bd9-9e2d-a3819da25f3d` | 10 |
| `322ca437-46eb-4802-bbb4-66edad12856f` | `195fb089-cfab-4575-bdad-dbba690658a3` | 11 |
| `440b7774-7f1a-4f55-bbe9-88b7d700ed7d` | `253631c3-9789-4405-a638-83e039138068` | 7 |

**One per group, and in each group it is the first member listed in the source's
own `<Members>` sequence.** Over group sizes 9/10/11/7 that alignment is about
1-in-7000 under random loss. It is the first child the re-parent loop would
touch in each group.

## 3. T130 — the larger finding: every group arrives empty

Of 37 group-owned children in the source, **zero** are group-owned in the
destination. The 33 that survive were re-homed to `MoMorphData`, and all four
groups transferred GUID-identically as **empty shells** — confirmed twice over,
by the destination's `<Members>` fields (all `[]`) and by every surviving
child's `ownerguid`.

**The census reads this as green:**

    MoMorphAdhocProhib   39 -> 35   SHORTFALL (-4)
    MoAdhocProhibGr       4 ->  4   MATCHED

Both counts are correct. Neither row can express that 33 objects changed owner
or that every group is now empty. With T127 above, T123(b)'s subclass
misclassification and T123's nesting demotion, that is **four** defects on this
feature's rows invisible to a class count, and the strongest case yet for the
census-contract gap T127 asks to raise with T081: **non-count assertions**. A
grammar in which every ad-hoc prohibition group is empty is broken in a way that
two near-green rows describe as `-4`.

## 4. Mechanism — one hypothesis that explains every figure

`Lib/categories.py:4677-4701`, the T011 group re-parenting branch:

```python
tgt_child = _find_target_obj_by_guid(
    list(morph_data.AdhocCoProhibitionsOC), child_guid)
if tgt_child is not None:
    try:
        morph_data.AdhocCoProhibitionsOC.Remove(tgt_child)   # owning collection
        new_rule.MembersOC.Add(tgt_child)
    except (AttributeError, TypeError):
        pass
```

**`Remove` on an LCM *owning* collection is a disposal, not a detach.** This
repository already treats it that way at both of its other call sites, and there
are only two:

* `categories.py:9225` — `entry_ie.AlternateFormsOS.Remove(rule_obj)`, followed
  immediately by an explicit `ICmObject(rule_obj).Delete()`.
* `categories.py:15592` — `contexts_os.Remove(member)`, in an orphan-cleanup loop.

Line 4696 is the **only** site in the codebase that uses `Remove` as a *move*.

Predicted per group: `Remove` disposes of the first child reached;
`MembersOC.Add` is handed a disposed object and raises something outside
`(AttributeError, TypeError)`; that escapes the inner `except`, escapes the outer
`try` (same narrow tuple), and aborts the group's `execute_action`, so its
remaining children are never re-parented and stay where they were created.
Over four groups: **−4 objects, 0 re-parented, 4 empty groups** — every observed
number falls out of it, including which child is lost.

**Ordering is not the cause, and saying so matters** because it is the obvious
first suspect. `adhoc_compound_rules_enumerate_source` (`categories.py:4357`)
does sort `MoAdhocProhibGr` last, and the `-4` is itself the proof that
`_find_target_obj_by_guid` **succeeded**: had the children not existed in the
target yet, nothing would have been removed and all 37 would have survived under
`MoMorphData` with no shortfall at all.

**This is a hypothesis, not a measurement.** It is consistent with every figure
above and with the codebase's own use of `Remove`, but no run was performed and
no LCM call was made from this document. Confirming it — and any fix — requires
a live restore-bounded transfer against a write path suspected of **disposing
owned objects**, which is a human's call.

## 5. Correction to the record

`_recurse_adhoc`'s T123 comment (`categories.py:4285-4290`) says:

> LATENT on the sanctioned corpus: `MoAdhocProhibGr` source_count is 0 on all
> three T078 pairs, so this is fixed to be correct the day a project with a
> grouping node arrives, and is NOT claimed as a measured recovery.

That was accurate when written. **It is no longer latent.** The mbugwe source
drift T128/T129 recorded (`fb6aadab…` → `3fb29a29…`) brought four grouping nodes
and 37 group children with it, and the path now runs on every mbugwe transfer.
The enumeration half the comment describes works correctly — all 39 are
enumerated and 35 are created. The placement half does not.

## 6. Note on the instrument

The parser bug in revision 0 of this document is the fourth instrument failure of
this spurt, after file:line citations read from the wrong tree, a pinning test
that SET the value it then asserted, and the unenforced source pin T129 closed.
It was caught by sanity-checking a surprising result against the raw XML before
acting on it — the result "all 16 entry types are nameless in both projects" is
not a plausible state for a real FLEx project, and that implausibility, not the
code, is what exposed it. The corrected probe and its output are committed under
`probes/t128/` so the next reader re-runs an instrument rather than trusting a
table.
