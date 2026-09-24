"""Feature 038 T120: one bad right-hand side used to lose all the others.

THE MEASUREMENT THAT DID NOT FIT THE STORY. T116 attributed the phonological
context family per route and found:

    PhRegularRule    MATCHED on all three pairs  (6/6, 21/21, 39/39)
    RightHandSides   SHORT on two                (21 -> 18, 39 -> 28)
    PhSegmentRule.StrucDesc   +-0 everywhere

A parent that arrives whole while its owned child COLLECTION arrives short is
not explained by a missing create path (there is one, and it works for the
first N children) and not by a gold-reserved enrichment gap (the rules are
created, not matched, on a fresh target). It IS explained by a loop that
aborts partway.

THE DEFECT. All three `RightHandSidesOS` loops in `categories.py` were written
as

    try:
        for src_rhs in src_rr.RightHandSidesOS:
            ...
    except (AttributeError, TypeError):
        pass

-- the `try` wrapping the WHOLE loop rather than the iterator acquisition. One
`AttributeError`/`TypeError` in any iteration therefore aborted the loop and
dropped every REMAINING right-hand side, silently (`pass`), with the rule still
reporting success. Each lost RHS took its `LeftContext` / `RightContext` /
`StrucChange` children with it -- on Mbugwe, 11 lost RHS account for 35 lost
child contexts, which is the same arithmetic T116 reports.

THREE SITES, FOUND BY PATTERN AUDIT, WITH THREE DIFFERENT CONSEQUENCES:

  * `_phon_rule_apply_body`'s RHS creation loop  -> the measured
    `PhSegRuleRHS` shortfall, and an SC-010 never-silent violation.
  * the CONSTRAINT PRE-PASS over RHS contexts    -> `PhFeatureConstraint`,
    owned SOLELY by `PhPhonData.FeatConstraints` and at -47 / -32 the single
    largest context-family loss. T120(a)'s shared pool.
  * `phonological_rules_dependencies`' ref walk  -> under-reports the FR-304
    dependency closure: a rule's later right-hand sides contribute no
    phoneme / natural-class / POS / rule-feature edges at all. This one is
    LATENT rather than measured, because nothing consumes the return value
    yet (the function's own RC-2 docstring says so) -- it is fixed now
    precisely so it is already correct when 038 Phase 2 wires the closure up,
    rather than becoming a fresh loss on the day it goes live.

The audit found 51 instances of the broad shape repo-wide; the other 48 guard
an ITERATOR ACQUISITION on duck fakes over a few lines and are correct. These
three are distinguished by wrapping a loop that CREATES objects (or builds a
comparison key) across tens of lines. They are fixed; the rest are deliberately
untouched.

Host-free: duck fakes only.
"""
from __future__ import annotations

import inspect
import re

import pytest

from gramtrans.Lib import categories


# --------------------------------------------------------------------------
# The structural claim: the guard is on the acquisition, not the loop
# --------------------------------------------------------------------------

def _body(fn):
    return inspect.getsource(fn)


@pytest.mark.parametrize("marker", [
    "rhs_list = list(src_rr.RightHandSidesOS)",
    "pre_pass_rhs = list(src_rr.RightHandSidesOS)",
])
def test_apply_body_acquires_the_rhs_list_before_looping(marker):
    """`list(...)` inside the `try`, the `for` outside it. Materialising is
    also what makes the acquisition failure distinguishable from a per-item
    one -- a bare `for` over a live LCM sequence can raise on ANY step."""
    body = _body(categories._phon_rule_apply_body)
    assert marker in body


def test_apply_body_has_no_whole_loop_guard_left():
    """The shape that caused it, asserted absent: a `try:` immediately
    followed by `for src_rhs in src_rr.RightHandSidesOS:`."""
    body = _body(categories._phon_rule_apply_body)
    assert not re.search(
        r"try:\s*\n\s*for src_rhs in src_rr\.RightHandSidesOS:", body)


def test_dependency_walk_acquires_the_rhs_list_before_looping():
    body = _body(categories.phonological_rules_dependencies)
    assert "dep_rhs = list(rr.RightHandSidesOS)" in body
    assert not re.search(r"try:\s*\n\s*for rhs in rr\.RightHandSidesOS:", body)


def test_a_failed_rhs_is_reported_and_the_loop_continues():
    """Report AND continue: the two halves of the fix. `continue` alone would
    have traded a silent total loss for a silent partial one."""
    body = _body(categories._phon_rule_apply_body)
    assert "_report_dropped_rhs" in body
    assert "continue" in body.split("_report_dropped_rhs")[1][:200]


# --------------------------------------------------------------------------
# The report record
# --------------------------------------------------------------------------

def test_report_dropped_rhs_emits_a_record():
    dropped = []
    categories._report_dropped_rhs(
        dropped, "rule-guid-1", "rhs-guid-1", TypeError("bad cast"))
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "PhSegRuleRHS"
    assert rec.field_name == "RightHandSidesOS"
    assert rec.item_guid == "rhs-guid-1"
    assert "TypeError" in rec.reason
    # The children lost with it are named -- the census cannot see them, so
    # the report is the only place a reader learns the cascade happened.
    assert "children" in rec.reason


def test_report_dropped_rhs_tolerates_no_sink():
    """`_dropped_list` is None on paths with no report sink. Reporting must
    never itself become the thing that aborts the loop."""
    categories._report_dropped_rhs(None, "r", "rhs", TypeError("x"))


def test_report_dropped_rhs_is_deduped():
    dropped = []
    for _ in range(3):
        categories._report_dropped_rhs(
            dropped, "rule-1", "rhs-1", TypeError("bad"))
    assert len(dropped) == 1


# --------------------------------------------------------------------------
# The pattern audit, recorded so the scope of the fix is legible
# --------------------------------------------------------------------------

def test_the_three_fixed_sites_are_the_creating_and_comparing_ones():
    """A guard against someone "consistently" re-wrapping these loops. The
    three sites share a shape with ~48 others that are CORRECT -- what marks
    these three is that the loop body creates objects or builds a comparison
    key. Naming them here is what keeps the fix's scope reviewable."""
    for fn in (categories._phon_rule_apply_body, categories.phonological_rules_dependencies):
        src = _body(fn)
        # No `try:` directly wrapping a RightHandSidesOS iteration anywhere.
        assert not re.search(r"try:\s*\n\s*for \w+ in \w+\.RightHandSidesOS:", src)
