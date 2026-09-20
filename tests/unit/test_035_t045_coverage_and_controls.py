"""Feature 035 -- T045: coverage honesty, and the field plane's own controls.

Source: spec.md FR-096, FR-134, FR-135, FR-137, FR-178..FR-181;
contracts/guards.md, contracts/verdict-exit-model.md, contracts/rosters.md s8.

Three things this task changed, and one it deliberately did not:

1. **FR-137 is now enforced.** ``CATEGORY-COVERAGE`` used to PASS a run whose
   exclusions all carried a reason, which made a reduced-coverage sweep and a
   full one indistinguishable at the verdict. A non-empty excluded set is now
   itself the failure; the recorded-reason check stays as a further one.
2. **FR-134/FR-135: the invisible default is gone.** ``build_full_selection``
   used to default ``exclude`` to ``{GrammarCategory.STEMS}``, so a caller who
   never typed the word "stems" shipped a run that skipped them.
3. **FR-178's Section E detectors have controls.** Four field-plane rules are
   now demonstrated capable of failing a run, through the real chain.
4. What it did NOT do: wire ``compare_structural_depth`` into a verdict. That
   gap is asserted here as a KNOWN state so the day it is closed, this file
   fails and says so rather than letting a stale claim stand.

NO FLEx project and NO LCM: every seeded defect is hand-built data.
Per FR-176 the contract tables are transcribed as INDEPENDENT literals.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "tests" / "integration")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from debug.fullsweep import guards  # noqa: E402
from debug.fullsweep import verdict  # noqa: E402

CONTROLS_PATH = (
    _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts" / "negative-controls.json"
)

#: contracts/verdict-exit-model.md: "`COVERAGE_REDUCED` | `CATEGORY-COVERAGE`
#: failed - any excluded category, any unmeasured enabled category."
CONTRACT_COVERAGE_TOKEN = "COVERAGE_REDUCED"

#: contracts/rosters.md section 8 record shape, transcribed.
CONTRACT_CONTROL_RECORD_KEYS = (
    "guard", "seeded_defect", "verdict_produced", "guard_module_hash",
    "recorded_at",
)

#: The Section E field-plane detectors T045 recorded a control for, and the
#: rule token each one's seeded defect must fire. Transcribed from the rule
#: vocabulary in ``fieldplane.py``, not imported from it.
CONTRACT_FIELD_PLANE_CONTROLS = {
    "FIELD-PLANE:ws-alternatives": "ws-alternatives",
    "FIELD-PLANE:text": "text",
    "FIELD-PLANE:order": "order",
    "FIELD-PLANE:link": "link",
}


def _ctx(**kw):
    return guards.RunContext(project="T045", **kw)


def _coverage(enabled, measured, excluded):
    return guards.guard_category_coverage(
        _ctx(enabled_categories=enabled, measured_categories=measured,
             excluded_categories=excluded))


# ===========================================================================
# FR-137 -- a reduced-coverage run never reports full-coverage success
# ===========================================================================


def test_full_coverage_with_nothing_excluded_passes():
    """The regime has to be satisfiable, or the guard is decorative."""
    result = _coverage(["pos", "stems"], ["pos", "stems"], [])
    assert result.result == "pass"
    assert result.evidence["full_coverage"] is True
    assert result.evidence["excluded_count"] == 0


def test_an_excluded_category_fails_even_with_a_recorded_reason():
    """FR-137, and the whole of T045's first half. This is the case that
    PASSED before T045: every exclusion carried a reason, so the only check
    that existed was satisfied and the run reported the same status as a
    full-coverage one."""
    result = _coverage(["pos", "stems"], ["pos"],
                       [{"category": "stems", "reason": "too slow for a pilot"}])
    assert result.result == "fail"
    assert "FR-137" in result.message
    assert result.evidence["excluded"] == ["stems"]
    assert result.evidence["excluded_count"] == 1
    assert result.evidence["full_coverage"] is False
    # The reason WAS recorded -- that is not what failed it.
    assert result.evidence["exclusions_missing_a_reason"] == []


def test_the_reduced_run_and_the_full_run_do_not_share_a_status():
    """FR-137 stated as the comparison it actually makes: two runs identical
    but for one excluded category must not end at the same verdict."""
    full = _coverage(["pos", "stems"], ["pos", "stems"], [])
    reduced = _coverage(["pos", "stems"], ["pos"],
                        [{"category": "stems", "reason": "operator chose to"}])
    assert full.result != reduced.result
    assert full.result == "pass" and reduced.result == "fail"


def test_the_failure_maps_to_coverage_reduced_and_never_to_success():
    """contracts/guards.md's "Fails as" column, and FR-111's two success
    verdicts."""
    token = guards.GUARD_FAILURE_VERDICT["CATEGORY-COVERAGE"]
    assert token == CONTRACT_COVERAGE_TOKEN
    assert token in verdict.VERDICT_TOKENS
    assert verdict.is_success(token) is False


def test_an_enabled_but_unmeasured_category_still_fails_as_fr_096():
    """The failure mode that already existed, unchanged by T045."""
    result = _coverage(["pos", "stems"], ["pos"], [])
    assert result.result == "fail"
    assert "FR-096" in result.message
    assert result.evidence["enabled_but_unmeasured"] == ["stems"]


def test_an_exclusion_with_no_reason_fails_for_both_reasons_at_once():
    """FR-135's explicitness and FR-137's reduction are separate facts about
    the same run, and a reader needs both: one says the run was narrowed, the
    other says the narrowing is not even explicable."""
    result = _coverage(["pos", "stems"], ["pos"], [{"category": "stems", "reason": ""}])
    assert result.result == "fail"
    assert "FR-137" in result.message
    assert "FR-096" in result.message
    assert result.evidence["exclusions_missing_a_reason"] == ["stems"]


def test_all_three_failure_modes_are_reported_together():
    """One run can have all three. Reporting them one at a time would make
    fixing the first reveal the second on the NEXT run instead of this one."""
    result = _coverage(
        ["pos", "stems", "affixes"], ["pos"],
        [{"category": "stems", "reason": ""}])
    assert result.result == "fail"
    assert result.message.count("FR-") >= 3
    assert result.evidence["enabled_but_unmeasured"] == ["affixes"]
    assert result.evidence["excluded"] == ["stems"]
    assert result.evidence["exclusions_missing_a_reason"] == ["stems"]


@pytest.mark.parametrize("missing", ["enabled_categories", "measured_categories",
                                     "excluded_categories"])
def test_a_missing_input_still_reports_not_evaluated_never_pass(missing):
    """FR-109: a guard that cannot be evaluated must never report pass, and
    T045 must not have turned an unmeasured input into a fail either -- that
    would be a different lie."""
    kw = {"enabled_categories": ["pos"], "measured_categories": ["pos"],
          "excluded_categories": []}
    kw[missing] = None
    assert guards.guard_category_coverage(_ctx(**kw)).result == "not-evaluated"


def test_the_seeded_defect_for_this_guard_still_fires():
    """FR-179: T045 rewrote the guard, so its own control must be re-checked
    rather than assumed to still hold."""
    ctx = guards._seeded_context("CATEGORY-COVERAGE")
    assert guards.guard_category_coverage(ctx).result == "fail"


# ===========================================================================
# FR-134 / FR-135 -- the stem-allomorph category, and the invisible default
# ===========================================================================


def _full_run():
    from harness import full_run
    return full_run


def test_build_full_selection_has_no_default_exclusion():
    """FR-135: an exclusion MUST NOT be "expressed as an invisible default
    argument that a reader of the results cannot see". It was one here, for
    the entire life of this harness."""
    param = inspect.signature(_full_run().build_full_selection).parameters["exclude"]
    assert param.default is inspect.Parameter.empty


def test_calling_it_with_no_exclusion_at_all_is_now_an_error():
    """The consequence that makes the requirement enforceable rather than
    documentary: inheriting the narrow shape is no longer possible."""
    with pytest.raises(TypeError):
        _full_run().build_full_selection()


def test_full_coverage_enables_the_stem_allomorph_category():
    """FR-134: "The stem-allomorph object category MUST be enabled for at
    least one full corpus pass"."""
    full_run = _full_run()
    on = {c.value for c, enabled
          in full_run.build_full_selection(exclude=full_run.FULL_COVERAGE)
          .categories.items() if enabled}
    assert "stems" in on
    assert full_run.FULL_COVERAGE == frozenset()


