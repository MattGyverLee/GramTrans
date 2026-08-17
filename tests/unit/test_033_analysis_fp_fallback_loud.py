"""The structural-dedup fallback must not absorb a GUID regression in silence.

033 allows a GUID-identity loss that is *justified and logged*; it forbids a
silent one. `wordforms._plan_analysis_fingerprint` is the cross-run dedup path
that runs when `_resolve_by_guid` finds nothing, and `_resolve_by_guid` finding
nothing has two indistinguishable causes: a legacy target (expected) or GUID
preservation having broken (a regression the fallback would otherwise hide).

These tests pin the aggregated WARNING that makes the difference visible, and
-- just as important -- pin that it stays SILENT on a healthy modern target, so
it cannot become noise that gets filtered out and stops being read.
"""
from __future__ import annotations

import logging

from gramtrans.Lib import wordforms


def test_fallback_hits_emit_one_aggregated_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.wordforms"):
        returned = wordforms._log_analysis_fp_fallback(7, 3, 10)

    assert returned == 7
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "one aggregated warning, not one per analysis"
    assert "7 of 10" in caplog.text
    assert "STRUCTURAL fingerprint" in caplog.text
    # Must name both readings, so the reader can tell legacy from regression.
    assert "legacy" in caplog.text
    assert "regress" in caplog.text
    # Must point at the durable explanation rather than only the symptom.
    assert "specs/033-guid-preservation/TODO.md" in caplog.text


def test_silent_when_every_analysis_matched_by_guid(caplog):
    """The cry-wolf guard: a modern target must produce NO warning at all."""
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.wordforms"):
        returned = wordforms._log_analysis_fp_fallback(0, 12, 12)

    assert returned == 0
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


def test_guid_hit_count_is_reported_so_a_vacuous_zero_is_detectable(caplog):
    """0 fallback hits out of 0 considered is NOT evidence of health.

    This is the vacuous-PASS trap 033 already hit once (an audit read
    `minted=0` only because almost nothing was created). Reporting the GUID-hit
    count alongside the total is what lets a reader tell "everything matched by
    identity" from "nothing was examined".
    """
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.wordforms"):
        assert wordforms._log_analysis_fp_fallback(0, 0, 0) == 0
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []

    # ...and when the fallback DOES fire, the message carries the guid-hit
    # count, so "0 by GUID" is visible as the regression signature it is.
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.wordforms"):
        wordforms._log_analysis_fp_fallback(9, 0, 9)
    assert "9 of 9" in caplog.text
    assert "(0 matched by GUID)" in caplog.text


def test_helper_is_reachable_from_apply_analyses():
    """Guard against the counters being wired up and then quietly dropped."""
    import inspect

    src = inspect.getsource(wordforms.apply_analyses)
    assert "_log_analysis_fp_fallback(" in src, (
        "apply_analyses must report its fallback tally; without this call the "
        "counters exist but nothing ever surfaces them"
    )
    assert "fp_fallback_hits += 1" in src
    assert "guid_hits += 1" in src
