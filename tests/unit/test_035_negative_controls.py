"""Feature 035 -- T026: the negative-control regime.

Source: spec.md FR-178..FR-181, contracts/rosters.md section 8,
contracts/guards.md "Negative controls", contracts/verdict-exit-model.md.

NO FLEx project and NO LCM. The seeded defects this file reasons about are
recorded outcomes in a tracked JSON artifact, not live transfers.

The regime in one line: a guard is admissible as passing evidence only once a
deliberately seeded defect has been shown to make it fail, that demonstration
is recorded durably, and the guard's own source has not changed since. Missing,
stale, or superseded control => that guard reports ``not-evaluated`` => the run
is ``VACUOUS`` (FR-180, FR-109). A guard no constructible defect can fail is
itself a defect (FR-181), never evidence of robustness.

TDD posture: T034 builds the ``negative-controls`` subcommand, the seeded-defect
suite, and the durable artifact. Until then the tests that need that machinery
are marked ``xfail(strict=True)``, so they flip to a hard failure the moment
T034 lands and the marker must be removed deliberately rather than rotting. The
API those tests expect is stated in EXPECTED_T034_API below -- T034 either
provides those names or updates this file as a conscious contract change.

Per FR-176 the contract tables are transcribed as INDEPENDENT literals.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import guards  # noqa: E402
from debug.fullsweep import verdict  # noqa: E402

# ---------------------------------------------------------------------------
# Contract tables -- transcribed, not imported
# ---------------------------------------------------------------------------

CONTRACT_GUARD_NAMES = (
    "BASELINE-DELTA",
    "COMPARISONS-PERFORMED",
    "CATEGORY-COVERAGE",
    "TOTAL-ACCOUNTING",
    "EMPTY-CORROBORATION",
    "UNHANDLED-SUBTYPE",
    "IDEMPOTENCY-IN-WRITTEN-CLASSES",
    "PLAN-CONSERVATION",
    "NO-EXTRA",
    "ACCESSOR-INTEGRITY",
    "HANDLE-INTEGRITY",
    "NO-TRUNCATION",
    "ARTIFACT-INTEGRITY",
    "NO-ENGINE-BUG-AS-LOSS",
    "CLEAN-CLOSE",
)

#: contracts/rosters.md section 8: the durable control record's shape.
CONTRACT_CONTROL_RECORD_KEYS = (
    "guard",
    "seeded_defect",
    "verdict_produced",
    "guard_module_hash",
    "recorded_at",
)
CONTRACT_CONTROLS_TOP_LEVEL_KEYS = ("schema_version", "controls")

#: FR-179: the specific failing verdict each guard exists to produce.
#: A value of None means the spec text does NOT pin a single token for that
#: guard -- there the only assertable rule is that the produced verdict does
#: not report success. Recorded as a concern rather than invented here.
MANDATED_VERDICT = {
    "BASELINE-DELTA": "VACUOUS",
    "COMPARISONS-PERFORMED": "VACUOUS",
    "CATEGORY-COVERAGE": "COVERAGE_REDUCED",
    "TOTAL-ACCOUNTING": "UNEXPLAINED_LOSS",
    "EMPTY-CORROBORATION": None,
    "UNHANDLED-SUBTYPE": None,
    "IDEMPOTENCY-IN-WRITTEN-CLASSES": "NON_IDEMPOTENT",
    "PLAN-CONSERVATION": "UNEXPLAINED_LOSS",
    "NO-EXTRA": "UNEXPLAINED_LOSS",
    "ACCESSOR-INTEGRITY": "HARNESS_ERROR",
    "HANDLE-INTEGRITY": "HARNESS_ERROR",
    "NO-TRUNCATION": "HARNESS_ERROR",
    "ARTIFACT-INTEGRITY": "INCOMPLETE",
    "NO-ENGINE-BUG-AS-LOSS": "UNEXPLAINED_LOSS",
    "CLEAN-CLOSE": "HARNESS_ERROR",
}

CONTRACT_VACUOUS_TOKEN = "VACUOUS"
CONTRACT_NOT_EVALUATED = "not-evaluated"
FORBIDDEN_DEGRADATION = "pass"

#: The names T034 is expected to provide. Kept deliberately small.
EXPECTED_T034_API = (
    "load_negative_controls",   # (path) -> dict
    "guard_module_hash",        # (guard_name) -> sha256 hex of the guard's module
    "negative_control_result",  # (guard_name, controls) -> "pass" | "not-evaluated"
)

_MISSING_T034 = tuple(n for n in EXPECTED_T034_API if not hasattr(guards, n))
_needs_t034 = pytest.mark.xfail(
    bool(_MISSING_T034),
    strict=True,
    reason="T034 builds the negative-control machinery; missing: %r" % (_MISSING_T034,),
)

CONTROLS_PATH = (
    _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts" / "negative-controls.json"
)


def _control(guard_name, *, defect="seeded", token=None, module_hash="deadbeef"):
    return {
        "guard": guard_name,
        "seeded_defect": defect,
        "verdict_produced": token or (MANDATED_VERDICT[guard_name] or "UNEXPLAINED_LOSS"),
        "guard_module_hash": module_hash,
        "recorded_at": "2026-08-18T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# FR-178/FR-179: every guard needs a control, and it must name a real verdict
# ---------------------------------------------------------------------------


def test_every_registered_guard_is_covered_by_the_mandated_verdict_table():
    """FR-178: no guard is exempt from having to be shown capable of failing."""
    assert set(MANDATED_VERDICT) == set(CONTRACT_GUARD_NAMES)
    assert set(guards.GUARD_REGISTRY) == set(MANDATED_VERDICT)


@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_each_mandated_verdict_is_a_published_failing_token(guard_name):
    """FR-179: the mandated outcome must be a real verdict that does not report
    success -- a control "producing" a passing verdict proves nothing."""
    token = MANDATED_VERDICT[guard_name]
    if token is None:
        pytest.skip("spec text does not pin a single token for %s" % guard_name)
    assert token in verdict.VERDICT_TOKENS
    assert verdict.is_success(token) is False


def test_no_guards_control_may_claim_a_successful_verdict():
    for guard_name, token in MANDATED_VERDICT.items():
        if token is None:
            continue
        assert token not in ("CLEAN_PASS", "PASS_WITH_ALLOWLIST"), guard_name


def test_the_retired_drops_reported_token_is_never_a_mandated_outcome():
    """FR-112: no verdict may mean "loss reported, review advisable, exit 0"."""
    assert verdict.DROPS_REPORTED not in verdict.VERDICT_TOKENS
    assert verdict.DROPS_REPORTED not in set(MANDATED_VERDICT.values())


# ---------------------------------------------------------------------------
# FR-180: absent control artifact => not-evaluated => VACUOUS
# ---------------------------------------------------------------------------


def test_the_durable_control_artifact_is_the_only_admissible_demonstration():
    """FR-180: "never an unrecorded claim or one-time manual check". A green
    test suite -- including this file -- is explicitly NOT a substitute, because
    it produces no durable artifact and cannot express staleness relative to
    guard code. So this test asserts the CURRENT honest state: while the record
    is absent, the run must not be able to claim anything.
    """
    if not CONTROLS_PATH.exists():
        results = guards.run_all_guards(guards.RunContext(project="T026"))
        assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN
    else:
        payload = json.loads(CONTROLS_PATH.read_text(encoding="utf-8"))
        for key in CONTRACT_CONTROLS_TOP_LEVEL_KEYS:
            assert key in payload, key
        recorded = {c["guard"] for c in payload["controls"]}
        assert recorded == set(CONTRACT_GUARD_NAMES), sorted(
            set(CONTRACT_GUARD_NAMES) - recorded
        )


def test_a_control_record_carries_every_contract_field():
    rec = _control("BASELINE-DELTA")
    for key in CONTRACT_CONTROL_RECORD_KEYS:
        assert key in rec, key


@pytest.mark.parametrize("dropped", CONTRACT_CONTROL_RECORD_KEYS)
def test_a_control_missing_any_field_cannot_stand_as_a_demonstration(dropped):
    """A record without its module hash cannot express staleness; one without
    its verdict cannot show the guard failed. Either is not a demonstration."""
    rec = _control("BASELINE-DELTA")
    del rec[dropped]
    assert set(CONTRACT_CONTROL_RECORD_KEYS) - set(rec) == {dropped}


# ---------------------------------------------------------------------------
# The module-hash staleness mechanic (FR-180)
# ---------------------------------------------------------------------------


def test_the_guard_module_hash_is_a_content_hash_that_moves_when_source_moves():
    """The staleness signal must be derived from the guard's own source content,
    so editing a guard without re-running its control is detectable."""
    module_path = _ROOT / "debug" / "fullsweep" / "guards.py"
    first = hashlib.sha256(module_path.read_bytes()).hexdigest()
    second = hashlib.sha256(module_path.read_bytes()).hexdigest()
    assert first == second
    assert len(first) == 64

    mutated = hashlib.sha256(module_path.read_bytes() + b"\n# edit\n").hexdigest()
    assert mutated != first


@_needs_t034
@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_guard_whose_module_changed_since_its_control_reports_not_evaluated(guard_name):
    """FR-180: a control "superseded by a later change to that guard" leaves the
    guard not-evaluated until re-demonstrated -- it MUST NOT stay passing."""
    stale = {"schema_version": 1,
             "controls": [_control(g, module_hash="0" * 64)
                          for g in CONTRACT_GUARD_NAMES]}
    outcome = guards.negative_control_result(guard_name, stale)
    assert outcome == CONTRACT_NOT_EVALUATED
    assert outcome != FORBIDDEN_DEGRADATION


@_needs_t034
@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_stale_control_makes_the_whole_run_vacuous(guard_name):
    """FR-180 + FR-109 composed: staleness is not a per-guard footnote, it sinks
    the run."""
    stale = {"schema_version": 1,
             "controls": [_control(g, module_hash="0" * 64)
                          for g in CONTRACT_GUARD_NAMES]}
    results = {
        name: guards.GuardResult(
            guard=name,
            result=guards.negative_control_result(name, stale)
            if name == guard_name else "pass",
            message="",
            evidence={},
        )
        for name in CONTRACT_GUARD_NAMES
    }
    assert verdict.verdict_for_guard_results(results) == CONTRACT_VACUOUS_TOKEN


@_needs_t034
@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_guard_with_no_recorded_control_at_all_reports_not_evaluated(guard_name):
    """FR-180: missing is treated exactly like stale."""
    empty = {"schema_version": 1, "controls": []}
    assert guards.negative_control_result(guard_name, empty) == CONTRACT_NOT_EVALUATED


@_needs_t034
@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_a_current_control_admits_the_guard_as_evidence(guard_name):
    """The regime must also be satisfiable -- otherwise nothing could ever pass
    and the guards would be decorative."""
    current = {
        "schema_version": 1,
        "controls": [_control(g, module_hash=guards.guard_module_hash(g))
                     for g in CONTRACT_GUARD_NAMES],
    }
    assert guards.negative_control_result(guard_name, current) == "pass"


@_needs_t034
@pytest.mark.parametrize("guard_name", CONTRACT_GUARD_NAMES)
def test_each_seeded_defect_produced_the_mandated_verdict(guard_name):
    """FR-179: the recorded demonstration must show the guard producing the
    specific failing verdict it exists to produce, not merely "some failure"."""
    controls = guards.load_negative_controls(CONTROLS_PATH)
    match = [c for c in controls["controls"] if c["guard"] == guard_name]
    assert match, "no recorded control for %s" % guard_name
    produced = match[0]["verdict_produced"]

    assert verdict.is_success(produced) is False
    expected = MANDATED_VERDICT[guard_name]
    if expected is not None:
        assert produced == expected


@_needs_t034
def test_a_guard_no_seeded_defect_can_fail_is_reported_as_a_defect():
    """FR-181: unfalsifiability is a defect in the sweep, never robustness."""
    controls = guards.load_negative_controls(CONTROLS_PATH)
    unfalsifiable = [c for c in controls["controls"]
                     if not c.get("seeded_defect")
                     or verdict.is_success(c["verdict_produced"])]
    assert unfalsifiable == [], (
        "guards with no constructible failing defect must be reported as sweep "
        "defects, not silently admitted: %r" % [c["guard"] for c in unfalsifiable]
    )