def test_the_historical_stemless_shape_is_still_reachable_but_must_be_named():
    """FR-134 forbids inheriting the narrower exclusion UNEXAMINED. It does
    not forbid the shape -- it forbids getting it by accident."""
    full_run = _full_run()
    on = {c.value for c, enabled
          in full_run.build_full_selection(exclude=full_run.LEGACY_STEMLESS_EXCLUSION)
          .categories.items() if enabled}
    assert "stems" not in on
    assert "affixes" in on


def test_no_caller_in_the_tree_inherits_the_exclusion_any_more():
    """The audit that makes the two tests above worth something: a call with
    no exclusion argument anywhere would reintroduce exactly the defect, and
    would do so silently. Read as syntax rather than as text, so a mention in
    a docstring or in this file's own ``pytest.raises`` is not an offender.
    """
    import ast

    offenders = []
    for path in sorted(_ROOT.glob("**/*.py")):
        if "__pycache__" in path.parts or path == Path(__file__):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            called = (fn.attr if isinstance(fn, ast.Attribute)
                      else fn.id if isinstance(fn, ast.Name) else None)
            if called == "build_full_selection" and not node.args and not node.keywords:
                offenders.append("%s:%d" % (path.relative_to(_ROOT), node.lineno))
    assert offenders == [], (
        "these call sites inherit an exclusion a reader of their results "
        "cannot see (FR-135): %r" % (offenders,))


