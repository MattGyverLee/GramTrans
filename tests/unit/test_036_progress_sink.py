"""Tests: Qt-free progress surface (feature 036, US1 foundation).

T002 -- test_036_progress_sink.py
FR-014, FR-014b, FR-014c, FR-014d, FR-015..FR-017, FR-019a, FR-020, FR-022,
FR-045; contracts/progress-sink.md; data-model.md sections 2 and 3.

This module tests `gramtrans.Lib.progress`, which is **Qt-free by contract**.
`Lib/selection.py` imports it, and `Lib/selection.py` must stay importable with
no `QApplication` -- exactly as `Lib/merge_preview.py` is (proven by
`test_merge_preview_qt_free.py`, whose static/subprocess pattern is mirrored
below). So, deliberately, for everything above the T016 banner near the end of
this file:

  - `QT_QPA_PLATFORM` is NOT set at module scope,
  - PyQt6 is NOT imported at module scope and NOT `importorskip`-ed there,
  - that whole half runs on a bare interpreter.

If a future edit makes `Lib/progress.py` reach for Qt, three tests here fail
(static AST scan, source-substring scan, blocked-import subprocess) rather than
the breakage surfacing later as a headless crash inside a wizard build.

T016 adds the other half of the same protocol -- `Lib/ui/progress_indicator.py`,
the ONE Qt implementation -- to this same file, because the two halves are one
contract and a reader chasing "what does a sink do" should find both answers in
one place. The Qt half is quarantined behind the `qt_env` fixture: the
`importorskip`, the offscreen platform pin and the `QApplication` all live inside
that fixture body, so a machine with no PyQt6 skips those tests and still runs
every Qt-free test above. Nothing at module scope touches Qt or the environment.

What is covered:
  - `PROGRESS_THRESHOLD_MS == 500`, declared in exactly ONE place (FR-019a)
  - `predicted_ms` / `warrants_indicator`, including the
    `warrants_indicator(None, rate) is False` rule (FR-014d)
  - `NullSink` is a true no-op with no per-instance allocation (FR-022, FR-045)
  - `reporting()` calls `end` through a normal exit AND through an exception,
    and re-raises that exception rather than swallowing it (FR-020)
  - `end` is idempotent; `tick` never raises, including after `end`
  - `SourceCounts` returns `None` ("unknown") instead of raising, and never
    performs a counting pass (FR-014d)
  - the `UNITS_PER_SECOND` per-operation calibration table (T019)
  - T016: the Qt sink -- `deferred()` shows nothing for work that finishes
    first (FR-019, SC-001a), `immediate()` is on screen before the work starts
    (FR-014a, SC-001b), a nested `begin` re-labels the one indicator and the
    matching `end` restores the outer label (FR-021), an overrun `total`
    degrades to indeterminate, a failure path still dismisses (FR-020), `tick`
    pumps the event loop on a time-based throttle (FR-018, SC-002), and the
    indicator sets no colour of its own
"""

from __future__ import annotations

import ast
import math
import os
import pathlib
import re
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from gramtrans.Lib import progress as prog

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_MODULE_PATH = _REPO_ROOT / "src" / "gramtrans" / "Lib" / "progress.py"
_QT_SINK_PATH = _REPO_ROOT / "src" / "gramtrans" / "Lib" / "ui" / "progress_indicator.py"


# ===========================================================================
# Recording sinks (test doubles -- the only "real" sink in a Qt-free world)
# ===========================================================================


class _RecordingSink:
    """Records the begin/tick/end call sequence so ordering can be asserted."""

    def __init__(self) -> None:
        self.calls: list = []

    def begin(self, label, total=None) -> None:
        self.calls.append(("begin", label, total))

    def tick(self, n: int = 1) -> None:
        self.calls.append(("tick", n))

    def end(self) -> None:
        self.calls.append(("end",))


class _EndExplodesSink(_RecordingSink):
    """A sink whose display teardown fails.

    A broken indicator must never become the exception the caller sees: the
    operation's own error is the one that matters (FR-020).
    """

    def end(self) -> None:
        self.calls.append(("end",))
        raise RuntimeError("display teardown blew up")


# ===========================================================================
# FR-019a -- the one threshold, declared once
# ===========================================================================


def test_threshold_is_500_ms():
    """The single project-wide threshold is 500 ms (FR-019a, data-model s2)."""
    assert prog.PROGRESS_THRESHOLD_MS == 500


def test_threshold_declared_in_exactly_one_place():
    """`PROGRESS_THRESHOLD_MS` is assigned in exactly one file: Lib/progress.py.

    FR-019a makes this a structural property, not a style preference: the
    constant is used twice (elapsed-time delay, anticipated-cost bar) and a
    second declaration would let the two uses drift apart silently.
    """
    declarations: list = []
    for root in (_REPO_ROOT / "src", _REPO_ROOT / "tests"):
        for py in root.rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
                continue
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                for tgt in targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "PROGRESS_THRESHOLD_MS":
                        declarations.append(str(py.relative_to(_REPO_ROOT)))

    assert len(declarations) == 1, (
        "PROGRESS_THRESHOLD_MS must be declared exactly once (FR-019a); found "
        f"{len(declarations)}: {declarations}"
    )
    assert declarations[0].replace("\\", "/").endswith("src/gramtrans/Lib/progress.py")


# ===========================================================================
# Qt-free guarantee (contract preamble; mirrors test_merge_preview_qt_free.py)
# ===========================================================================


def test_progress_module_has_no_qt_import_statement():
    """Static AST scan: no PyQt/PySide import anywhere in Lib/progress.py."""
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    qt_imports = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            if any(qt in name for qt in ("PyQt", "PySide")):
                qt_imports.append(name)
    assert qt_imports == [], f"Qt imports found in Lib/progress.py: {qt_imports}"


def test_progress_module_source_never_mentions_qt():
    """Source-substring scan -- catches a lazy/in-function or string-built import.

    Cheaper and broader than the AST scan, and it also fails on a
    `importlib.import_module("PyQt6...")` that the AST scan cannot see.
    """
    source = _MODULE_PATH.read_text(encoding="utf-8")
    for token in ("PyQt", "PySide", "QApplication", "QtWidgets", "QtCore"):
        assert token not in source, (
            f"Lib/progress.py mentions {token!r}; the module is Qt-free by "
            "contract because Lib/selection.py imports it and must stay "
            "importable headless"
        )


def test_progress_module_source_is_ascii():
    """No non-ASCII characters: Windows terminals mangle them (house rule)."""
    source = _MODULE_PATH.read_text(encoding="utf-8")
    offenders = sorted({ch for ch in source if ord(ch) > 127})
    assert offenders == [], f"non-ASCII characters in Lib/progress.py: {offenders!r}"


