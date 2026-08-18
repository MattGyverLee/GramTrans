"""Item 9 -- the Finish page's guard rail, asserted end to end (FR-038..FR-044).

Execute is the only write GramTrans performs, and Preview-before-Mutate is the
constitution's central safety property. This module is the evidence that the
guard is *tighter* than it was, never looser, so it deliberately covers the
already-met halves as regression alongside the two genuinely new behaviours.

What has to hold, and is asserted here:

* **Execute starts unavailable and returns to unavailable.** Disabled on
  construction and on every page entry (FR-038), and the cached plan that
  authorises a write is `None` at both of those moments (data-model section 6).
* **The unavailability explains itself.** A disabled Execute states either that
  a dry run is required (FR-039) or that the run is read-only (FR-044). A dead
  button with no explanation is the gap this feature closes.
* **No stale result is presented as current.** Page entry clears the *displayed*
  dry-run report as well as the cached plan, so a report on screen always
  describes the selections currently in force (FR-041).
* **Nothing on the page reaches a write while Execute is disabled.** Asserted
  twice: structurally (`gt_api.execute_move` is called from exactly one place)
  and behaviourally (a spy that fails the test if it is ever called on a
  disabled-Execute path) -- FR-040, SC-007.
* **A failed dry run states the failure and changes nothing** (FR-042), and a
  completed Execute leaves Execute disabled for the rest of the session so the
  same selections cannot be written twice (FR-043).

The page is constructed directly wherever possible -- `_PageFinish` needs only a
report sink, a modify-allowed flag and (optionally) a confirmation gate -- which
keeps the run fast and keeps each assertion pointed at the guard rather than at
the wizard around it. One test builds the whole wizard, because "disabled when
the operator first sees it" is a claim about the real assembled flow.

Deliberately NOT asserted: the page title. Renumbering the wizard's steps is a
sibling task in this same feature; pinning "Step 10 of 10" here would make this
module fail for a reason that has nothing to do with the guard.
"""
from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

# House convention: offscreen platform chosen before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

from gramtrans.Lib import api as gt_api  # noqa: E402
from gramtrans.Lib.models import RunContext, RunMode, RunReport  # noqa: E402
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402

_WIZARD_SOURCE = Path(sw.__file__)


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _Sink:
    """The four methods a report sink has, remembering what it was told."""

    def __init__(self) -> None:
        self.lines = []

    def Info(self, msg=""):  # noqa: N802
        self.lines.append(("info", msg))

    def Warning(self, msg=""):  # noqa: N802
        self.lines.append(("warn", msg))

    def Error(self, msg=""):  # noqa: N802
        self.lines.append(("error", msg))

    def Blank(self):  # noqa: N802
        self.lines.append(("blank", ""))


def _built_on_real_qt(cls) -> bool:
    """Did `cls` capture the real PyQt6 base, or a sibling module's double?

    `test_wizard_page_flow.py` and `test_ui_gating.py` overwrite
    `QtWidgets.QWizard` and `QWizardPage` at import time -- on the real
    extension module, when real PyQt6 was imported first. Which class a wizard
    page ends up inheriting therefore depends on whether `selection_wizard` was
    imported before or after those modules, and pytest imports every test module
    during collection, so the answer is a property of the whole session.

    Asking `QtWidgets.QWizard` is the wrong question: in a full-suite run the
    doubles are installed by collection time, yet `_PageFinish` still has the
    real base because the class statement ran earlier. So ask the class itself.
    """
    return any(
        base.__name__ in ("QWizardPage", "QWizard")
        and getattr(base, "__module__", "").startswith("PyQt6")
        for base in cls.__mro__
    )


def _needs_a_real_qwizard():
    """Skip when `SelectionWizard` itself was built on a double (see above)."""
    if not _built_on_real_qt(sw.SelectionWizard):
        pytest.skip("SelectionWizard was built on a PyQt6 double this session")
    if not isinstance(getattr(QtWidgets.QWizard, "WizardStyle", None), type):
        pytest.skip("a PyQt6 QWizard double is installed in this session")


@pytest.fixture(autouse=True)
def _real_qwizardpage_only():
    """A `_PageFinish` on a stub base cannot even be constructed -- its
    `__init__` takes no parent -- and nothing about the guard can be asserted
    against a fake base class. Stand the module down rather than report failures
    that say nothing about the Finish page."""
    if not _built_on_real_qt(sw._PageFinish):
        pytest.skip("_PageFinish was built on a PyQt6 QWizardPage double")