def test_the_sweeps_own_empty_exclusion_keeps_stems():
    """End to end through the driver's own resolver, which is what a real
    ``--exclude-categories ''`` produces."""
    import importlib
    driver = importlib.import_module("debug.run_fullcopy_sweep")
    full_run = _full_run()
    members, records = driver.resolve_excluded_categories([])
    assert members == frozenset() and records == []
    on = {c.value for c, enabled
          in full_run.build_full_selection(exclude=members).categories.items()
          if enabled}
    assert "stems" in on


# ===========================================================================
# FR-178/FR-179 -- the Section E field-plane detectors
# ===========================================================================


def test_the_four_field_plane_controls_are_named_and_cannot_collide():
    """They are detectors, not guards: FR-109's completeness assertion is over
    the fifteen registry keys alone, and a name that could be mistaken for one
    of them would break that set equality in a confusing way."""
    assert set(guards.FIELD_PLANE_CONTROL_NAMES) == set(CONTRACT_FIELD_PLANE_CONTROLS)
    assert not set(guards.FIELD_PLANE_CONTROL_NAMES) & set(guards.GUARD_NAMES)
    for name in guards.FIELD_PLANE_CONTROL_NAMES:
        assert name.startswith("FIELD-PLANE:")


@pytest.mark.parametrize("name", sorted(CONTRACT_FIELD_PLANE_CONTROLS))
def test_each_seeded_field_defect_fails_the_run_through_its_own_rule(name):
    """FR-179 for the field plane. Both halves matter: that the run failed,
    and that it failed through the rule the defect was built for. A defect
    that failed through a DIFFERENT rule would record a demonstration of the
    wrong detector, which reads as coverage while being none."""
    token, rule, detail = guards._field_plane_control(name)
    assert rule == CONTRACT_FIELD_PLANE_CONTROLS[name], detail
    assert detail["guard_result"] == "fail", detail
    assert token == "UNEXPLAINED_LOSS"
    assert verdict.is_success(token) is False


def test_the_field_plane_reaches_a_verdict_only_through_total_accounting():
    """Recorded because it is load-bearing and non-obvious: the field plane
    has no verdict channel of its own. Every finding becomes a False from
    ``payload_equal``, an unaccounted object, and a TOTAL-ACCOUNTING failure.
    A detector with no route into the accounting therefore reaches no verdict
    at all -- which is exactly the depth gap below."""
    assert guards.FIELD_PLANE_VERDICT_VIA == "TOTAL-ACCOUNTING"
    for name in guards.FIELD_PLANE_CONTROL_NAMES:
        _t, _r, detail = guards._field_plane_control(name)
        assert detail["guard"] == "TOTAL-ACCOUNTING"


