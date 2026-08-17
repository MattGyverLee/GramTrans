"""Exception 7 — the source is picked on step 1, beside the target.

The application used to open three things at once: its own window, a modal
source chooser, and then the wizard. The chooser is now the Source row of the
wizard's step 1, mirroring the Target row that was always there, so the entry
point is step 1 and there is exactly one thing to read at a time.

What has to hold, and is asserted here:

* **FlexTools is untouched.** No binder means no button, no picker, and the
  page's subtitle byte for byte as it was (SC-013).
* **The deferred host gets both rows.** Source button present, target refused
  until a source exists — which is what makes the same-project rule enforceable
  by omission rather than by a check that could be forgotten.
* **Same project, both directions.** The source is excluded from the target
  list; a bound target is excluded from the source list.
* **The run keeps its identity.** Re-picking the source must not re-mint
  `run_id`: it is stamped into the residue tag of everything a Move writes.
* **Handles are owned by the host.** The picker asks; the session opens and
  closes. A re-pick closes the project it replaces.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

# SC-007 convention: offscreen platform before Qt is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

PyQt6 = pytest.importorskip("PyQt6")

from PyQt6 import QtWidgets  # noqa: E402

from gramtrans.Lib import api as gt_api  # noqa: E402
from gramtrans.Lib.ui import selection_wizard as sw  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The step-1 subtitle before exception 7 existed. Spelled out rather than
# imported so a change to it is a deliberate two-file edit.
_FLEXTOOLS_SUBTITLE = (
    "Bind a target project and map source writing systems to target "
    "writing systems. Each WS can be Mapped, Created, or Skipped."
)


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


def _projects_tree(root: Path, names) -> None:
    """A directory that looks like a FLEx projects root: <name>/<name>.fwdata."""
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.fwdata").write_text("<!-- fixture -->", encoding="utf-8")


def _stub(**kwargs):
    fields = {
        "source_handle": None,
        "source_project_name": "",
        "source_project_path": "",
        "run_id": "GT-20260817-000000",
        "started_at": "2026-08-17T00:00:00",
        "projects_root": "",
    }
    fields.update(kwargs)
    return gt_api.RunContextStub(**fields)


def _needs_a_real_qwizard():
    """Skip when a sibling module has swapped a QWizard double into PyQt6.

    `test_wizard_page_flow.py` and `test_ui_gating.py` install a Qt double at
    import time and overwrite `QtWidgets.QWizard`/`QWizardPage` on whatever is
    in `sys.modules` -- including the real extension module, when real PyQt6
    was imported first. Constructing a real wizard is then impossible for the
    rest of the session. The page-level assertions below cover the same
    behaviour and are unaffected, because `_PageProjectWS` was built against
    the real base class at import time.
    """
    if not isinstance(getattr(QtWidgets.QWizard, "WizardStyle", None), type):
        pytest.skip("a PyQt6 double is installed in this session (see docstring)")


def _page(qapp, **kwargs):
    """A step-1 page, constructed the way the wizard constructs it."""
    stub = kwargs.pop("stub", None) or _stub()
    host = kwargs.pop("host", None)
    return sw._PageProjectWS(stub, host, **kwargs)


class _PickerDouble:
    """Stand-in for `SourcePickerDialog`: chooses `choice`, or cancels."""

    def __init__(self, choice, accepted=True):
        self._choice = choice
        self._accepted = accepted
        self.constructed_with = None
        self.exec_calls = 0

    def __call__(self, candidates, parent=None):
        self.constructed_with = list(candidates)
        return self

    def exec(self):
        self.exec_calls += 1
        return (QtWidgets.QDialog.DialogCode.Accepted if self._accepted
                else QtWidgets.QDialog.DialogCode.Rejected)

    def selected_candidate(self):
        return self._choice if self._accepted else None


# ===========================================================================
# The host boundary keeps its shape
# ===========================================================================

def test_source_binder_is_keyword_only_and_defaults_to_none():
    """A fourth positional parameter would silently absorb a host's argument."""
    import gramtrans.gramtrans as entry

    for func in (entry.MainFunction, entry._run_gui,
                 sw.SelectionWizard.__init__):
        param = inspect.signature(func).parameters["source_binder"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, func
        assert param.default is None, func


# ===========================================================================
# FlexTools: no binder, no change
# ===========================================================================

def test_flextools_page_has_no_source_button_and_can_pick_a_target(qapp):
    page = _page(qapp, stub=_stub(source_project_name="Host Project"))

    assert page._pick_source_btn is None
    assert page._pick_target_btn.isEnabled() is True
    assert "Host Project" in page._src_label.text()
    assert "open in FlexTools" in page._src_label.text()


def test_the_flextools_subtitle_is_byte_identical(qapp):
    page = _page(qapp, stub=_stub(source_project_name="Host Project"))
    assert page.subTitle() == _FLEXTOOLS_SUBTITLE


def test_the_deferred_subtitle_mentions_both_choices(qapp):
    page = _page(qapp, source_binder=lambda name: object())
    assert page.subTitle() != _FLEXTOOLS_SUBTITLE
    assert "source" in page.subTitle().lower()
    assert "target" in page.subTitle().lower()


# ===========================================================================
# The deferred host: both rows, source first
# ===========================================================================

def test_a_deferred_source_starts_unpicked_with_the_target_refused(qapp):
    page = _page(qapp, source_binder=lambda name: object())

    assert page._pick_source_btn is not None
    assert "not picked" in page._src_label.text()
    # Target disabled, not merely unclicked: the target list is built by
    # excluding the source, so there has to be a source first.
    assert page._pick_target_btn.isEnabled() is False
    assert page._pick_target_btn.toolTip()
    assert page.isComplete() is False


def test_picking_a_source_binds_it_and_opens_the_target_row(qapp, tmp_path,
                                                            monkeypatch):
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    handle = object()
    opened = []

    def binder(name):
        opened.append(name)
        return handle

    sink = _Sink()
    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=binder, report_sink=sink)

    double = _PickerDouble(gt_api.SourceCandidate("Beta", str(tmp_path / "Beta")))
    monkeypatch.setattr(sw, "SourcePickerDialog", double)
    page._on_pick_source()

    assert opened == ["Beta"]
    assert [c.project_name for c in double.constructed_with] == ["Alpha", "Beta"]
    assert page._stub.source_project_name == "Beta"
    assert page._stub.source_project_path == str(tmp_path / "Beta")
    assert page._stub.source_handle is handle
    assert page._host is handle
    assert page._pick_target_btn.isEnabled() is True
    assert "Beta" in page._src_label.text()
    # Still not complete: the target is a separate, deliberate choice.
    assert page.isComplete() is False