def test_imports_and_runs_with_qt_blocked():
    """Import + exercise the module in a subprocess with every Qt flavour blocked.

    The sentinel modules are empty, so any real attribute access on them fails;
    a transitive Qt import would surface as an ImportError or AttributeError.
    """
    src_dir = str(_REPO_ROOT / "src")
    script = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, %s)

        # Block every Qt flavour with an empty sentinel module.
        for _blocked in ("PyQt6", "PyQt5", "PySide2", "PySide6"):
            sys.modules[_blocked] = type(sys)(_blocked)

        try:
            import gramtrans.Lib.progress as p
        except Exception as e:
            print("IMPORT_ERROR: " + repr(e), flush=True)
            sys.exit(1)

        assert p.PROGRESS_THRESHOLD_MS == 500
        assert p.warrants_indicator(None, 100.0) is False
        assert p.predicted_ms(1000, 500.0) == 2000.0

        sink = p.NullSink()
        with p.reporting(sink, "Reading texts...", 3) as s:
            s.tick()
            s.tick(2)
        sink.end()

        counts = p.SourceCounts(None)
        assert counts.lexicon_entries is None
        assert counts.phonology is None

        assert len(p.UNITS_PER_SECOND) == 13

        print("QT_FREE_OK", flush=True)
        """
    ) % repr(src_dir)

    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, (
        f"Qt-free subprocess failed.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    assert "QT_FREE_OK" in result.stdout, f"sentinel missing.\nSTDOUT: {result.stdout}"


# ===========================================================================
# AnticipatedSize -- predicted_ms (data-model section 3)
# ===========================================================================


@pytest.mark.parametrize(
    "total,rate,expected",
    [
        (1000, 500.0, 2000.0),  # 1000 units at 500/s => 2 s
        (250, 500.0, 500.0),  # exactly the threshold
        (1, 1000.0, 1.0),
        (0, 500.0, 0.0),  # nothing to do costs nothing
    ],
)
def test_predicted_ms_arithmetic(total, rate, expected):
    """predicted_ms = total_units / units_per_second * 1000 (data-model s3)."""
    assert prog.predicted_ms(total, rate) == pytest.approx(expected)


def test_predicted_ms_of_unknown_size_is_zero():
    """An unknown size predicts nothing.

    `None` means "size not cheaply knowable", which the elapsed-time fallback
    covers (FR-014b/FR-014d) -- not a prediction. Returning 0.0 keeps
    `warrants_indicator` False for that case without a second code path.
    """
    assert prog.predicted_ms(None, 500.0) == 0.0


def test_predicted_ms_of_negative_total_is_zero():
    """A nonsense total never yields a negative duration."""
    assert prog.predicted_ms(-5, 500.0) == 0.0


@pytest.mark.parametrize("rate", [0.0, -1.0, None])
def test_predicted_ms_without_a_usable_rate_is_infinite(rate):
    """Zero throughput never finishes, so the prediction is +inf, not a crash."""
    assert math.isinf(prog.predicted_ms(100, rate))


# ===========================================================================
# AnticipatedSize -- warrants_indicator (FR-014a, FR-014d)
# ===========================================================================


def test_warrants_indicator_none_total_is_false():
    """FR-014d: unknown size => elapsed-time fallback governs, not up-front display.

    This is the load-bearing assertion of the whole prediction rule: an
    unknowable size must NOT force an indicator on screen before the work
    starts, because we have no basis for claiming the wait will be long.
    """
    assert prog.warrants_indicator(None, 500.0) is False


def test_warrants_indicator_at_the_threshold_is_true():
    """`>=` not `>`: 250 units at 500/s is exactly 500 ms and clears the bar."""
    assert prog.warrants_indicator(250, 500.0) is True


def test_warrants_indicator_below_the_threshold_is_false():
    """200 ms of predicted work shows nothing up front -- no flash (FR-019)."""
    assert prog.warrants_indicator(100, 500.0) is False


def test_warrants_indicator_above_the_threshold_is_true():
    assert prog.warrants_indicator(100_000, 500.0) is True


@pytest.mark.parametrize("rate", [None, 0.0, -1.0])
def test_warrants_indicator_without_a_calibration_is_false(rate):
    """No calibration constant => no prediction => elapsed-time fallback.

    Deliberately NOT True: an uncalibrated operation must not be given a
    permanent up-front indicator just because its rate is missing.
    """
    assert prog.warrants_indicator(100, rate) is False


def test_warrants_indicator_returns_a_real_bool():
    """The contract says `-> bool`; `is True` / `is False` must hold."""
    assert prog.warrants_indicator(250, 500.0) is True
    assert prog.warrants_indicator(1, 500.0) is False


# ===========================================================================
# ProgressSink protocol + NullSink (FR-022, FR-045)
# ===========================================================================


def test_null_sink_satisfies_the_protocol():
    assert isinstance(prog.NullSink(), prog.ProgressSink)
    assert isinstance(_RecordingSink(), prog.ProgressSink)


def test_null_sink_methods_are_no_ops():
    """Every method returns None and does nothing observable."""
    sink = prog.NullSink()
    assert sink.begin("Reading texts...", 42) is None
    assert sink.begin("Opening source project...") is None
    assert sink.tick() is None
    assert sink.tick(10_000) is None
    assert sink.end() is None


def test_null_sink_allocates_no_per_instance_state():
    """FR-022/FR-045: `progress=None` costs nothing observable.

    `__slots__ = ()` means a NullSink has no instance `__dict__` at all -- no
    counter, no timestamp, nothing the walk could pay for or observe.
    """
    sink = prog.NullSink()
    assert not hasattr(sink, "__dict__")
    with pytest.raises(AttributeError):
        sink.completed = 1  # type: ignore[attr-defined]


def test_null_sink_singleton_is_reusable():
    """A module-level singleton so callers need not allocate at all."""
    assert isinstance(prog.NULL_SINK, prog.NullSink)
    prog.NULL_SINK.begin("x", 1)
    prog.NULL_SINK.tick()
    prog.NULL_SINK.end()
    prog.NULL_SINK.end()


def test_null_sink_end_is_idempotent():
    """`end` may be called any number of times (contract guarantee)."""
    sink = prog.NullSink()
    sink.begin("Reading rules...", 5)
    sink.end()
    sink.end()
    sink.end()


def test_null_sink_tick_never_raises_after_end():
    """A nested walk that outlives its indicator must not take the run down.

    Contract: "a sink whose display has already been dismissed absorbs further
    ticks silently".
    """
    sink = prog.NullSink()
    sink.begin("Reading stems...", 2)
    sink.end()
    for _ in range(1000):
        sink.tick()


def test_tick_never_raises_without_begin():
    """Out-of-order use is absorbed, not punished."""
    prog.NullSink().tick(5)
    prog.NullSink().end()


# ===========================================================================
# reporting() context manager (FR-020)
# ===========================================================================


def test_reporting_calls_begin_then_end_on_normal_exit():
    sink = _RecordingSink()
    with prog.reporting(sink, "Reading affixes...", 7) as yielded:
        assert yielded is sink
        yielded.tick(3)
    assert sink.calls == [
        ("begin", "Reading affixes...", 7),
        ("tick", 3),
        ("end",),
    ]


def test_reporting_defaults_total_to_none_for_indeterminate_work():
    """FR-017: no total => indeterminate, and `total` is optional."""
    sink = _RecordingSink()
    with prog.reporting(sink, "Opening source project..."):
        pass
    assert sink.calls == [("begin", "Opening source project...", None), ("end",)]


def test_reporting_calls_end_through_an_exception_and_re_raises():
    """FR-020: success, failure and abandonment all dismiss the indicator.

    The exception must reach the caller unchanged -- the existing error path is
    what surfaces it to the operator; `reporting` only guarantees dismissal.
    """
    sink = _RecordingSink()
    boom = ValueError("inventory walk failed")
    with pytest.raises(ValueError) as excinfo, prog.reporting(sink, "Reading phonology...", 3):
        sink.tick()
        raise boom
    assert excinfo.value is boom
    assert sink.calls == [
        ("begin", "Reading phonology...", 3),
        ("tick", 1),
        ("end",),
    ]


def test_reporting_does_not_swallow_generatorexit_style_control_flow():
    """`break` out of a loop inside the block still ends the indicator."""
    sink = _RecordingSink()
    for _ in range(3):
        with prog.reporting(sink, "Reading texts...", 3):
            break
    assert sink.calls[-1] == ("end",)


def test_reporting_with_a_broken_end_still_propagates_the_real_error():
    """A failing indicator teardown must not mask the operation's own failure."""
    sink = _EndExplodesSink()
    with pytest.raises(ValueError, match="real failure"), prog.reporting(
        sink, "Writing to the target project...", 2
    ):
        raise ValueError("real failure")
    assert ("end",) in sink.calls


