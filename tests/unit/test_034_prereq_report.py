"""T048 / FR-036, SC-006 — the self-check tells the truth, and gives a next step.

Two things are being protected.

**A `[FAIL]` with no remedy is a dead end**, and dead ends are the exact
experience this feature exists to remove: the user who cannot start the
application is, by definition, the one who cannot ask the application what is
wrong. So "every failing check carries a remedy" is enforced in the type, not
in review, and this file proves the enforcement is real.

**A false `[FAIL]` is worse than no self-check at all.** It sends someone with
a working FieldWorks off to reinstall it. `test_034_fwglobals_only.py` bans
direct reads of the FieldWorks globals statically; this file covers the half an
AST scan cannot express — that detection actually *observes* the live module
attribute, so patching it changes what the report says.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gramtrans.standalone.prereq import (
    PrerequisiteCheck,
    PrerequisiteReport,
    Verdict,
    run_checks,
)


def _check(name="X", verdict=Verdict.PASS, remedy="", detected="d", expected="e"):
    return PrerequisiteCheck(
        name=name, detected=detected, expected=expected,
        verdict=verdict, remedy=remedy,
    )


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def test_overall_is_fail_if_any_check_fails():
    report = PrerequisiteReport(checks=[
        _check("a"),
        _check("b", Verdict.FAIL, remedy="do the thing"),
        _check("c"),
    ])
    assert report.overall is Verdict.FAIL


def test_overall_is_pass_when_nothing_failed():
    report = PrerequisiteReport(checks=[_check("a"), _check("b")])
    assert report.overall is Verdict.PASS


def test_unknown_does_not_fail_the_report():
    """`UNKNOWN` means "not determined", not "broken".

    A self-check that went red because one optional fact was unreadable would
    train users to ignore the red, which costs more than the missing fact.
    """
    report = PrerequisiteReport(checks=[_check("a"), _check("b", Verdict.UNKNOWN)])
    assert report.overall is Verdict.PASS


def test_an_empty_report_is_pass_not_a_crash():
    assert PrerequisiteReport().overall is Verdict.PASS
    assert PrerequisiteReport().total == 0


def test_passed_and_total_count_only_what_they_claim():
    report = PrerequisiteReport(checks=[
        _check("a"),
        _check("b", Verdict.UNKNOWN),
        _check("c", Verdict.FAIL, remedy="r"),
    ])
    assert (report.passed, report.total) == (1, 3)


# ---------------------------------------------------------------------------
# SC-006 — a FAIL must carry a remedy
# ---------------------------------------------------------------------------

def test_a_failing_check_cannot_be_constructed_without_a_remedy():
    with pytest.raises(ValueError, match="remedy"):
        PrerequisiteCheck(name="X", detected="d", expected="e", verdict=Verdict.FAIL)


def test_whitespace_is_not_a_remedy():
    with pytest.raises(ValueError, match="remedy"):
        PrerequisiteCheck(
            name="X", detected="d", expected="e", verdict=Verdict.FAIL, remedy="   "
        )


def test_a_passing_check_needs_no_remedy():
    assert _check("X").remedy == ""


def test_every_failing_check_in_a_real_report_has_a_remedy():
    """The invariant, checked against a live run rather than a fixture."""
    report = run_checks(log_path="")
    for check in report.checks:
        if check.verdict is Verdict.FAIL:
            assert check.remedy.strip(), f"{check.name} FAILs with no remedy"


# ---------------------------------------------------------------------------
# The R1 guard the AST ban cannot express
# ---------------------------------------------------------------------------

def test_detection_reads_the_live_module_attribute():
    """Patch `FLExGlobals.FWProjectsDir`; the report must show the patched value.

    Detection wired to the package re-export (`flexicon.FWProjectsDir`) would
    show the value bound at import instead, and on the machine research R1
    described would show `None` and report a false FAIL.

    Note the correction recorded in probe-results.md §T012: on flexicon 4.3.1
    the re-exports happen to be populated, so this specific test would pass
    against a wrong implementation *on this machine*. It still earns its place
    — it pins the intended semantics (read the module, at call time), which is
    what stays correct if flexicon's import-time initialisation ever moves.
    """
    flex_globals = pytest.importorskip("flexicon.code.FLExGlobals")
    from gramtrans.standalone import fwglobals

    sentinel = r"D:\Somewhere\Else\Projects"
    original = flex_globals.FWProjectsDir
    flex_globals.FWProjectsDir = sentinel
    fwglobals.mark_initialized()
    try:
        report = run_checks(log_path="")
        location = next(
            c for c in report.checks if c.name == "FieldWorks projects location"
        )
        assert sentinel in location.detected, (
            "the projects-location check did not observe the patched module "
            "attribute — it is reading a snapshot"
        )
        # And the check correctly fails, because the sentinel does not exist.
        assert location.verdict is Verdict.FAIL
        assert location.remedy.strip()
    finally:
        flex_globals.FWProjectsDir = original
        fwglobals.reset_for_tests()


def test_a_real_run_on_this_machine_passes():
    """A sanity anchor: on a machine with FieldWorks, the self-check is green.

    Not marked `integration` on purpose. If it ever fails on a developer
    machine that has FieldWorks, that is exactly the false-negative FR-036 is
    written to prevent, and it should be loud. On a machine without
    FieldWorks the report legitimately fails, so the assertion is conditional
    on detection rather than unconditional.
    """
    from gramtrans.standalone import fwglobals

    try:
        fwglobals.probe()
    except fwglobals.FieldWorksNotDetected:
        pytest.skip("no FieldWorks on this machine")

    report = run_checks(log_path="")
    failures = [(c.name, c.detected) for c in report.checks if c.verdict is Verdict.FAIL]
    assert not failures, f"self-check failed on a machine with FieldWorks: {failures}"


# ---------------------------------------------------------------------------
# FR-037 — the rendered block
# ---------------------------------------------------------------------------

def test_the_rendered_block_is_ascii_and_carries_the_required_lines():
    from gramtrans.standalone.selfcheck import render

    report = PrerequisiteReport(
        checks=[
            _check("Good"),
            _check("Bad", Verdict.FAIL, remedy="Install FieldWorks 9."),
            _check("Dunno", Verdict.UNKNOWN),
        ],
        app_version="0.1.0+gdeadbee",
        generated_at="2026-08-17T00:00:00",
        log_path=r"C:\Users\x\AppData\Local\GramTrans\logs\gramtrans-GT-1.log",
    )
    text = render(report)

    text.encode("ascii")  # raises if anything non-ASCII crept in
    assert "GramTrans self-check" in text
    assert "0.1.0+gdeadbee" in text
    assert "[PASS] Good" in text
    assert "[FAIL] Bad" in text
    assert "[UNKNOWN] Dunno" in text
    assert "VERDICT: FAIL (1 of 3)" in text
    assert r"gramtrans-GT-1.log" in text

    # No colour, no box drawing -- it has to survive being pasted anywhere.
    assert "\x1b[" not in text
    assert not set(text) & set("│─┌┐└┘├┤┬┴┼█")


def test_every_fail_line_is_followed_by_a_remedy_line():
    from gramtrans.standalone.selfcheck import render

    report = PrerequisiteReport(checks=[
        _check("Bad", Verdict.FAIL, remedy="Do the specific thing."),
        _check("Fine"),
    ])
    lines = render(report).splitlines()
    idx = next(i for i, line in enumerate(lines) if line.startswith("[FAIL]"))
    following = "\n".join(lines[idx: idx + 5])
    assert "remedy:" in following
    assert "Do the specific thing." in following


def test_a_passing_check_gets_no_remedy_line():
    from gramtrans.standalone.selfcheck import render

    text = render(PrerequisiteReport(checks=[_check("Fine")]))
    assert "remedy:" not in text