def test_cancelling_the_source_picker_changes_nothing(qapp, tmp_path,
                                                     monkeypatch):
    _projects_tree(tmp_path, ["Alpha"])
    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=lambda name: object())

    monkeypatch.setattr(sw, "SourcePickerDialog",
                        _PickerDouble(None, accepted=False))
    page._on_pick_source()

    assert page._stub.source_project_name == ""
    assert page._host is None
    assert page._pick_target_btn.isEnabled() is False


def test_re_picking_the_source_keeps_the_run_id(qapp, tmp_path, monkeypatch):
    """`run_id` is stamped into the residue tag of everything a Move writes.

    A run that re-minted its identity while the user was still choosing
    projects would leave additions that no log line accounts for.
    """
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=lambda name: object())
    before = (page._stub.run_id, page._stub.started_at)

    monkeypatch.setattr(sw, "SourcePickerDialog", _PickerDouble(
        gt_api.SourceCandidate("Alpha", str(tmp_path / "Alpha"))))
    page._on_pick_source()
    monkeypatch.setattr(sw, "SourcePickerDialog", _PickerDouble(
        gt_api.SourceCandidate("Beta", str(tmp_path / "Beta"))))
    page._on_pick_source()

    assert (page._stub.run_id, page._stub.started_at) == before
    assert page._stub.source_project_name == "Beta"
    # The projects root survives a re-pick too -- otherwise the next target
    # list would silently fall back to the default install location.
    assert page._stub.projects_root == str(tmp_path)


def test_a_source_that_will_not_open_is_reported_and_nothing_is_bound(
        qapp, tmp_path, monkeypatch):
    """FR-034: attributed to the project, with the rest of the list intact."""
    _projects_tree(tmp_path, ["Alpha"])
    shown = []

    def _critical(parent, title, text, *a, **kw):
        shown.append(text)
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", staticmethod(_critical))

    def binder(name):
        raise RuntimeError("the project is open in FLEx")

    sink = _Sink()
    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=binder, report_sink=sink)
    monkeypatch.setattr(sw, "SourcePickerDialog", _PickerDouble(
        gt_api.SourceCandidate("Alpha", str(tmp_path / "Alpha"))))
    page._on_pick_source()

    assert shown and "Alpha" in shown[0]
    assert "the project is open in FLEx" in shown[0]
    assert page._stub.source_project_name == ""
    assert page._host is None
    assert page._pick_target_btn.isEnabled() is False
    assert any(kind == "error" for kind, _ in sink.lines)