# ---------------------------------------------------------------------------
# Fixture doubles: a plan, a report, and a wizard that is only as real as the
# guard needs it to be.
# ---------------------------------------------------------------------------

def _ctx(run_id: str = "GT-20260817-120000") -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/fake/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/fake/tgt",
        run_id=run_id,
        started_at="2026-08-17T12:00:00",
    )


def _report(mode: RunMode = RunMode.PREVIEW, run_id: str = "GT-20260817-120000") -> RunReport:
    # Empty per_category + no skips satisfies the FR-018 __post_init__ invariant.
    return RunReport(context=_ctx(run_id), mode=mode)


class _PlanDouble:
    """Stand-in for a RunPlan. `_on_move` asks it exactly one question."""

    def __init__(self, excluded_lossy: int = 0) -> None:
        self._excluded_lossy = excluded_lossy

    def excluded_lossy_count(self) -> int:
        return self._excluded_lossy


class _ProjectWSDouble:
    def __init__(self, context) -> None:
        self._context = context

    def context(self):
        return self._context


class _WizardDouble:
    """What `_on_dry_run` / `_on_move` actually read off the wizard.

    A page whose `wizard()` is `None` returns early from both handlers, so the
    guard cannot be exercised at all without something here. Keeping it a double
    (rather than a real `SelectionWizard`) is what lets every assertion below
    name one behaviour instead of nine pages of setup.
    """

    def __init__(self, context=None) -> None:
        self._page_project_ws = _ProjectWSDouble(context)

    def page_project_ws(self):
        return self._page_project_ws

    def page_skeleton(self):
        return None


def _finish(qapp, modify_allowed: bool = True, gate=None):
    """A Finish page, constructed the way the wizard constructs it."""
    return sw._PageFinish(_Sink(), modify_allowed, confirmation_gate=gate)


def _attach(page, context=None):
    """Give `page` a wizard. Shadows the bound `wizard()` on the instance."""
    wizard = _WizardDouble(context)
    page.wizard = lambda: wizard  # type: ignore[method-assign]
    return wizard


@pytest.fixture
def quiet_dialogs(monkeypatch):
    """No modal dialog may block the offscreen run. Records what was popped."""
    popped = {"warning": [], "critical": [], "question": []}

    def _warn(*args, **kwargs):
        popped["warning"].append(args[2] if len(args) > 2 else "")
        return QtWidgets.QMessageBox.StandardButton.Ok

    def _crit(*args, **kwargs):
        popped["critical"].append(args[2] if len(args) > 2 else "")
        return QtWidgets.QMessageBox.StandardButton.Ok

    def _question(*args, **kwargs):
        popped["question"].append(args[2] if len(args) > 2 else "")
        return QtWidgets.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(_warn))
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(_crit))
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(_question))
    return popped


@pytest.fixture
def write_spy(monkeypatch):
    """The one write, replaced by a witness.

    Any test that expects no write asserts `spy.calls == []`; any test that
    expects one asserts it happened here and nowhere else. Because this is the
    only write point (see the structural test below), an empty `calls` list is a
    complete statement that nothing was written.
    """

    class _Spy:
        def __init__(self) -> None:
            self.calls = []

        def __call__(self, context, plan):
            self.calls.append((context, plan))
            return _report(RunMode.MOVE)

    spy = _Spy()
    monkeypatch.setattr(gt_api, "execute_move", spy)
    # `selection_wizard` calls through the `gt_api` module object, so patching
    # the attribute on the module is enough -- but assert that, rather than
    # assume it, so a future `from ... import execute_move` cannot silently
    # route around the spy and write during a unit test run.
    assert sw.gt_api is gt_api
    return spy


def _succeed_dry_run(monkeypatch, plan=None, report=None):
    """Make the next dry run succeed with a known plan + report."""
    plan = _PlanDouble() if plan is None else plan
    report = _report() if report is None else report
    monkeypatch.setattr(sw, "_compute_wizard_plan", lambda wizard: (plan, report))
    return plan, report


def _fail_dry_run(monkeypatch):
    """Make the next dry run fail to produce a plan (FR-042)."""
    monkeypatch.setattr(sw, "_compute_wizard_plan", lambda wizard: (None, None))


