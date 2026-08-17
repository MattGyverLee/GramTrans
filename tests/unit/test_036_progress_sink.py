"""Tests: Qt-free progress surface (feature 036, US1 foundation).

T002 -- test_036_progress_sink.py
FR-014, FR-014b, FR-014c, FR-014d, FR-015..FR-017, FR-019a, FR-020, FR-022,
FR-045; contracts/progress-sink.md; data-model.md sections 2 and 3.

This module tests `gramtrans.Lib.progress`, which is **Qt-free by contract**.
`Lib/selection.py` imports it, and `Lib/selection.py` must stay importable with
no `QApplication` -- exactly as `Lib/merge_preview.py` is (proven by
`test_merge_preview_qt_free.py`, whose static/subprocess pattern is mirrored
below). So, deliberately:

  - `QT_QPA_PLATFORM` is NOT set here,
  - PyQt6 is NOT imported and NOT `importorskip`-ed,
  - the whole module runs on a bare interpreter.

If a future edit makes `Lib/progress.py` reach for Qt, three tests here fail
(static AST scan, source-substring scan, blocked-import subprocess) rather than
the breakage surfacing later as a headless crash inside a wizard build.

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
"""

from __future__ import annotations

import ast
import math
import pathlib
import subprocess
import sys
import textwrap

import pytest

from gramtrans.Lib import progress as prog

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_MODULE_PATH = _REPO_ROOT / "src" / "gramtrans" / "Lib" / "progress.py"


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