def test_an_undistorted_pair_does_not_fail_the_same_chain():
    """The control of the controls. Four seeded defects all failing proves
    nothing if the chain fails everything handed to it."""
    from debug.fullsweep import compare as compare_mod
    from debug.fullsweep import fieldplane as fp

    values = {"LexEntry": {guards._CONTROL_OWNER: {"CitationForm": "ngoreme"}}}
    census = guards._ControlCensus(values)
    comparator = fp.FieldPlaneComparator(
        source_census=census, target_census=census,
        ws_mapping=compare_mod.build_writing_system_mapping(("en",), ("en",)),
        source_ws_keys=("en",), target_ws_keys=("en",), target_ws_tags=("en",),
        drops=(),
    )
    ids = {"LexEntry": {guards._CONTROL_OWNER}}
    accounting = compare_mod.reconcile_objects(
        ids, ids, ids, project="T045", payload_equal=comparator.payload_equal)
    result = guards.guard_total_accounting(_ctx(accounting=accounting))
    assert result.result == "pass"
    assert comparator.value_findings() == []


@pytest.mark.parametrize("name", sorted(CONTRACT_FIELD_PLANE_CONTROLS))
def test_a_field_plane_controls_staleness_covers_both_its_modules(name):
    """FR-180: a control is stale when the logic it demonstrated changed. The
    rule lives in ``compare.py`` and the dispatch that chooses it lives in
    ``fieldplane.py``; hashing only one would let an edit to the other pass as
    still-demonstrated."""
    base = _ROOT / "debug" / "fullsweep"
    recorded = guards.guard_module_hash(name)
    both = hashlib.sha256()
    for fname in ("compare.py", "fieldplane.py"):
        both.update((base / fname).read_bytes())
    assert recorded == "sha256:%s" % both.hexdigest()

    for fname in ("compare.py", "fieldplane.py"):
        only_one = hashlib.sha256((base / fname).read_bytes()).hexdigest()
        assert recorded != "sha256:%s" % only_one


def test_the_fifteen_guards_still_hash_their_own_module_alone():
    """The multi-module table must not have changed the fifteen: their
    recorded hashes would all go stale at once for no reason."""
    guards_py = (_ROOT / "debug" / "fullsweep" / "guards.py").read_bytes()
    expected = "sha256:%s" % hashlib.sha256(guards_py).hexdigest()
    for name in guards.GUARD_NAMES:
        assert guards.guard_module_hash(name) == expected


@pytest.mark.parametrize("name", sorted(CONTRACT_FIELD_PLANE_CONTROLS))
def test_the_durable_artifact_records_each_field_plane_control(name):
    """FR-180: the demonstration is the tracked record, never this test."""
    controls = guards.load_negative_controls(CONTROLS_PATH)
    match = [c for c in controls["controls"] if c["guard"] == name]
    assert match, "no recorded control for %s" % name
    record = match[0]
    for key in CONTRACT_CONTROL_RECORD_KEYS:
        assert key in record, key
    assert verdict.is_success(record["verdict_produced"]) is False
    assert record["seeded_defect"]


def test_every_recorded_control_is_current_against_its_own_modules():
    """FR-180 composed with T045's own edit: this task changed ``guards.py``,
    which staled all fifteen records at once. Re-running the suite is part of
    the task, and this is what proves it was not skipped."""
    controls = guards.load_negative_controls(CONTROLS_PATH)
    stale = [c["guard"] for c in controls["controls"]
             if guards.negative_control_result(c["guard"], controls) != "pass"]
    assert stale == [], (
        "re-run `python debug/run_fullcopy_sweep.py negative-controls`: %r"
        % (stale,))


# ===========================================================================
# The one Section E detector T045 could not give a control, asserted as known
# ===========================================================================