def _quiet_move_extras(monkeypatch):
    """Zero out the two cross-page EXCLUDED-LOSSY sweeps `_on_move` performs."""
    monkeypatch.setattr(sw, "_phonology_excluded_lossy_for", lambda wizard: [])
    monkeypatch.setattr(sw, "_entry_types_missing_ref_for", lambda wizard: [])


# ---------------------------------------------------------------------------
# Observables the guard must expose
# ---------------------------------------------------------------------------

_REASON_ATTR = "execute_disabled_reason"


def _reason(page) -> str:
    """The disabled-Execute explanation, as the contract requires it exposed.

    FR-039/FR-044 say the *state of the control* explains itself. A visible
    banner elsewhere on the page is not that: it does not change when the
    control's reason for being disabled changes. So the guard must expose the
    live reason -- `execute_disabled_reason` -- returning falsy exactly when
    Execute is enabled. Accepts a method or a property, since which of the two
    it is has no bearing on the requirement.
    """
    assert hasattr(page, _REASON_ATTR), (
        f"the disabled Execute control must state its reason (FR-039, FR-044): "
        f"_PageFinish exposes no {_REASON_ATTR!r}"
    )
    value = getattr(page, _REASON_ATTR)
    if callable(value):
        value = value()
    return "" if value is None else str(value)


def _presented_text(page) -> str:
    """Everything the page puts in front of the operator, lower-cased.

    The reason has to be *presented*, not merely returned to a caller, so the
    same words must appear either on the Execute control itself (tooltip /
    accessible description) or in a label on the page. Visibility flags are not
    consulted: an unshown page reports every child as hidden, so filtering on
    `isVisible()` here would assert nothing at all.
    """
    parts = [
        page._move_btn.toolTip(),
        page._move_btn.text(),
        page._move_btn.accessibleDescription(),
        page._move_btn.statusTip(),
        page.subTitle(),
    ]
    parts.extend(lbl.text() for lbl in page.findChildren(QtWidgets.QLabel))
    return "\n".join(p for p in parts if p).lower()


def _report_is_displayed(page) -> bool:
    """Is a dry-run report currently on screen, presented as current?

    `StatsPanel` announces the run it is showing in its header -- mode, run_id,
    source and target. That header is the observable: it says "run_id=" exactly
    when a report is being presented, and the panel's own pre-run placeholder
    does not. Clearing the panel therefore means the header stops naming a run
    (however the implementation chooses to do it -- a `StatsPanel.clear()` or a
    header reset both satisfy this).
    """
    return "run_id=" in page._stats._header.text()


# ===========================================================================
# FR-038 -- disabled on construction, and on every page entry
# ===========================================================================

def test_execute_is_disabled_on_construction(qapp):
    """FR-038, regression. The dead-stop default: no plan, no write."""
    page = _finish(qapp, modify_allowed=True)

    assert page._move_btn.isEnabled() is False
    assert page._move_done is False


def test_the_cached_plan_is_none_on_construction(qapp):
    """data-model section 6: `_cached_plan` is `None` on construction.

    Today it is created only by `initializePage`, so a `_PageFinish` that has
    been built but not yet entered has no `_cached_plan` attribute at all. That
    is a real gap: every other reader of the guard treats "no cached plan" as
    the safe state, and an attribute that does not exist is not that state -- it
    is an AttributeError waiting for the first caller who checks before entry.
    """
    page = _finish(qapp, modify_allowed=True)

    assert getattr(page, "_cached_plan", "MISSING") is None, (
        "_cached_plan must be None on construction, not absent (data-model 6)"
    )