def test_reporting_with_a_broken_end_does_not_raise_on_a_clean_exit():
    """No operation error to report, and a display fault is not one either."""
    sink = _EndExplodesSink()
    with prog.reporting(sink, "Reading rules...", 1):
        pass
    assert sink.calls == [("begin", "Reading rules...", 1), ("end",)]


def test_reporting_accepts_none_as_the_sink():
    """`progress=None` is the documented "no sink" value and must be free."""
    with prog.reporting(None, "Reading custom fields...", 4) as sink:
        assert isinstance(sink, prog.NullSink)
        sink.tick()


# ===========================================================================
# T019 -- per-operation units_per_second calibration table
# ===========================================================================

_EXPECTED_OPERATIONS = {
    "bind_source",
    "bind_target",
    "custom_fields",
    "phonology",
    "affixes",
    "stems",
    "skeleton",
    "dependencies",
    "entry_types",
    "rules",
    "texts",
    "plan_assembly",
    "move_write",
}


def test_units_per_second_covers_the_13_fr023_operations():
    """One key per row of the FR-023 "Covered operations" table."""
    assert set(prog.UNITS_PER_SECOND) == _EXPECTED_OPERATIONS
    assert len(prog.UNITS_PER_SECOND) == 13


def test_the_two_bind_operations_have_no_rate():
    """Rows 1-2 have no cheap total, so they are elapsed-triggered only.

    `None` records that fact explicitly rather than inventing a rate that
    could never be applied (data-model s3).
    """
    assert prog.UNITS_PER_SECOND["bind_source"] is None
    assert prog.UNITS_PER_SECOND["bind_target"] is None


def test_every_other_operation_has_a_positive_rate():
    for name, rate in prog.UNITS_PER_SECOND.items():
        if name in ("bind_source", "bind_target"):
            continue
        assert isinstance(rate, (int, float)), f"{name}: rate is {rate!r}"
        assert rate > 0, f"{name}: units_per_second must be positive, got {rate!r}"


def test_the_threshold_is_not_smuggled_into_the_rate_table():
    """FR-019a: the 500 ms threshold is NOT a per-operation number."""
    assert not any("threshold" in k.lower() for k in prog.UNITS_PER_SECOND)
    assert "PROGRESS_THRESHOLD_MS" not in prog.UNITS_PER_SECOND


def test_rate_for_returns_the_table_value():
    assert prog.rate_for("texts") == prog.UNITS_PER_SECOND["texts"]
    assert prog.rate_for("bind_source") is None


def test_rate_for_an_unknown_operation_fails_loudly():
    """A typo'd operation name is a wiring bug, caught at wiring time.

    This lookup happens when a page sets up its indicator, never inside a
    walk, so failing loudly here costs no runtime safety.
    """
    with pytest.raises(KeyError):
        prog.rate_for("reading_the_tea_leaves")


# ===========================================================================
# T004 -- SourceCounts (cheap, O(1), never raises, never counts)
# ===========================================================================


class _FakeCount:
    """Stands in for an LCM owning/reference collection.

    `.Count` is O(1); `__iter__` raises so any counting pass in `SourceCounts`
    fails the test loudly instead of merely being slow (FR-014d).
    """

    def __init__(self, count) -> None:
        self.Count = count

    def __iter__(self):  # pragma: no cover - must never be reached
        raise AssertionError("SourceCounts performed a counting pass (FR-014d)")


class _FakeList(_FakeCount):
    """A CmPossibilityList: the item count lives on `PossibilitiesOS`."""

    def __init__(self, count) -> None:
        super().__init__(0)
        self.PossibilitiesOS = _FakeCount(count)


class _FakeCustomFields:
    def __init__(self, per_class: int) -> None:
        self._per_class = per_class

    def GetAllFields(self, owner_class):  # noqa: N802 - mirrors flexicon
        return [(1000 + i, f"cf{i}") for i in range(self._per_class)]


