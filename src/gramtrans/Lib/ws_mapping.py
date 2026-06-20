"""Writing-system mapping validation (T036, spec.md FR-011 / Clarification Q3).

Pure-Python validation: given a set of source WS IDs (with kind) that the
current Selection requires, and a user-supplied `WSMapping`, decide whether
the mapping is complete and 1:1.

Mapping materialization into the target (creating WSs flagged
`create_in_target=True`) is implemented at runtime in `Lib/transfer.py`'s
pre-step; this module is the read-only validator and stays import-safe
without flexlibs2 / pythonnet.
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

if __package__:
    from .models import WSKind, WSMapping
else:
    from models import WSKind, WSMapping


# ============================================================================
# Exceptions
# ============================================================================

class WSMappingError(Exception):
    """Base class for WS-mapping errors surfaced by `validate`."""


class WSMappingIncomplete(WSMappingError):
    """Raised when the user-provided WSMapping doesn't cover every required
    source writing system. The missing set is exposed via the `.missing`
    attribute as a frozenset of (source_ws_id, WSKind) pairs."""

    def __init__(self, missing: FrozenSet[Tuple[str, WSKind]]) -> None:
        self.missing = missing
        formatted = ", ".join(
            f"{ws_id!r} ({kind.value})" for ws_id, kind in sorted(missing, key=lambda x: x[0])
        )
        super().__init__(f"WS mapping incomplete: missing {formatted}")


class WSMappingOverspecified(WSMappingError):
    """Raised when the user-provided WSMapping carries entries for WSs that
    the current Selection doesn't reference. Not a hard error in production
    (the extras are simply ignored), but tests use it to verify the WSs the
    user is asked to map are exactly the ones actually needed."""

    def __init__(self, extras: FrozenSet[Tuple[str, WSKind]]) -> None:
        self.extras = extras
        super().__init__(f"WS mapping overspecified: extras {sorted(extras)}")


# ============================================================================
# Public API
# ============================================================================

def required_ws_set(pairs: Iterable[Tuple[str, WSKind]]) -> FrozenSet[Tuple[str, WSKind]]:
    """Build a frozenset of (source_ws_id, kind) pairs from an arbitrary
    iterable. Caller is the closure walker — it asks each selected piece for
    its `required_writing_systems()` and feeds the union here.
    """
    return frozenset(pairs)


def validate(ws_mapping: WSMapping,
             required: FrozenSet[Tuple[str, WSKind]],
             *, strict_overspec: bool = False) -> None:
    """Verify that `ws_mapping` covers every (source_ws_id, kind) pair in
    `required`. Raises `WSMappingIncomplete` listing the missing entries
    otherwise.

    If `strict_overspec=True`, also raise `WSMappingOverspecified` when the
    mapping carries entries the Selection doesn't reference. Default is
    permissive — production runs ignore extras (the user may have mapped
    extra WSs in anticipation of future selections).
    """
    provided = frozenset(
        (e.source_ws_id, e.source_ws_kind) for e in ws_mapping.entries
    )
    missing = required - provided
    if missing:
        raise WSMappingIncomplete(missing)
    if strict_overspec:
        extras = provided - required
        if extras:
            raise WSMappingOverspecified(extras)


def is_complete(ws_mapping: WSMapping,
                required: FrozenSet[Tuple[str, WSKind]]) -> bool:
    """Predicate form of `validate` — True iff `ws_mapping` covers every
    required pair. Use this in UI gating (Move button stays disabled until
    the WS mapping is complete)."""
    try:
        validate(ws_mapping, required, strict_overspec=False)
        return True
    except WSMappingIncomplete:
        return False