def test_execute_is_disabled_on_every_page_entry(qapp, monkeypatch, quiet_dialogs):
    """FR-038, regression. Re-entry re-arms the guard even mid-session."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)

    page.initializePage()
    assert page._move_btn.isEnabled() is False

    page._on_dry_run()
    assert page._move_btn.isEnabled() is True, "a successful dry run enables Execute"

    page.initializePage()
    assert page._move_btn.isEnabled() is False, (
        "entering the Finish page must re-disable Execute (FR-038)"
    )


def test_the_dry_run_control_is_always_enabled(qapp):
    """Contract row: the dry-run control is present, always enabled, label as was.

    The guard makes Execute conditional; it must not make the *escape* from that
    condition conditional too, in either permission mode.
    """
    for modify_allowed in (True, False):
        page = _finish(qapp, modify_allowed=modify_allowed)
        assert page._dry_run_btn.isEnabled() is True
        assert page._dry_run_btn.text() == "Dry run (preview plan)"


def test_the_finish_page_of_a_real_wizard_opens_with_execute_disabled(qapp, tmp_path):
    """FR-038 against the assembled flow, not a page in isolation.

    The claim the story makes is about what the operator sees, so it is worth
    one test that pays for a whole wizard to see it.
    """
    _needs_a_real_qwizard()
    for name in ("Alpha", "Beta"):
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")

    wizard = sw.SelectionWizard(
        None, _Sink(), True,
        source_project_name="",
        projects_root=str(tmp_path),
        source_binder=lambda name: object(),
    )
    page = wizard.page_finish()

    assert page._move_btn.isEnabled() is False
    assert page._move_done is False
    assert _report_is_displayed(page) is False


# ===========================================================================
# FR-039 / FR-044 -- the disabled state explains itself
# ===========================================================================

def test_the_disabled_execute_states_that_a_dry_run_is_required(qapp):
    """FR-039. Write-enabled, freshly entered: a dead button with no reason.

    This is the case with no explanation at all today -- the read-only banner is
    absent (writes are permitted) and nothing else on the page accounts for why
    Execute cannot be clicked.
    """
    page = _finish(qapp, modify_allowed=True)
    page.initializePage()

    reason = _reason(page).lower()
    assert page._move_btn.isEnabled() is False
    assert "dry run" in reason and "requir" in reason, (
        f"the reason must say a dry run is required (FR-039); got {reason!r}"
    )
    presented = _presented_text(page)
    assert "dry run" in presented and "requir" in presented, (
        "the reason must be presented to the operator -- on the Execute control "
        "(tooltip / accessible description) or in a label on the page"
    )


def test_the_disabled_execute_states_that_the_run_is_read_only(qapp):
    """FR-044. Without write permission, the reason is the permission, not the plan."""
    page = _finish(qapp, modify_allowed=False)
    page.initializePage()

    reason = _reason(page).lower()
    assert page._move_btn.isEnabled() is False
    assert "read-only" in reason, (
        f"the reason must state the read-only condition (FR-044); got {reason!r}"
    )
    assert "read-only" in _presented_text(page)


def test_the_read_only_reason_outlives_a_successful_dry_run(qapp, monkeypatch,
                                                            quiet_dialogs):
    """FR-044 precedence. A dry run cannot turn "read-only" into "run a dry run".

    Read-only outranks want-of-a-plan: once a plan exists, the only remaining
    reason Execute is unavailable is the permission, and saying anything else
    would send the operator to re-run a dry run that cannot help.
    """
    page = _finish(qapp, modify_allowed=False)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()

    assert page._move_btn.isEnabled() is False
    assert "read-only" in _reason(page).lower()


def test_there_is_no_reason_once_execute_is_enabled(qapp, monkeypatch, quiet_dialogs):
    """The reason is the *disabled* state's. An enabled control explains nothing.

    Asserted so the explanation cannot be implemented as a fixed label that
    keeps telling the operator to run a dry run they have already run.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()

    assert page._move_btn.isEnabled() is True
    assert not _reason(page), (
        "an enabled Execute must report no disabled-state reason"
    )


# ===========================================================================
# FR-041 -- no stale dry-run result is presented as current
# ===========================================================================

def test_page_entry_clears_the_cached_plan(qapp, monkeypatch, quiet_dialogs):
    """FR-041, regression. The authorisation a dry run confers does not persist."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()
    assert page._cached_plan is not None

    page.initializePage()
    assert page._cached_plan is None


def test_page_entry_clears_the_displayed_dry_run_report(qapp, monkeypatch,
                                                        quiet_dialogs):
    """FR-041, the new half. A report on screen must describe current selections.

    Leaving the Finish page to change a selection and coming back is the only way
    a selection changes after a dry run, and coming back runs `initializePage`.
    Today that clears the cached plan but leaves the previous report rendered --
    so the operator is looking at a plan for selections that are no longer in
    force, with nothing marking it stale. Clearing the panel is the fix: an empty
    panel plus a "dry run required" reason cannot be misread.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()
    assert _report_is_displayed(page) is True, "the dry run renders its report"

    page.initializePage()
    assert _report_is_displayed(page) is False, (
        "page entry must clear the displayed dry-run report, not just the cached "
        "plan -- a stale report presented as current is what FR-041 forbids"
    )


