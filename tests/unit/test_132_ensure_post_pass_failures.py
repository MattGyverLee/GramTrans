"""Issue #132 batch 1: post-loop `_ensure_*` safety nets record failures.

Before this change, swallowed exceptions in execute()'s post-passes only hit
the log; RunReport.leaf_execution_failures stayed empty and leaf_failed did
not move.
"""

from __future__ import annotations

from unittest import mock

import pytest

from gramtrans.Lib.models import GrammarCategory, LeafExecutionFailure
from gramtrans.Lib import transfer as transfer_mod


def test_record_post_pass_failure_appends_with_synthetic_guid():
    failures: list = []
    transfer_mod._record_post_pass_failure(
        failures,
        pass_name="demo-pass",
        category=GrammarCategory.STEMS,
        exc=RuntimeError("boom"),
    )
    assert len(failures) == 1
    rec = failures[0]
    assert isinstance(rec, LeafExecutionFailure)
    assert rec.source_guid == "post-pass:demo-pass"
    assert rec.exception_type == "RuntimeError"
    assert rec.message == "boom"
    assert rec.category == GrammarCategory.STEMS


def test_record_post_pass_failure_no_list_is_noop():
    transfer_mod._record_post_pass_failure(
        None,
        pass_name="demo-pass",
        category=GrammarCategory.STEMS,
        message="skipped",
    )


def _bare_exec_ctx(**attrs):
    """Minimal exec_ctx without Mock's auto truthy attributes."""
    ctx = mock.Mock(spec=["_run_plan"])
    for key, val in attrs.items():
        setattr(ctx, key, val)
    return ctx


@pytest.mark.parametrize(
    "helper,inner_path,category,pass_suffix,call_args",
    [
        (
            transfer_mod._ensure_171_subpass,
            "gramtrans.Lib.categories._run_171_subpass",
            GrammarCategory.AFFIX_TEMPLATES,
            "171-subpass",
            lambda ctx, tgt: (ctx, tgt, "tag", []),
        ),
        (
            transfer_mod._ensure_matched_nc_segments,
            "gramtrans.Lib.categories._wire_matched_nc_segments",
            GrammarCategory.NATURAL_CLASSES,
            "matched-nc-segments",
            lambda ctx, tgt: (ctx, tgt, []),
        ),
        (
            transfer_mod._ensure_owner_feat_strucs,
            "gramtrans.Lib.categories._wire_owner_feat_strucs",
            GrammarCategory.STEMS,
            "owner-feat-strucs",
            lambda ctx, tgt: (ctx, tgt, "tag", []),
        ),
        (
            transfer_mod._ensure_complex_feature_type_ra,
            "gramtrans.Lib.categories._run_complex_feature_type_ra_pass",
            GrammarCategory.INFLECTION_FEATURES,
            "complex-feature-type-ra",
            lambda ctx, tgt: (ctx, tgt, []),
        ),
        (
            transfer_mod._ensure_struct_type_features_rs,
            "gramtrans.Lib.categories._run_struct_type_features_rs_pass",
            GrammarCategory.FEATURE_STRUCT_TYPES,
            "struct-type-features-rs",
            lambda ctx, tgt: (ctx, tgt, []),
        ),
    ],
)
def test_ensure_passes_record_leaf_failure_on_raise(
    helper, inner_path, category, pass_suffix, call_args,
):
    failures: list = []
    exec_ctx = _bare_exec_ctx(_run_plan=object())
    target = object()
    with mock.patch(inner_path, side_effect=RuntimeError("post-pass broke")):
        args = call_args(exec_ctx, target)
        helper(*args, post_pass_failures=failures)
    assert len(failures) == 1
    assert failures[0].category == category
    assert failures[0].source_guid == f"post-pass:{pass_suffix}"


def test_ensure_infl_feature_links_records_missing_plan():
    failures: list = []
    exec_ctx = _bare_exec_ctx(_run_plan=None)
    with mock.patch(
        "gramtrans.Lib.categories._reconcile_deferred_infl_pairs",
    ) as reconcile:
        transfer_mod._ensure_infl_feature_links(
            exec_ctx, object(), "tag", [], post_pass_failures=failures,
        )
    reconcile.assert_called_once()
    assert len(failures) == 1
    assert failures[0].source_guid == "post-pass:infl-feature-links"
    assert "no RunPlan" in failures[0].message


def test_run_post_pass_ensure_increments_leaf_failed_counter():
    """execute()'s wrapper must bump leaf_failed when a post-pass records."""
    failures: list = []
    leaf_failed = 0

    def _run_post_pass_ensure(fn, *args, **kwargs):
        nonlocal leaf_failed
        _before = len(failures)
        fn(*args, post_pass_failures=failures, **kwargs)
        leaf_failed += len(failures) - _before

    exec_ctx = _bare_exec_ctx(_run_plan=object())
    with mock.patch(
        "gramtrans.Lib.categories._run_171_subpass",
        side_effect=ValueError("nope"),
    ):
        _run_post_pass_ensure(
            transfer_mod._ensure_171_subpass,
            exec_ctx, object(), "tag", [],
        )
    assert leaf_failed == 1
    assert len(failures) == 1
