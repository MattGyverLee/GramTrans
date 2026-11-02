"""Issue #132 batch: post-pass A LexEntryRef RS Adds must not abort the pass.

``_run_post_pass_a`` used to call ``seq.Add`` bare; one failure stopped wiring
for every later ref on the entry and every later entry. Failures are Skips;
Add+read-back-present only logs (issue #111 parity).
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory, RunContext, SkipReason

from test_phase3c_post_pass_a import (
    _FakeEntryRef,
    _FakeObj,
    _FakeTarget,
    _FakeTargetEntry,
    _ctx_post_pass_a,
)


class _RaisingThenPresentSeq:
    """First Add raises; second call (read-back path) sees the member."""

    def __init__(self) -> None:
        self._items = []
        self.add_attempts = 0

    def Add(self, obj) -> None:
        self.add_attempts += 1
        if self.add_attempts == 1:
            self._items.append(obj)
            raise RuntimeError("transient Add failure")
        self._items.append(obj)

    def __iter__(self):
        return iter(self._items)


class _AlwaysFailSeq:
    def __init__(self) -> None:
        self._items = []

    def Add(self, obj) -> None:
        raise ValueError("Add permanently rejected")

    def __iter__(self):
        return iter(self._items)


def test_post_pass_a_add_failure_emits_skip_and_continues() -> None:
    comp_a = _FakeObj("comp-a")
    comp_b = _FakeObj("comp-b")
    ref = _FakeEntryRef()
    ref.ComponentLexemesRS = _AlwaysFailSeq()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    target = _FakeTarget({"entry-1": entry, "comp-b": comp_b})
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["comp-a", "comp-b"]}},
        in_plan_entries={"comp-a": comp_a, "comp-b": comp_b},
    )
    skips = categories._run_post_pass_a(ctx, target, tag=None)
    assert len(skips) == 2
    assert all(s.reason == SkipReason.DEPENDENCY_UNRESOLVED for s in skips)
    assert "Add failed" in skips[0].detail
    assert skips[0].category == GrammarCategory.STEMS


def test_post_pass_a_add_raises_but_readback_present_no_skip() -> None:
    comp = _FakeObj("comp-a")
    ref = _FakeEntryRef()
    ref.ComponentLexemesRS = _RaisingThenPresentSeq()
    entry = _FakeTargetEntry("entry-1", entry_refs=[ref])
    target = _FakeTarget({"entry-1": entry, "comp-a": comp})
    ctx = _ctx_post_pass_a(
        {"entry-1": {"ComponentLexemesRS": ["comp-a"]}},
        in_plan_entries={"comp-a": comp},
    )
    skips = categories._run_post_pass_a(ctx, target, tag=None)
    assert skips == []
    assert ref.ComponentLexemesRS.add_attempts == 1