def _fake_project(
    *,
    entries=12,
    texts=3,
    per_class_custom_fields=2,
    phoneme_sets=1,
    natural_classes=5,
    phon_rules=4,
    variant_types=6,
    complex_types=7,
    adhoc=8,
):
    """Duck-typed stand-in for a bound flexicon project handle.

    Mirrors the accessor paths `Lib/selection.py` and `Lib/categories.py`
    already use, so `SourceCounts` is proven against the real shape:
    `Cache.LangProject.PhonologicalDataOA.*`,
    `Cache.LangProject.LexDbOA.{Variant,Complex}EntryTypesOA`,
    `Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC`.
    """

    class _Obj:
        pass

    phon = _Obj()
    phon.PhonemeSetsOS = _FakeCount(phoneme_sets)
    phon.NaturalClassesOS = _FakeCount(natural_classes)
    phon.PhonRulesOS = _FakeCount(phon_rules)

    lex_db = _Obj()
    lex_db.VariantEntryTypesOA = _FakeList(variant_types)
    lex_db.ComplexEntryTypesOA = _FakeList(complex_types)

    morph = _Obj()
    morph.AdhocCoProhibitionsOC = _FakeCount(adhoc)

    lp = _Obj()
    lp.PhonologicalDataOA = phon
    lp.LexDbOA = lex_db
    lp.MorphologicalDataOA = morph

    cache = _Obj()
    cache.LangProject = lp

    proj = _Obj()
    proj.Cache = cache
    proj.CustomFields = _FakeCustomFields(per_class_custom_fields)
    proj.LexiconNumberOfEntries = lambda: entries
    proj.TextsNumberOfTexts = lambda: texts
    return proj


def test_source_counts_reads_every_declared_count():
    """Every cheap total in data-model s3 is available after one bind."""
    counts = prog.SourceCounts(_fake_project())
    assert counts.lexicon_entries == 12
    assert counts.texts == 3
    assert counts.custom_fields == 8  # 2 per class x 4 owner classes
    assert counts.phoneme_sets == 1
    assert counts.natural_classes == 5
    assert counts.phonological_rules == 4
    assert counts.variant_types == 6
    assert counts.complex_form_types == 7
    assert counts.adhoc_prohibitions == 8


def test_source_counts_aggregates_match_the_wizard_pages():
    """Page-level totals for FR-023 rows 4, 9 and 10."""
    counts = prog.SourceCounts(_fake_project())
    assert counts.phonology == 1 + 5 + 4
    assert counts.entry_types == 6 + 7
    assert counts.rules == 8


def test_source_counts_never_iterates_a_collection():
    """FR-014d: O(1) reads only -- never a counting pass.

    The fakes raise `AssertionError` from `__iter__`, so any iteration would
    surface here rather than as an unexplained pause in front of the operator.
    """
    counts = prog.SourceCounts(_fake_project())
    # Touch every accessor; none of them may iterate.
    _ = (
        counts.lexicon_entries,
        counts.texts,
        counts.custom_fields,
        counts.phonology,
        counts.entry_types,
        counts.rules,
    )
    assert counts.as_dict()["natural_classes"] == 5


def test_source_counts_of_no_source_is_all_unknown():
    """No bound source => every count is `None`, and nothing raises."""
    counts = prog.SourceCounts(None)
    assert counts.lexicon_entries is None
    assert counts.texts is None
    assert counts.custom_fields is None
    assert counts.phoneme_sets is None
    assert counts.natural_classes is None
    assert counts.phonological_rules is None
    assert counts.variant_types is None
    assert counts.complex_form_types is None
    assert counts.adhoc_prohibitions is None
    assert counts.phonology is None
    assert counts.entry_types is None
    assert counts.rules is None
    assert set(counts.as_dict().values()) == {None}


def test_source_counts_unknown_constructor():
    """`SourceCounts.unknown()` is the explicit "nothing bound yet" value."""
    counts = prog.SourceCounts.unknown()
    assert isinstance(counts, prog.SourceCounts)
    assert counts.lexicon_entries is None


def test_source_counts_absorbs_a_raising_probe():
    """A probe that throws yields `None`, never an exception (FR-014d).

    Binding a project must not fail because one metadata read is unhappy; an
    unknown count degrades the indicator to indeterminate and nothing else.
    """
    proj = _fake_project()

    def _boom():
        raise RuntimeError("LCM said no")

    proj.LexiconNumberOfEntries = _boom
    counts = prog.SourceCounts(proj)
    assert counts.lexicon_entries is None
    assert counts.texts == 3  # unrelated probes still resolved


def test_source_counts_absorbs_a_missing_accessor_chain():
    """A handle with no `Cache` at all is "unknown", not an AttributeError."""

    class _Bare:
        pass

    proj = _Bare()
    proj.LexiconNumberOfEntries = lambda: 42
    counts = prog.SourceCounts(proj)
    assert counts.lexicon_entries == 42
    assert counts.phoneme_sets is None
    assert counts.phonology is None


def test_source_counts_rejects_a_non_integer_count():
    """A `.Count` that is not an int is "unknown", not a bogus total."""
    proj = _fake_project()
    proj.Cache.LangProject.PhonologicalDataOA.NaturalClassesOS = _FakeCount("many")
    counts = prog.SourceCounts(proj)
    assert counts.natural_classes is None


def test_aggregate_is_unknown_when_any_part_is_unknown():
    """Conservative: a partial sum would under-predict the wait.

    Better an indeterminate bar than a determinate one that promises a total
    the walk will blow straight through.
    """
    proj = _fake_project()
    del proj.Cache.LangProject.PhonologicalDataOA.PhonRulesOS
    counts = prog.SourceCounts(proj)
    assert counts.phonological_rules is None
    assert counts.phonology is None
    assert counts.entry_types == 6 + 7  # unaffected aggregate still resolves


def test_source_counts_is_filled_once_and_then_frozen():
    """Counts are a snapshot taken at bind; later source churn is not re-read.

    data-model s1 relies on this: `nextId()` can fire on every
    `completeChanged`, so the page-skip predicates must read a cache, never
    the project.
    """
    proj = _fake_project(entries=12)
    counts = prog.SourceCounts(proj)
    assert counts.lexicon_entries == 12
    proj.LexiconNumberOfEntries = lambda: 999
    assert counts.lexicon_entries == 12


def test_source_counts_repr_is_readable():
    """A log line that says what was measured, in ASCII."""
    text = repr(prog.SourceCounts(_fake_project()))
    assert "SourceCounts" in text
    assert all(ord(ch) < 128 for ch in text)


# ===========================================================================
# Integration of the two halves: a cheap count drives the display decision
# ===========================================================================


def test_cheap_count_drives_the_up_front_decision():
    """The end-to-end rule of US1, with no Qt and no live project involved."""
    counts = prog.SourceCounts(_fake_project(entries=1_000_000, texts=1))
    assert prog.warrants_indicator(counts.lexicon_entries, prog.rate_for("affixes")) is True
    assert prog.warrants_indicator(counts.texts, prog.rate_for("texts")) is False


def test_unknown_count_falls_back_to_elapsed_time():
    """No source bound => nothing shown up front; the deferred sink governs."""
    counts = prog.SourceCounts.unknown()
    assert prog.warrants_indicator(counts.lexicon_entries, prog.rate_for("affixes")) is False


