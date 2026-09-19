# Cycle 18 -- is PhSimpleContextNC e6a93fd6 referenced in the SOURCE?

Read-only XML parse, no project opened, no writes.

## Hash precondition
Both re-verified against cycle17: source `3fb29a29...5436d` MATCH, dest
`dd97c8c8...14b1a` MATCH. No drift.

## Reference collection
Two `objsur` occurrences of `e6a93fd6-ecfc-45a5-81df-497fba40766e` exist in the
source, distinguished by `t`:

| t | referring rt class + field | referring guid |
|---|---|---|
| `o` (ownership) | `PhPhonData.Contexts` | `be765e3e-...` (owner, cycle17) |
| `r` (reference) | `PhSequenceContext.Members` | `1f36ff23-743b-4ee0-8078-18a38f492a30` |

The `t="r"` hit is a genuine referrer. Chasing it: `PhSequenceContext 1f36ff23`
is itself owned (`t="o"`) by `PhSegRuleRHS 32eb9ca9-...` via `RightContext`. So
the object is reachable: `PhSegRuleRHS.RightContext` -> `PhSequenceContext.Members`
-> target -- the path item 4 named. It resolves positive here.

## Two-way class partition, PhSimpleContextNC
| | total | referenced (t="r" anywhere) | unreferenced |
|---|---|---|---|
| source | 104 | 59 | 45 |
| dest | 103 | 58 | 45 |

The 45 unreferenced GUIDs are identical in both files -- every source orphan
of this class transferred untouched. The whole -1 shortfall sits inside the
referenced 59->58, and the sole missing GUID is the target. `PhIterationContext`
bodies were scanned separately: target not present in any.

## Incidental (not this task's question)
In dest, `PhSequenceContext 1f36ff23` survives as an empty self-closed `<rt/>`
with no `<Members>` at all -- it lost both members' membership entries, not
just the target's. Flagged, not chased.

## Verdict
**SOURCE_REFERENCED** -- one referrer, `PhSequenceContext.Members` (`1f36ff23`),
reachable from a live `PhSegRuleRHS.RightContext`. Does NOT match the
`UNREFERENCED_IN_SOURCE` fact pattern from the `PhFeatureConstraint` ruling,
which explicitly declines `PhSimpleContext*` (its section 4). Whether any
token extends here is a human decision, not asserted here. On the fact
pattern alone this is a genuine create-path loss.
