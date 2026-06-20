"""Phase 2 test doubles for the ConflictResolver / WSResolver protocols.

These satisfy the structural Protocols defined in
`gramtrans.Lib.conflict` and `gramtrans.Lib.ws_mapping` without
needing PyQt.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.conflict import UserCancelled


class FakeConflictResolver:
    """Returns a pre-canned decision per prompt; optionally raises
    UserCancelled on the Nth prompt to exercise FR-213 atomicity.

    Construct with either:
    - `decisions=tuple[MergeDecision, ...]` -- one decision per prompt,
      same order. Length must match `prompts` passed to resolve().
    - `decision_for=callable(ConflictPrompt) -> MergeDecision`.
    - `cancel_at=N` -- raise UserCancelled when resolving the Nth prompt
      (0-indexed).
    """

    def __init__(self, decisions=None, decision_for=None, cancel_at=None):
        self.decisions = decisions
        self.decision_for = decision_for
        self.cancel_at = cancel_at
        self.invocations = 0

    def resolve(self, prompts):
        self.invocations += 1
        if self.cancel_at is not None and self.cancel_at < len(prompts):
            raise UserCancelled(f"FakeConflictResolver cancelled at index {self.cancel_at}")
        if self.decisions is not None:
            if len(self.decisions) != len(prompts):
                raise ValueError(
                    f"FakeConflictResolver: decisions length {len(self.decisions)} "
                    f"does not match prompts length {len(prompts)}"
                )
            return tuple(self.decisions)
        if self.decision_for is not None:
            return tuple(self.decision_for(p) for p in prompts)
        raise ValueError(
            "FakeConflictResolver requires either decisions= or decision_for="
        )


class FakeWSResolver:
    """Returns a pre-canned tuple of WSMappingChoice.  Same calling
    convention as FakeConflictResolver."""

    def __init__(self, choices=None, cancel=False):
        self.choices = choices or ()
        self.cancel = cancel
        self.invocations = 0

    def resolve(self, mismatches):
        self.invocations += 1
        if self.cancel:
            raise UserCancelled("FakeWSResolver cancelled")
        if len(self.choices) != len(mismatches):
            raise ValueError(
                f"FakeWSResolver: choices length {len(self.choices)} "
                f"does not match mismatches length {len(mismatches)}"
            )
        return tuple(self.choices)


@pytest.fixture
def make_fake_resolver():
    """Convenience factory: returns FakeConflictResolver(**kwargs)."""
    return FakeConflictResolver


@pytest.fixture
def make_fake_ws_resolver():
    return FakeWSResolver