# ###########################################################################
# T016 -- the Qt sink: `Lib/ui/progress_indicator.py`
#
# EVERYTHING ABOVE THIS BANNER IS AND MUST REMAIN QT-FREE.
#
# Nothing below imports Qt at module scope, sets `QT_QPA_PLATFORM` at module
# scope, or `importorskip`s at module or class scope. Class-body `importorskip`
# would raise `Skipped` while the module is being imported and skip the whole
# file -- all 56 Qt-free tests with it -- so the quarantine is a FIXTURE: the
# import, the platform pin and the `QApplication` are created on first use by a
# test that asked for them, and a machine with no PyQt6 skips exactly those
# tests.
#
# The source-level checks (ASCII, no hard-coded colour, no restated threshold)
# need no Qt at all and are plain functions, so they run on a bare interpreter
# too.
# ###########################################################################


# ---------------------------------------------------------------------------
# Source-level structure (no Qt required)
# ---------------------------------------------------------------------------

#: Names that would mean the indicator paints itself instead of inheriting the
#: active palette. `Lib/ui/theme.py` owns every colour in this application, and
#: the suite runs with `GRAMTRANS_NO_THEME=1` -- so the only way a wait entered
#: in dark mode can show a dark indicator is for the indicator to set no colour
#: whatsoever and let the toolkit hand it the application's own.
_COLOUR_TOKENS = (
    "QColor",
    "QPalette",
    "setPalette",
    "setStyleSheet",
    "styleSheet",
    "setBackgroundRole",
    "setForegroundRole",
    "GlobalColor",
    "rgb(",
    "rgba(",
)

#: A literal colour: `#` immediately followed by 3-8 hex digits. Comments in
#: this codebase always put a space after `#`, so a comment cannot match.
_HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{3,8}(?![0-9A-Za-z_])")


def test_qt_sink_module_exists():
    """T017 delivers exactly one file, and this is where the tests expect it."""
    assert _QT_SINK_PATH.is_file(), f"missing Qt sink module: {_QT_SINK_PATH}"


def test_qt_sink_module_source_is_ascii():
    """No non-ASCII characters: Windows terminals mangle them (house rule)."""
    source = _QT_SINK_PATH.read_text(encoding="utf-8")
    offenders = sorted({ch for ch in source if ord(ch) > 127})
    assert offenders == [], f"non-ASCII characters in progress_indicator.py: {offenders!r}"


def test_qt_sink_hard_codes_no_colour():
    """FR-024..FR-028 by omission: the indicator inherits, it does not paint.

    Asserted as an ABSENCE rather than as the presence of some specific colour,
    because the whole suite runs un-themed (`GRAMTRANS_NO_THEME=1`, root
    conftest) -- there is no installed palette to compare against, and a test
    that demanded one would be testing the theme, not the indicator. What the
    indicator owes the operator is that it never overrides what it was given.
    """
    source = _QT_SINK_PATH.read_text(encoding="utf-8")
    found = [token for token in _COLOUR_TOKENS if token in source]
    assert found == [], (
        "progress_indicator.py must draw from the active palette, never from a "
        f"colour of its own; found {found}"
    )
    assert _HEX_COLOUR.search(source) is None, (
        "progress_indicator.py contains a literal hex colour: "
        f"{_HEX_COLOUR.search(source).group(0)!r}"  # type: ignore[union-attr]
    )


def test_qt_sink_never_restates_the_threshold():
    """FR-019a: the 500 ms number appears nowhere in the Qt half, not even in prose.

    `test_threshold_declared_in_exactly_one_place` already forbids a second
    *assignment*; this forbids the softer failure of a comment or docstring that
    quotes the number, which is how the two copies start drifting.
    """
    source = _QT_SINK_PATH.read_text(encoding="utf-8")
    assert "500" not in source, (
        "progress_indicator.py mentions 500; import PROGRESS_THRESHOLD_MS from "
        "Lib/progress.py and refer to it by name (FR-019a)"
    )
    assert "PROGRESS_THRESHOLD_MS" in source, (
        "progress_indicator.py must import and use PROGRESS_THRESHOLD_MS: it is "
        "the elapsed-time fallback delay (FR-014b)"
    )


