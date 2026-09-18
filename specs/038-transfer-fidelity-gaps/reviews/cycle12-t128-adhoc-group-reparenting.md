# T128 acceptance — and the larger defect the census cannot see

**Date:** 2026-09-18
**Task:** T128 (feature 038, Phase 10 / US6), plus a NEW row this measurement opens
**Method:** read-only `.fwdata` XML parse of `Mbugwe LizzieHC practice` (source)
and `GT038 T124 Mbugwe` (destination). **No project was opened, no LCM import
happened, nothing was written.**
**Pins:** source `3fb29a29…7cd5436d`, destination `0f46c9f5…25660360`.

---

## 1. T128's specified query cannot answer T128's question

T128's acceptance was:

> destination-side `MembersOC` GUID diff for mbugwe `MoMorphAdhocProhib`

Run as specified — reading each `MoAdhocProhibGr`'s `Members` field from the
**owner** side — it returns **empty on both projects, for all four groups**, and
therefore reports "no members lost".

That is a **false negative produced by the query, not by the data.** `.fwdata`
serialises owned-collection membership on the **child**, as `ownerguid`, not as
`<objsur t="o">` entries under the parent's field. An owner-side read of an
owning collection is structurally blind, and it returns "nothing lost" at the
exact moment every group has lost every child it had.

Re-run from the child side, the picture inverts completely. **Recorded here
because the query was specified in a committed task row and will be re-run.**

## 2. The measurement, child side

| | source | destination |
|---|---|---|
| `MoMorphAdhocProhib` total | 39 | 35 |
| …owned by `MoAdhocProhibGr` | **37** | **0** |
| …owned by `MoMorphData` | 2 | **35** |
| `MoAdhocProhibGr` | 4 | 4 (GUID-identical, 4/4) |
| destination-only objects | — | 0 |
| GUID-identical overlap | — | 35 |

## 3. Two findings, and the second is much larger than the first

### 3a. T128's `-4` is genuine, and it is one child per group

Missing, all four `MoMorphAdhocProhib`, each owned in the source by a *different*
one of the four groups:

| missing child | source owner (`MoAdhocProhibGr`) |
|---|---|
| `056d9746-06aa-4dfd-9558-c2ff666ecbd5` | `c2be0b70-c590-4ef2-81c1-c8298183e78f` |
| `068da9c3-992b-49ab-aeb2-5549dd292633` | `74c09f36-e9e6-4bd9-9e2d-a3819da25f3d` |
| `322ca437-46eb-4802-bbb4-66edad12856f` | `195fb089-cfab-4575-bdad-dbba690658a3` |
| `440b7774-7f1a-4f55-bbe9-88b7d700ed7d` | `253631c3-9789-4405-a638-83e039138068` |

**One per group, and in each group it is the GUID-lowest member.** Group sizes
are 9, 10, 11 and 7, so under any random-loss model that alignment is about a
1-in-7000 coincidence. It is not document order — this document reconstructed
membership and sorted it — but "GUID-lowest" is a plausible enumeration order
for an LCM owning collection, which makes the missing child **the first one the
re-parent loop would touch in each group**.

### 3b. THE LARGER FINDING: 33 surviving children were RE-PARENTED, and the census reads that as green

Of the 37 group-owned children in the source, **zero** are group-owned in the
destination. The 33 that survive were re-homed to `MoMorphData`, and all four
groups arrive as **GUID-identical empty shells**.

**The census is structurally blind to this.** It reads:

    MoMorphAdhocProhib   39 -> 35   SHORTFALL (-4)
    MoAdhocProhibGr       4 ->  4   MATCHED

Both rows are counted correctly. Neither can express that 33 objects changed
owner or that every group is now empty. This is the **fourth** defect on this
feature's rows invisible to a class count — after T123(b)'s subclass
misclassification, T123's nesting demotion, and T127's empty `Name` — and it is
the strongest argument yet for the census-contract gap T127 asks to raise with
T081: **non-count assertions**. A grammar in which every ad-hoc prohibition
group is empty is broken in a way that three green-ish rows describe as a `-4`.

## 4. Mechanism — a single strong hypothesis that explains every observation

`Lib/categories.py:4677-4701`, the T011 group re-parenting branch:

```python
tgt_child = _find_target_obj_by_guid(
    list(morph_data.AdhocCoProhibitionsOC), child_guid)
if tgt_child is not None:
    try:
        morph_data.AdhocCoProhibitionsOC.Remove(tgt_child)   # <-- owning collection
        new_rule.MembersOC.Add(tgt_child)
    except (AttributeError, TypeError):
        pass
```

**`Remove` on an LCM *owning* collection is a disposal, not a detach.** This
repository already treats it that way everywhere else it appears — and it
appears only twice more:

* `categories.py:9225` — `entry_ie.AlternateFormsOS.Remove(rule_obj)`, immediately
  followed by an explicit `ICmObject(rule_obj).Delete()`.
* `categories.py:15592` — `contexts_os.Remove(member)`, in an orphan-cleanup loop.

Line 4696 is the **only** site in the codebase that uses `Remove` as a *move*.

The predicted sequence, per group: `Remove` disposes of the first child reached;
`MembersOC.Add` is then handed a disposed object and raises something outside
`(AttributeError, TypeError)`; that escapes the inner `except`, escapes the
outer `try` (same narrow tuple), and aborts the group's `execute_action` — so
the group's remaining children are never re-parented and stay where they were
created. Repeat over four groups: **−4 objects, 0 re-parented, 4 empty groups.**
Every observed number falls out of it.

**Ordering is not the cause, and that is worth stating** because it is the
obvious first suspect. `adhoc_compound_rules_enumerate_source`
(`categories.py:4357`) does sort `MoAdhocProhibGr` last, and the children
demonstrably exist in the target when the group runs — otherwise
`_find_target_obj_by_guid` would return `None`, nothing would be removed, and
all 37 would have survived under `MoMorphData` with no `-4` at all. The `-4` is
what proves the lookup succeeded.

**This is a hypothesis, not a measurement.** It is consistent with every figure
above and with the codebase's own usage of `Remove`, but no run was performed and
no LCM call was made from this document. Confirming it requires a live
restore-bounded transfer, and so does any fix.

## 5. Why this is not folded into T128

T128's `-4` is a *count* defect with a count acceptance. The re-parenting loss is
a *shape* defect that no count can state, on a write path whose suspected
mechanism is **destructive** (an owned object disposed rather than moved). Those
have different acceptances and different risk, and the second needs a human
before any fix is attempted. Filed as its own row.

## 6. Correction to the record

`_recurse_adhoc`'s T123 comment (`categories.py:4285-4290`) says:

> LATENT on the sanctioned corpus: `MoAdhocProhibGr` source_count is 0 on all
> three T078 pairs, so this is fixed to be correct the day a project with a
> grouping node arrives, and is NOT claimed as a measured recovery.

That was accurate when written. **It is no longer latent.** The mbugwe source
drift T128/T129 recorded (`fb6aadab…` → `3fb29a29…`) brought four grouping nodes
and 37 group children with it, and the path now runs on every mbugwe transfer.
The enumeration half the comment describes works correctly — all 39 are
enumerated and 35 are created. The placement half does not.