# ===========================================================================
# Same project, refused from both directions
# ===========================================================================

def test_the_source_list_excludes_a_project_by_name_and_by_path(tmp_path):
    _projects_tree(tmp_path, ["Alpha", "Beta", "Gamma"])

    by_name = gt_api.list_source_candidates(
        str(tmp_path), exclude_names=("Beta",))
    assert [c.project_name for c in by_name] == ["Alpha", "Gamma"]

    # Path exclusion is the half that catches two names for one directory.
    by_path = gt_api.list_source_candidates(
        str(tmp_path), exclude_paths=(str(tmp_path / "Gamma").upper() + os.sep,))
    assert [c.project_name for c in by_path] == ["Alpha", "Beta"]


def test_the_two_lists_agree_about_what_a_project_is(tmp_path):
    """Source and target enumeration must not drift apart.

    Same directory rule, same root, same order -- with each role's own
    exclusion applied. A `.fwdata`-less directory is not a project to either.
    """
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    (tmp_path / "NotAProject").mkdir()

    stub = _stub(projects_root=str(tmp_path), source_project_name="Alpha")
    targets = [c.project_name for c in gt_api.list_target_candidates(stub)]
    sources = [c.project_name for c in gt_api.list_source_candidates(
        str(tmp_path), exclude_names=("Beta",))]

    assert targets == ["Beta"]
    assert sources == ["Alpha"]


def test_a_bound_target_is_excluded_from_the_source_list(qapp, tmp_path,
                                                         monkeypatch):
    """The other half of the same-project rule, in the direction that is new."""
    _projects_tree(tmp_path, ["Alpha", "Beta", "Gamma"])

    class _Ctx:
        target_project_name = "Gamma"
        target_project_path = str(tmp_path / "Gamma")
        target_handle = None

    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=lambda name: object())
    page._context = _Ctx()

    double = _PickerDouble(gt_api.SourceCandidate("Alpha",
                                                  str(tmp_path / "Alpha")))
    monkeypatch.setattr(sw, "SourcePickerDialog", double)
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        staticmethod(lambda *a, **kw: QtWidgets.QMessageBox.StandardButton.Yes),
    )
    page._on_pick_source()

    assert [c.project_name for c in double.constructed_with] == ["Alpha", "Beta"]


def test_changing_the_source_releases_a_bound_target(qapp, tmp_path,
                                                     monkeypatch):
    """`bind_target` opened it write-enabled; a dropped handle stays locked."""
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    closed = []

    class _Handle:
        def CloseProject(self):  # noqa: N802
            closed.append(True)

    class _Ctx:
        target_project_name = "Beta"
        target_project_path = str(tmp_path / "Beta")
        target_handle = _Handle()

    sink = _Sink()
    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=lambda name: object(), report_sink=sink)
    page._context = _Ctx()
    page._set_target_ready(True)

    monkeypatch.setattr(sw, "SourcePickerDialog", _PickerDouble(
        gt_api.SourceCandidate("Alpha", str(tmp_path / "Alpha"))))
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        staticmethod(lambda *a, **kw: QtWidgets.QMessageBox.StandardButton.Yes),
    )
    page._on_pick_source()

    assert closed == [True]
    assert page.context() is None
    assert page.isComplete() is False
    assert "not picked" in page._tgt_label.text()


def test_declining_the_release_leaves_both_bindings_alone(qapp, tmp_path,
                                                          monkeypatch):
    _projects_tree(tmp_path, ["Alpha", "Beta"])

    class _Ctx:
        target_project_name = "Beta"
        target_project_path = str(tmp_path / "Beta")
        target_handle = None

    page = _page(qapp, stub=_stub(projects_root=str(tmp_path)),
                 source_binder=lambda name: object())
    ctx = _Ctx()
    page._context = ctx

    called = []
    monkeypatch.setattr(sw, "SourcePickerDialog",
                        lambda *a, **kw: called.append(True))
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        staticmethod(lambda *a, **kw: QtWidgets.QMessageBox.StandardButton.No),
    )
    page._on_pick_source()

    assert called == []
    assert page.context() is ctx