# ---------------------------------------------------------------------------
# The Qt quarantine: import, platform pin and QApplication, all in a fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qt_env():
    """PyQt6 + an offscreen `QApplication` + the sink module, or skip.

    Module-scoped: building a `QApplication` is the expensive part and Qt only
    permits one per process anyway. `QT_QPA_PLATFORM` is `setdefault`-ed here
    rather than at import time because the platform plugin is chosen when the
    application object is constructed, not when PyQt6 is imported -- so a
    fixture is early enough, and it keeps the module scope clean for the
    Qt-free half above.
    """
    pytest.importorskip("PyQt6")
    # SC-007 convention (mirrors test_014_pane_display.py): pick the platform
    # before any QApplication exists, so the suite needs no display.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6 import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    from gramtrans.Lib.ui import progress_indicator as pi

    return SimpleNamespace(app=app, pi=pi, QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


@pytest.fixture
def qt(qt_env):
    """`qt_env`, with the ONE shared indicator torn down before and after.

    The sink is deliberately application-global (FR-021: at most one indicator
    for the whole application), so its state outlives any single test. Every
    test therefore starts from "no dialog, empty stack" and leaves it that way;
    without this a dismissal bug in one test would show up as a mystery failure
    in the next.
    """
    _tear_down_indicator(qt_env)
    yield qt_env
    _tear_down_indicator(qt_env)


def _tear_down_indicator(qt_env):
    """Hide and forget the shared dialog, then let Qt actually delete it.

    Guarded: one test deliberately destroys the dialog under the sink, after
    which every call on the Python wrapper raises -- and a teardown that blew up
    on that would report the failure against the NEXT test.
    """
    pi = qt_env.pi
    dialog = pi._DIALOG
    pi._STACK.clear()
    pi._DIALOG = None
    pi._VISIBLE = False
    if dialog is not None:
        try:
            dialog.hide()
            dialog.setParent(None)
            dialog.deleteLater()
        except RuntimeError:
            pass  # already deleted from the C++ side
    qt_env.app.processEvents()


def _visible_progress_dialogs(qt_env):
    """Every progress dialog currently on screen, from Qt's own widget registry.

    Counted from `allWidgets()` rather than from the module's own bookkeeping,
    so a second window really would be caught -- asking the module how many
    dialogs it thinks it has could never fail.
    """
    return [
        w
        for w in qt_env.QtWidgets.QApplication.allWidgets()
        if isinstance(w, qt_env.QtWidgets.QProgressDialog) and w.isVisible()
    ]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_qt_sink_satisfies_the_progress_sink_protocol(qt):
    """One protocol, two implementations -- and this is the only Qt one."""
    sink = qt.pi.QtProgressSink()
    assert isinstance(sink, prog.ProgressSink)
    assert isinstance(qt.pi.deferred("Reading rules..."), prog.ProgressSink)
    assert isinstance(qt.pi.immediate("Reading rules...", 10), prog.ProgressSink)


def test_pump_interval_is_below_the_project_threshold(qt):
    """The throttle must be finer-grained than the moment it has to act on.

    The elapsed-time fallback shows the indicator on a pump, so the pump
    interval bounds how late that can happen. A pump interval at or above
    PROGRESS_THRESHOLD_MS could delay the indicator past its own deadline.
    """
    assert 0 < qt.pi.PUMP_INTERVAL_MS < prog.PROGRESS_THRESHOLD_MS


# ---------------------------------------------------------------------------
# deferred() -- FR-014b, FR-019, SC-001a
# ---------------------------------------------------------------------------


def test_deferred_shows_nothing_for_work_that_finishes_first(qt):
    """FR-019 / SC-001a: fast work displays NOTHING -- no flash, no flicker.

    Checked after every single tick, not only at the end: a flash is by
    definition transient, so a test that only looked at the final state would
    pass on exactly the defect it exists to catch.
    """
    pi = qt.pi
    sink = pi.deferred("Reading custom fields...", 12)

    # Before `begin` there is not even a dialog object: a deferred sink that is
    # never used costs one Python object and no widget.
    assert pi._DIALOG is None

    with prog.reporting(sink, "Reading custom fields...", 12):
        for _ in range(12):
            sink.tick()
            assert _visible_progress_dialogs(qt) == [], "an indicator flashed on fast work"

    assert _visible_progress_dialogs(qt) == []
    assert pi._STACK == []


def test_deferred_uses_the_project_threshold_as_its_minimum_duration(qt):
    """FR-014b: the elapsed-time fallback IS the dialog's minimum duration.

    Asserted against the imported constant, never against a literal, so the
    single declaration (FR-019a) stays the single source of the number.
    """
    pi = qt.pi
    sink = pi.deferred("Opening source project...")
    sink.begin("Opening source project...")
    assert pi._DIALOG.minimumDuration() == prog.PROGRESS_THRESHOLD_MS
    sink.end()


def test_deferred_appears_once_the_threshold_has_elapsed(qt, monkeypatch):
    """FR-014b: at PROGRESS_THRESHOLD_MS the indicator appears, mid-walk.

    Driven through the module's clock seam instead of `sleep`: a real 500 ms
    wait would make this the slowest unit test in the suite and would still be
    timing-dependent on a loaded CI box.
    """
    pi = qt.pi
    clock = {"ms": 0}
    monkeypatch.setattr(pi, "_now_ms", lambda: clock["ms"])

    sink = pi.deferred("Reading grammatical dependencies...")
    sink.begin("Reading grammatical dependencies...")

    clock["ms"] = prog.PROGRESS_THRESHOLD_MS - 1
    sink.tick()
    assert _visible_progress_dialogs(qt) == [], "shown before the threshold elapsed"

    clock["ms"] = prog.PROGRESS_THRESHOLD_MS
    sink.tick()
    assert _visible_progress_dialogs(qt) == [pi._DIALOG]
    assert pi._DIALOG.labelText() == "Reading grammatical dependencies..."

    sink.end()
    assert _visible_progress_dialogs(qt) == []


# ---------------------------------------------------------------------------
# immediate() -- FR-014a, FR-014c, SC-001b
# ---------------------------------------------------------------------------


def test_immediate_is_on_screen_before_the_work_starts(qt):
    """FR-014a / SC-001b: no still window ahead of the indicator.

    `immediate()` returning is the last thing that happens before the caller
    starts walking, so visibility is asserted on the returned value with no
    `begin`, no `tick` and no event loop of the caller's own in between.
    """
    pi = qt.pi
    sink = pi.immediate("Reading affixes...", 5000)

    assert _visible_progress_dialogs(qt) == [pi._DIALOG]
    assert pi._DIALOG.labelText() == "Reading affixes..."
    assert pi._DIALOG.minimumDuration() == 0

    sink.end()


def test_immediate_states_the_scale_of_the_work_from_the_first_frame(qt):
    """FR-014c / FR-016: determinate, with the real total, before the first tick."""
    pi = qt.pi
    sink = pi.immediate("Reading stems...", 4321)
    sink.begin("Reading stems...", 4321)
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 4321)
    sink.end()


def test_immediate_dismisses_even_if_the_walk_never_begins(qt):
    """A primed indicator whose walk bailed out early must still come down.

    `immediate()` puts a dialog up before anything calls `begin`. If the
    builder then returns early -- an empty inventory, a guard clause -- the only
    call it is contractually guaranteed to make is `end` (FR-020), so `end`
    has to be able to take down an indicator it never began.
    """
    pi = qt.pi
    sink = pi.immediate("Reading lexical-entry types...", 7)
    assert _visible_progress_dialogs(qt) == [pi._DIALOG]
    sink.end()
    assert _visible_progress_dialogs(qt) == []


def test_indeterminate_when_the_total_is_unknown(qt):
    """FR-017: no total => a busy range, which is what animates visibly."""
    pi = qt.pi
    sink = pi.immediate("Opening target project...", 0)
    sink.begin("Opening target project...", None)
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 0)
    sink.end()


# ---------------------------------------------------------------------------
# FR-021 -- one indicator, nested labels on a stack
# ---------------------------------------------------------------------------


def test_a_nested_begin_relabels_the_one_indicator(qt):
    """FR-021: the operator sees the current work, not a stack of dialogs."""
    pi = qt.pi
    sink = pi.immediate("Reading morphology skeleton...", 100)
    sink.begin("Reading morphology skeleton...", 100)
    first_dialog = pi._DIALOG

    sink.begin("Reading grammatical dependencies...", 4)
    assert pi._DIALOG is first_dialog, "a second dialog was created for a nested walk"
    assert _visible_progress_dialogs(qt) == [first_dialog]
    assert pi._DIALOG.labelText() == "Reading grammatical dependencies..."

    sink.end()
    sink.end()


def test_a_nested_end_restores_the_outer_label(qt):
    """FR-021: `end` pops back to the operation still in progress."""
    pi = qt.pi
    sink = pi.immediate("Reading morphology skeleton...", 100)
    sink.begin("Reading morphology skeleton...", 100)
    sink.tick(10)
    sink.begin("Reading grammatical dependencies...", 4)
    sink.end()

    assert pi._DIALOG.labelText() == "Reading morphology skeleton..."
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 100)
    assert _visible_progress_dialogs(qt) == [pi._DIALOG], "the outer indicator was dismissed"

    sink.end()
    assert _visible_progress_dialogs(qt) == []