def test_the_depth_detector_has_no_control_and_the_reason_is_recorded():
    """FR-178 requires a control for every Section E detector, and
    ``compare_structural_depth`` does not have one. Not an oversight: a seeded
    per-parent degree disagreement populates the artifact's depth block and
    reaches no verdict, because nothing reads that block. Recording a control
    would mean writing down a verdict token the run does not produce.

    This test pins the gap so it cannot be quietly forgotten OR quietly fixed:
    when T071 wires depth into a verdict, this fails and says so.
    """
    controls = guards.load_negative_controls(CONTROLS_PATH)
    recorded = {c["guard"] for c in controls["controls"]}
    assert not any(g.startswith("FIELD-PLANE:structural-depth") for g in recorded)
    assert "T071" in guards.FIELD_PLANE_DETECTOR_WITHOUT_A_CONTROL


def test_a_degree_disagreement_is_detected_and_reaches_no_verdict():
    """The measurement behind the test above, taken rather than asserted from
    memory: the detector DOES fire, and the artifact block it fires into is
    read by nothing."""
    from debug.fullsweep import artifact as artifact_mod
    from debug.fullsweep import compare as compare_mod

    parent = guards._CONTROL_OWNER
    result = compare_mod.compare_structural_depth(
        "LexSense",
        source_children={parent: [guards._CONTROL_GUID_A, guards._CONTROL_GUID_B]},
        target_children={parent: [guards._CONTROL_GUID_A]},
        source_roots=(parent,), target_roots=(parent,),
    )
    block = artifact_mod.depth_block([result])
    assert block["per_parent_degree_findings"], "the detector itself must fire"

    # ... and nothing reads it. Asserted structurally rather than over a guess
    # about which guard it "should" be: RunContext is the ONLY surface a guard
    # can read, and it has no depth field of any name. The driver's side is
    # asserted too, since a guard could only get one if the driver deposited
    # it.
    depth_fields = [f for f in guards.RunContext.__dataclass_fields__
                    if "depth" in f or "degree" in f or "nesting" in f]
    assert depth_fields == [], (
        "RunContext grew a depth input -- if a guard now reads it, this "
        "detector has a verdict and needs a control: %r" % (depth_fields,))
    driver_src = (_ROOT / "debug" / "run_fullcopy_sweep.py").read_text(encoding="utf-8")
    assert 'measured["depth"]' not in driver_src


def test_the_artifact_schema_still_separates_the_three_depth_dispositions():
    """T045f's ruling, re-asserted because T071 will touch this block: the
    corpus never nesting a class is NOT the target losing the nesting."""
    from debug.fullsweep import artifact as artifact_mod

    block = artifact_mod.depth_block([])
    assert set(block) >= {"per_parent_degree_findings", "vacuous_classes",
                          "not_evaluated_classes"}
    assert block["vacuous_classes"] == [] and block["not_evaluated_classes"] == []


# ===========================================================================
# The suite as a whole
# ===========================================================================


def test_the_control_suite_covers_the_fifteen_guards_and_the_four_detectors():
    outcomes = guards.run_negative_controls()
    assert len(outcomes) == len(guards.GUARD_NAMES) + len(
        guards.FIELD_PLANE_CONTROL_NAMES)
    assert [o.guard for o in outcomes[:len(guards.GUARD_NAMES)]] == list(
        guards.GUARD_NAMES)
    assert [o.guard for o in outcomes[len(guards.GUARD_NAMES):]] == list(
        guards.FIELD_PLANE_CONTROL_NAMES)


def test_no_control_in_the_suite_is_unfalsifiable():
    """FR-181: a detector no constructible defect can fail is a defect in the
    sweep, never evidence of robustness."""
    unfalsifiable = [o.guard for o in guards.run_negative_controls() if o.unfalsifiable]
    assert unfalsifiable == []


def test_the_tracked_artifact_is_valid_json_with_the_contract_top_level():
    payload = json.loads(CONTROLS_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert isinstance(payload["controls"], list)
    guards_seen = [c["guard"] for c in payload["controls"]]
    assert len(guards_seen) == len(set(guards_seen)), "one record per detector"