def test_a_selection_change_after_a_dry_run_leaves_no_authorisation_behind(
        qapp, monkeypatch, quiet_dialogs, write_spy):
    """FR-041 + FR-040 together: re-entry, then a click, and still no write."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _quiet_move_extras(monkeypatch)
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()

    page.initializePage()          # the operator went back and changed something
    page._on_move()                # ... and then clicked Execute anyway

    assert write_spy.calls == [], (
        "a plan cached before a selection change must not be writable after it"
    )
    assert page._move_btn.isEnabled() is False


# ===========================================================================
# FR-042 -- a failed dry run leaves the guard shut and says why
# ===========================================================================

def test_a_dry_run_with_no_target_bound_states_the_failure(qapp, monkeypatch,
                                                           quiet_dialogs, write_spy):
    """FR-042, regression. No context -> named failure, guard untouched."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=None)
    _fail_dry_run(monkeypatch)
    page.initializePage()

    page._on_dry_run()

    assert page._move_btn.isEnabled() is False
    assert page._cached_plan is None
    assert write_spy.calls == []
    assert quiet_dialogs["warning"], "a failed dry run must state the failure"
    assert "target project" in quiet_dialogs["warning"][-1].lower()


def test_a_dry_run_whose_plan_assembly_fails_states_the_failure(qapp, monkeypatch,
                                                                quiet_dialogs,
                                                                write_spy):
    """FR-042, regression. Context present, assembly failed -> a different message.

    Two failures with two messages, because "no target bound" and "plan assembly
    failed" send the operator to different places.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _fail_dry_run(monkeypatch)
    page.initializePage()

    page._on_dry_run()

    assert page._move_btn.isEnabled() is False
    assert page._cached_plan is None
    assert write_spy.calls == []
    assert quiet_dialogs["warning"], "a failed dry run must state the failure"
    assert "plan assembly failed" in quiet_dialogs["warning"][-1].lower()


def test_a_failed_dry_run_does_not_leave_a_report_on_screen(qapp, monkeypatch,
                                                            quiet_dialogs):
    """FR-041 + FR-042. A failure must not leave the previous success displayed."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()
    assert _report_is_displayed(page) is True

    page.initializePage()          # selections changed
    _fail_dry_run(monkeypatch)
    page._on_dry_run()             # ... and the new dry run cannot produce a plan

    assert page._move_btn.isEnabled() is False
    assert _report_is_displayed(page) is False, (
        "after a failed dry run the only report on screen would be the previous "
        "run's -- which is exactly the stale result FR-041 forbids"
    )


# ===========================================================================
# FR-040 / SC-007 -- there is no path to a write while Execute is disabled
# ===========================================================================

def _execute_move_callers() -> set:
    """Every function in `selection_wizard` that calls `gt_api.execute_move`.

    Structural rather than behavioural on purpose: a spy proves the paths the
    tests walk are safe, while this proves there is no *other* path to walk.
    """
    tree = ast.parse(_WIZARD_SOURCE.read_text(encoding="utf-8"))
    callers = set()
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "execute_move":
            total += 1
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute):
                if inner.func.attr == "execute_move":
                    callers.add(node.name)
    # A call outside every function body would be a module-import-time write.
    assert total > 0, "the write point vanished -- this suite is asserting nothing"
    return callers


def test_the_write_is_reachable_from_the_execute_handler_and_nowhere_else():
    """FR-040, SC-007. One write point, one caller, checked in the source.

    `_execute_move_callers` returns enclosing function names, so a nested helper
    that wrapped the write would show up as an extra name here and fail.
    """
    assert _execute_move_callers() == {"_on_move"}, (
        "gt_api.execute_move must be called from _PageFinish._on_move only"
    )


def test_the_execute_handler_returns_before_the_write_when_no_plan_is_cached():
    """FR-040. The guard is the first thing `_on_move` does, not the last."""
    src = inspect.getsource(sw._PageFinish._on_move)
    assert "plan is None" in src
    assert src.index("plan is None") < src.index("gt_api.execute_move"), (
        "the no-cached-plan bail-out must precede the write"
    )