def test_only_the_outermost_end_dismisses(qt):
    """Three deep, and nothing comes down until the last `end`."""
    pi = qt.pi
    sink = pi.immediate("Reading affixes...", 3)
    for label in ("Reading affixes...", "Reading stems...", "Reading rules..."):
        sink.begin(label, 3)
    for expected in ("Reading stems...", "Reading affixes..."):
        sink.end()
        assert _visible_progress_dialogs(qt) == [pi._DIALOG]
        assert pi._DIALOG.labelText() == expected
    sink.end()
    assert _visible_progress_dialogs(qt) == []
    assert pi._STACK == []


def test_two_separate_sinks_still_present_one_indicator(qt):
    """FR-021 is about the APPLICATION, not about one sink object.

    Two independently-created sinks nesting is the case a per-instance dialog
    would get wrong -- and it is the realistic one, since each wizard page
    builds its own sink.
    """
    pi = qt.pi
    outer = pi.immediate("Building the transfer plan...", 8)
    outer.begin("Building the transfer plan...", 8)
    shared = pi._DIALOG

    inner = pi.deferred("Reading texts...", 3)
    inner.begin("Reading texts...", 3)
    assert pi._DIALOG is shared
    assert _visible_progress_dialogs(qt) == [shared]
    assert pi._DIALOG.labelText() == "Reading texts..."

    inner.end()
    assert pi._DIALOG.labelText() == "Building the transfer plan..."
    assert _visible_progress_dialogs(qt) == [shared]

    outer.end()
    assert _visible_progress_dialogs(qt) == []


def test_a_strays_end_does_not_dismiss_another_sinks_indicator(qt):
    """An extra `end` is absorbed, and never pops a level it did not push."""
    pi = qt.pi
    outer = pi.immediate("Reading phonology...", 9)
    outer.begin("Reading phonology...", 9)
    inner = pi.deferred("Reading rules...", 2)
    inner.end()  # never began: nothing of its own to pop
    inner.end()
    assert _visible_progress_dialogs(qt) == [pi._DIALOG]
    assert pi._DIALOG.labelText() == "Reading phonology..."
    outer.end()
    assert _visible_progress_dialogs(qt) == []


# ---------------------------------------------------------------------------
# Overrun degradation (data-model s2, spec edge case)
# ---------------------------------------------------------------------------


def test_overrunning_the_total_degrades_to_indeterminate(qt):
    """Never over 100%, never a negative remainder -- a busy bar instead."""
    pi = qt.pi
    sink = pi.immediate("Reading rules...", 3)
    sink.begin("Reading rules...", 3)
    for _ in range(3):
        sink.tick()
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 3)

    sink.tick()  # the fourth unit of a three-unit walk
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 0), (
        "an overrun total must degrade to indeterminate (data-model s2)"
    )
    sink.end()


def test_overrun_covers_the_three_pass_skeleton_walk(qt):
    """The overrun that T018 documents, not a hypothetical one.

    `build_skeleton_inventory` makes THREE passes over the entry list and ticks
    all three, while the caller's cheap total is one `LexiconNumberOfEntries()`.
    So the honest behaviour for a real wizard page is: fill, overrun at entry
    count + 1, and finish as a busy bar.
    """
    pi = qt.pi
    entries = 40
    sink = pi.immediate("Reading morphology skeleton...", entries)
    sink.begin("Reading morphology skeleton...", entries)
    for _ in range(3):
        for _ in range(entries):
            sink.tick()
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 0)
    assert pi._DIALOG.value() <= max(pi._DIALOG.maximum(), 0)
    sink.end()


def test_the_bar_never_reports_more_than_its_total(qt):
    """The invariant behind the degradation, asserted tick by tick."""
    pi = qt.pi
    sink = pi.immediate("Writing to the target project...", 6)
    sink.begin("Writing to the target project...", 6)
    for _ in range(20):
        sink.tick()
        assert pi._DIALOG.value() <= pi._DIALOG.maximum() or pi._DIALOG.maximum() == 0
    sink.end()


def test_a_zero_total_is_indeterminate_not_a_full_bar(qt):
    """A total of 0 has no finish line to draw, so it must not draw one."""
    pi = qt.pi
    sink = pi.immediate("Reading texts...", 0)
    sink.begin("Reading texts...", 0)
    assert (pi._DIALOG.minimum(), pi._DIALOG.maximum()) == (0, 0)
    sink.end()


# ---------------------------------------------------------------------------
# FR-020 -- dismissal on every path, and the never-raises guarantees
# ---------------------------------------------------------------------------


def test_the_failure_path_still_dismisses(qt):
    """FR-020 through `reporting()`: an exception dismisses and re-raises.

    A modal indicator left up over a failed operation is the worst available
    outcome -- it blocks the very input the operator needs to dismiss the error
    message.
    """
    pi = qt.pi
    sink = pi.immediate("Writing to the target project...", 10)
    boom = RuntimeError("target write failed")

    with pytest.raises(RuntimeError) as excinfo, prog.reporting(
        sink, "Writing to the target project...", 10
    ):
        sink.tick(3)
        raise boom

    assert excinfo.value is boom
    assert _visible_progress_dialogs(qt) == []
    assert pi._STACK == []


def test_a_nested_failure_leaves_the_outer_indicator_up(qt):
    """The outer operation has not failed, so its indicator has not finished."""
    pi = qt.pi
    sink = pi.immediate("Reading morphology skeleton...", 50)
    with prog.reporting(sink, "Reading morphology skeleton...", 50):
        with pytest.raises(ValueError), prog.reporting(
            sink, "Reading grammatical dependencies...", 5
        ):
            raise ValueError("inner walk failed")
        assert _visible_progress_dialogs(qt) == [pi._DIALOG]
        assert pi._DIALOG.labelText() == "Reading morphology skeleton..."
    assert _visible_progress_dialogs(qt) == []


def test_qt_sink_end_is_idempotent(qt):
    """Contract guarantee, same as the Qt-free half."""
    pi = qt.pi
    sink = pi.immediate("Reading stems...", 2)
    sink.begin("Reading stems...", 2)
    sink.end()
    sink.end()
    sink.end()
    assert _visible_progress_dialogs(qt) == []


def test_qt_sink_tick_never_raises_after_end(qt):
    """A nested walk that outlives its indicator must not take the run down."""
    pi = qt.pi
    sink = pi.immediate("Reading stems...", 2)
    sink.begin("Reading stems...", 2)
    sink.end()
    for _ in range(1000):
        sink.tick()
    assert _visible_progress_dialogs(qt) == []


