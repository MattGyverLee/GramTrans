"""Issue #171 -- mid-pass raise must keep InflectableFeats link write count and skips."""

from __future__ import annotations

import pytest

from gramtrans.Lib import categories, transfer
from gramtrans.Lib.models import GrammarCategory, SkipReason
import test_133_deferred_reconciliation as recon
import test_038_enrichment_executor as fake_base


def test_midpass_raise_keeps_write_count_and_skips_before_raise():
    ctx, target, created = recon._created_pos_chain()
    target._objects.pop("pos-num", None)
    target.POS = fake_base._FakeOps([created])
    real = categories._resolve_target_by_guid

    def _flaky(tgt, guid):
        if guid == "feat-2":
            raise RuntimeError("mid-pass failure")
        return real(tgt, guid)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(categories, "_resolve_target_by_guid", _flaky)
    object.__setattr__(
        ctx._run_plan,
        "feature_category_links",
        {"pos-missing": ["feat-orphan"], "pos-num": ["feat-1", "feat-2"]},
    )
    # #170: with a drop collector an unresolved POS is a drop, not a Skip; the
    # Skip stash is what a collector-less run must not lose.
    object.__setattr__(ctx, "_dropped", None)
    transfer._ensure_infl_feature_links(ctx, target, None, ctx._exec_skips)
    monkeypatch.undo()
    assert ctx._infl_feature_link_writes == 1
    pos_skips = [
        s
        for s in ctx._exec_skips
        if s.category is GrammarCategory.GRAM_CATEGORIES
        and s.source_guid == "pos-missing"
    ]
    assert len(pos_skips) == 1
    assert pos_skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