# ===========================================================================
# The wizard opens with nothing bound
# ===========================================================================

def test_the_wizard_constructs_with_no_source_at_all(qapp, tmp_path):
    """The entry point: step 1, both rows, nothing opened yet.

    Constructing the whole wizard (not just page 1) is the assertion that
    matters here -- it is what proves the application can reach its first
    screen with no project open, which is the whole point of exception 7.
    """
    _needs_a_real_qwizard()
    _projects_tree(tmp_path, ["Alpha", "Beta"])
    wizard = sw.SelectionWizard(
        None, _Sink(), True,
        source_project_name="",
        projects_root=str(tmp_path),
        source_binder=lambda name: object(),
    )
    page = wizard.page_project_ws()

    assert wizard.context() is None
    assert page._pick_source_btn is not None
    assert page._pick_target_btn.isEnabled() is False
    assert wizard._host is None


def test_binding_a_source_updates_the_wizards_own_handle(qapp, tmp_path,
                                                         monkeypatch):
    """Downstream pages read the source through `wizard._host`."""
    _needs_a_real_qwizard()
    _projects_tree(tmp_path, ["Alpha"])
    handle = object()
    wizard = sw.SelectionWizard(
        None, _Sink(), True,
        source_project_name="",
        projects_root=str(tmp_path),
        source_binder=lambda name: handle,
    )
    monkeypatch.setattr(sw, "SourcePickerDialog", _PickerDouble(
        gt_api.SourceCandidate("Alpha", str(tmp_path / "Alpha"))))
    wizard.page_project_ws()._on_pick_source()

    assert wizard._host is handle


# ===========================================================================
# The shell: no third window, and the binder is what it hands over
# ===========================================================================

def test_the_shell_opens_no_project_chooser_of_its_own():
    """The modal-before-the-window is gone, not merely unused."""
    shell = _REPO_ROOT / "src" / "gramtrans" / "standalone"
    text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(shell.rglob("*.py"))
        if "__pycache__" not in p.parts
    )
    assert "SourcePickerDialog" not in text, (
        "the source chooser belongs to the wizard's step 1 now; a second copy "
        "in the shell is the third window this change removed"
    )


def test_the_session_hands_its_own_bind_source_to_the_module(monkeypatch):
    """`MainFunction` gets the binder, and the session keeps handle ownership."""
    import gramtrans.gramtrans as entry
    from gramtrans.standalone.app import HostSession, SessionState

    session = HostSession.__new__(HostSession)
    session.state = SessionState.PREREQ_OK
    session.report_sink = _Sink()
    session.source_handle = None
    session.source_project_name = ""
    session._confirmation_gate = None
    session._flexicon = None

    captured = {}

    def _main(project, report, modify_allowed, **kwargs):
        captured["project"] = project
        captured.update(kwargs)

    monkeypatch.setattr(entry, "MainFunction", _main)
    monkeypatch.setattr(
        "gramtrans.standalone.fwglobals.projects_dir", lambda: r"X:\Projects"
    )
    session.run()

    assert captured["project"] is None       # nothing open yet -- step 1 asks
    assert captured["source_binder"] == session.bind_source
    assert captured["projects_root"] == r"X:\Projects"
    assert session.state is SessionState.RUNNING


def test_rebinding_the_source_closes_the_one_it_replaces():
    """A user who changes their mind must not leave a handle open."""
    from gramtrans.standalone.app import HostSession, SessionState

    closed = []

    class _Handle:
        def __init__(self, name=""):
            self.name = name

        def OpenProject(self, projectName="", writeEnabled=False):  # noqa: N803
            assert writeEnabled is False   # FR-007: the source is read-only
            self.name = projectName

        def CloseProject(self):  # noqa: N802
            closed.append(self.name)

    class _Flexicon:
        FLExProject = _Handle

    session = HostSession.__new__(HostSession)
    session.state = SessionState.RUNNING
    session.report_sink = _Sink()
    session.source_handle = None
    session.source_project_name = ""
    session._flexicon = _Flexicon()

    session.bind_source("Alpha")
    first = session.source_handle
    session.bind_source("Beta")

    assert closed == ["Alpha"]
    assert session.source_handle is not first
    assert session.source_project_name == "Beta"
    # Binding from inside the run must not walk the state machine backwards.
    assert session.state is SessionState.RUNNING