def test_qt_sink_tick_never_raises_without_begin(qt):
    """Out-of-order use is absorbed, not punished."""
    sink = qt.pi.QtProgressSink()
    sink.tick(5)
    sink.end()


def test_qt_sink_tick_survives_a_dead_dialog(qt):
    """A display that has been destroyed under us is not the walk's problem.

    Qt objects can be deleted from outside Python (a parent going away takes
    its children with it), after which every call raises `RuntimeError`. The
    contract says `tick` never raises, and this is the realistic way it would.
    """
    pi = qt.pi
    sink = pi.immediate("Reading phonology...", 100)
    sink.begin("Reading phonology...", 100)
    pi._DIALOG.deleteLater()
    qt.app.processEvents()
    for _ in range(50):
        sink.tick()
    sink.end()


# ---------------------------------------------------------------------------
# FR-018 -- modal, no cancel affordance, and a pumped-but-throttled tick
# ---------------------------------------------------------------------------


def test_the_indicator_is_modal_with_no_cancel_affordance(qt):
    """FR-018: wizard input is blocked, and there is no button to press.

    Cancellation is explicitly out of scope, so a cancel button would be an
    affordance that does nothing -- worse than none at all.
    """
    pi = qt.pi
    sink = pi.immediate("Reading affixes...", 100)
    dialog = pi._DIALOG
    assert dialog.windowModality() == qt.QtCore.Qt.WindowModality.ApplicationModal
    assert dialog.findChild(qt.QtWidgets.QPushButton) is None
    sink.end()


def test_escape_does_not_dismiss_the_indicator(qt):
    """No cancel affordance means Esc is not one either (FR-018).

    Qt's default is that Esc rejects a dialog, which would HIDE the indicator
    while the walk kept running -- unblocking the wizard mid-read, which is the
    re-entrant database access FR-018 exists to prevent.
    """
    pi = qt.pi
    sink = pi.immediate("Reading affixes...", 100)
    dialog = pi._DIALOG
    event = qt.QtGui.QKeyEvent(
        qt.QtCore.QEvent.Type.KeyPress,
        qt.QtCore.Qt.Key.Key_Escape,
        qt.QtCore.Qt.KeyboardModifier.NoModifier,
    )
    qt.app.sendEvent(dialog, event)
    qt.app.processEvents()
    assert dialog.isVisible()
    assert dialog.wasCanceled() is False
    sink.end()


def test_tick_pumps_the_event_loop_on_a_time_based_throttle(qt, monkeypatch):
    """SC-002 core: the throttle is measured in milliseconds, not in ticks.

    A count-based throttle behaves completely differently for a 100-unit walk
    than for a 10-million-unit one; a time-based one pumps at a fixed rate
    whatever the tick rate, which is exactly the property "the OS never reports
    the window unresponsive" needs.

    Both halves are driven through the clock seam, so the numbers are exact
    rather than approximate.
    """
    pi = qt.pi
    pumps = []
    clock = {"ms": 0}
    monkeypatch.setattr(pi, "_pump_events", lambda: pumps.append(clock["ms"]))
    monkeypatch.setattr(pi, "_now_ms", lambda: clock["ms"])

    sink = pi.deferred("Opening source project...")
    sink.begin("Opening source project...")
    del pumps[:]

    # A frozen clock: no time has passed, so no repaint is owed -- however many
    # ticks arrive. This is the assertion a tick-count throttle fails.
    for _ in range(1000):
        sink.tick()
    assert pumps == [], f"pumped {len(pumps)} times with no time elapsed"

    # 10 ms per tick over 40 ticks = 400 ms of walk, still under the threshold
    # so nothing is shown; pumps land on the interval boundaries.
    interval = pi.PUMP_INTERVAL_MS
    for _ in range(40):
        clock["ms"] += 10
        sink.tick()
    assert pumps == [interval * k for k in range(1, 400 // interval + 1)]

    sink.end()


def test_a_200k_tick_walk_does_not_live_in_the_event_loop(qt, monkeypatch):
    """SC-002 at scale: pumps must be bounded by wall time, not by tick count.

    200,000 ticks against the REAL clock. A sink that pumped per tick would
    make 200,000 `processEvents()` calls; a 40 ms throttle makes one per 40 ms
    of actual walking, which on any machine is a handful.
    """
    pi = qt.pi
    pumps = {"n": 0}

    def _counting_pump():
        pumps["n"] += 1

    monkeypatch.setattr(pi, "_pump_events", _counting_pump)

    ticks = 200_000
    sink = pi.deferred("Reading stems...", ticks)
    sink.begin("Reading stems...", ticks)
    for _ in range(ticks):
        sink.tick()
    sink.end()

    assert pumps["n"] < ticks / 100, (
        f"pumped {pumps['n']} times for {ticks} ticks -- the throttle is not working"
    )
    # A hard ceiling too: 500 pumps at 40 ms apart would mean 20 seconds of
    # wall clock for a walk that has no business taking one.
    assert pumps["n"] <= 500, f"pumped {pumps['n']} times for {ticks} ticks"


def test_tick_still_advances_the_bar_between_pumps(qt, monkeypatch):
    """Throttling the repaint must not throttle the counting.

    The bar's value is only pushed to the widget on a pump, but the units
    themselves are never dropped -- otherwise a throttled walk would finish
    showing less progress than it made.
    """
    pi = qt.pi
    clock = {"ms": 0}
    monkeypatch.setattr(pi, "_now_ms", lambda: clock["ms"])

    sink = pi.immediate("Reading texts...", 100)
    sink.begin("Reading texts...", 100)
    for _ in range(60):
        sink.tick()
    clock["ms"] += pi.PUMP_INTERVAL_MS
    sink.tick()
    assert pi._DIALOG.value() == 61
    sink.end()


def test_labels_are_operator_vocabulary_not_internal_vocabulary(qt):
    """FR-015: whatever the caller passes is what the operator reads, verbatim.

    The sink must not decorate, prefix or truncate the label -- the FR-023
    table is the vocabulary of record, and this is the one place it could be
    quietly rewritten.
    """
    pi = qt.pi
    label = "Reading morphology skeleton..."
    sink = pi.immediate(label, 10)
    assert pi._DIALOG.labelText() == label
    sink.begin(label, 10)
    assert pi._DIALOG.labelText() == label
    sink.end()


def test_the_dialog_accepts_a_parent(qt):
    """The indicator belongs to the window it blocks, so it can be parented."""
    pi = qt.pi
    host = qt.QtWidgets.QWidget()
    try:
        sink = pi.deferred("Reading rules...", 3, parent=host)
        sink.begin("Reading rules...", 3)
        assert pi._DIALOG.parent() is host
        sink.end()
    finally:
        host.deleteLater()
        qt.app.processEvents()