def test_clicking_execute_with_no_dry_run_writes_nothing_and_says_so(
        qapp, monkeypatch, quiet_dialogs, write_spy):
    """FR-040, regression. The disabled button's handler is itself defensive.

    Calling the handler directly is not a contrivance: a Qt shortcut, a default
    button or a synthesised click can reach a handler, so "the button is greyed
    out" is not on its own a guarantee that no write occurs.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _quiet_move_extras(monkeypatch)
    page.initializePage()

    page._on_move()

    assert write_spy.calls == []
    assert quiet_dialogs["warning"], "the refusal must be stated, not silent"
    assert "dry run" in quiet_dialogs["warning"][-1].lower()


def test_read_only_mode_refuses_the_write_even_with_a_cached_plan(
        qapp, monkeypatch, quiet_dialogs, write_spy):
    """FR-044, regression. A successful dry run does not confer permission."""
    page = _finish(qapp, modify_allowed=False)
    _attach(page, context=_ctx())
    _quiet_move_extras(monkeypatch)
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()

    assert page._move_btn.isEnabled() is False, (
        "modify_allowed=False must keep Execute disabled after a dry run (FR-044)"
    )
    assert write_spy.calls == []


def test_a_dry_run_never_writes(qapp, monkeypatch, quiet_dialogs, write_spy):
    """Preview-before-Mutate, stated as the absence it is."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _succeed_dry_run(monkeypatch)
    page.initializePage()
    page._on_dry_run()

    assert write_spy.calls == []
    assert _report_is_displayed(page) is True


# ===========================================================================
# FR-043 -- a completed Execute is not repeatable
# ===========================================================================

def _run_a_move(page, monkeypatch, plan=None):
    """Dry run then Execute, on a page already attached to a wizard double."""
    _quiet_move_extras(monkeypatch)
    _succeed_dry_run(monkeypatch, plan=plan)
    page.initializePage()
    page._on_dry_run()
    page._on_move()


def test_a_completed_execute_leaves_execute_disabled(qapp, monkeypatch,
                                                     quiet_dialogs, write_spy):
    """FR-043, regression. The write happened; the button goes back to dead."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _run_a_move(page, monkeypatch)

    assert len(write_spy.calls) == 1, "the move must actually have been written"
    assert page._move_btn.isEnabled() is False
    assert page._move_done is True
    assert page._cached_plan is None


def test_a_second_execute_click_after_a_move_writes_nothing(qapp, monkeypatch,
                                                            quiet_dialogs,
                                                            write_spy):
    """FR-043 + FR-040. A double-click cannot duplicate LCM objects."""
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _run_a_move(page, monkeypatch)

    page._on_move()

    assert len(write_spy.calls) == 1, (
        "the cached plan is cleared by the write, so the second click has "
        "nothing to write"
    )


def test_a_dry_run_after_a_completed_execute_does_not_re_enable_execute(
        qapp, monkeypatch, quiet_dialogs, write_spy):
    """FR-043, the conjunction the contract spells out.

    Contract: enablement requires a cached plan, `modify_allowed`, **and** no
    completed Execute this session. Today `_on_dry_run` consults only
    `modify_allowed`, so a second dry run after a completed move re-enables
    Execute -- and the same selections get written a second time, which is the
    duplicate write FR-043 exists to prevent. `_move_done` is already recorded;
    the enablement test simply does not read it yet.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _run_a_move(page, monkeypatch)
    assert page._move_done is True

    page._on_dry_run()             # a fresh, successful dry run

    assert page._move_btn.isEnabled() is False, (
        "a completed Execute must keep Execute disabled for the rest of the "
        "session (FR-043) -- a later dry run must not re-arm it"
    )

    page._on_move()
    assert len(write_spy.calls) == 1, "and no second write may occur"


def test_a_completed_execute_still_explains_why_execute_is_unavailable(
        qapp, monkeypatch, quiet_dialogs, write_spy):
    """FR-039's spirit applied to FR-043's state: no unexplained dead control.

    The wording is left to the implementation -- what matters is that a page
    sitting on a finished move does not present a disabled Execute with nothing
    to say about it.
    """
    page = _finish(qapp, modify_allowed=True)
    _attach(page, context=_ctx())
    _run_a_move(page, monkeypatch)

    assert page._move_btn.isEnabled() is False
    assert _reason(page), (
        "after a completed Execute the disabled control must still state a reason"
    )
