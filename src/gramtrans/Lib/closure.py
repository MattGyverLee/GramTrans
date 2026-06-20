"""Dependency-closure traversal (constitution v5.0.0 Principle V; FR-013).

`walk(seeds, dependencies)` performs a BFS over the source-side closure
starting from the user's selected seed pieces. The walker is pure-Python —
it consumes a `dependencies(category, source_guid)` callable that each
category module under `Lib/categories*.py` will supply at preview time.

Dedup is by `(category, source_guid)` so diamond dependencies (Edge Case
"same item appears via two paths") yield exactly one transfer.

Return ordering is topological within BFS levels: a piece never precedes
the pieces it depends on (dependents appear before dependencies in the
visit order's reverse). For Phase 0 we return the visit order itself plus
a side `pulled_in_by` mapping; `Lib/preview.py` reverses where dependency-
first execution is required.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Dict, FrozenSet, Iterable, List, Tuple

if __package__:
    from .models import GrammarCategory
else:
    from models import GrammarCategory


Ref = Tuple[GrammarCategory, str]
DepFn = Callable[[GrammarCategory, str], Iterable[Ref]]


# ============================================================================
# Public API
# ============================================================================

def walk(
    seeds: Iterable[Ref],
    dependencies: DepFn,
) -> Tuple[Tuple[Ref, ...], Dict[Ref, Tuple[Ref, ...]]]:
    """Breadth-first walk of the closure.

    Args:
        seeds: iterable of (category, source_guid) pairs the user selected
            directly. Each appears once in the visit order with an empty
            pulled_in_by tuple.
        dependencies: callable that, given (category, source_guid), yields
            outgoing refs. Leaf categories return empty iterables.

    Returns:
        (visit_order, pulled_in_by):
        - visit_order: tuple of (category, source_guid) pairs in BFS order,
          deduplicated. Seeds come first in their input order, then
          dependencies in BFS layers.
        - pulled_in_by: dict mapping each non-seed ref to the tuple of refs
          that referenced it (multiple ancestors possible). Seeds map to ().
    """
    seen: set = set()
    seeded: set = set()  # explicitly-selected seeds; their parents stay empty
    order: List[Ref] = []
    parents: Dict[Ref, List[Ref]] = {}
    queue: deque = deque()

    # Enqueue seeds — they have no parent.
    for seed in seeds:
        if seed not in seen:
            seen.add(seed)
            seeded.add(seed)
            order.append(seed)
            parents[seed] = []
            queue.append(seed)

    # BFS.
    while queue:
        cur = queue.popleft()
        for ref in dependencies(*cur):
            if ref in seen:
                # Already queued/visited — record the additional parent unless
                # this ref was an explicit seed (seed semantics win: an item
                # the user picked directly is never "pulled in by" another).
                if ref not in seeded:
                    parents[ref].append(cur)
                continue
            seen.add(ref)
            order.append(ref)
            parents[ref] = [cur]
            queue.append(ref)

    pulled_in_by: Dict[Ref, Tuple[Ref, ...]] = {
        ref: tuple(p for p in ps) for ref, ps in parents.items()
    }
    return tuple(order), pulled_in_by


def topological(visit_order: Tuple[Ref, ...],
                pulled_in_by: Dict[Ref, Tuple[Ref, ...]]) -> Tuple[Ref, ...]:
    """Re-order a BFS visit so dependencies precede dependents.

    Uses Kahn's algorithm: repeatedly emit nodes with no remaining
    in-edges. Stable with respect to `visit_order` — among nodes ready
    to emit at the same time, the one that appeared earlier in
    `visit_order` wins.

    The previous implementation returned `reversed(visit_order)` which is
    correct only for *tree*-shaped closures. For DAGs with shared
    descendants (e.g. seeds B and C both pull in a leaf L), reversing
    can place a seed before its shared dependency. Kahn's gives the
    correct order in both shapes.

    Edge interpretation:
    - `pulled_in_by[X] = [Y, Z]` means Y and Z both pulled X in — i.e. X is
      a *dependency* of Y and Z. Therefore X must precede Y and Z in topo
      order. In edge form: X → Y and X → Z.
    - So `in_degree[Y]` counts how many of Y's *dependencies* haven't been
      emitted yet. A node is ready when all its deps have been emitted.
    """
    if not visit_order:
        return ()

    in_degree: Dict[Ref, int] = {ref: 0 for ref in visit_order}
    downstream: Dict[Ref, list] = {ref: [] for ref in visit_order}
    for dep, dependents in pulled_in_by.items():
        for dependent in dependents:
            in_degree[dependent] = in_degree.get(dependent, 0) + 1
            downstream.setdefault(dep, []).append(dependent)

    # Initial ready set: nodes with in_degree 0, preserving visit_order rank.
    rank = {ref: i for i, ref in enumerate(visit_order)}
    ready = sorted(
        (ref for ref in visit_order if in_degree[ref] == 0),
        key=lambda r: rank[r],
    )

    result: List[Ref] = []
    while ready:
        # Pop the earliest-ranked ready node.
        current = ready.pop(0)
        result.append(current)
        # Emitting `current` reduces in-degree on its children.
        new_ready = []
        for dependent in downstream.get(current, ()):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                new_ready.append(dependent)
        if new_ready:
            # Merge into the ready list maintaining rank order.
            ready.extend(new_ready)
            ready.sort(key=lambda r: rank[r])

    if len(result) != len(visit_order):
        # Cycle detected — emit remaining nodes by rank to keep output total.
        emitted = set(result)
        remaining = sorted(
            (ref for ref in visit_order if ref not in emitted),
            key=lambda r: rank[r],
        )
        result.extend(remaining)

    return tuple(result)
