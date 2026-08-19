"""Wizard step 1 -- bind the source and target projects (feature 039, T012).

Why this module exists
----------------------
Step 1 is the only page that decides *which two projects a run is about*, and
that makes it the page with the most host-shaped surface in the wizard: it owns
the source and target pickers, the same-project refusal, the "close the target
in FLEx" guidance, and the `RunContext` every later page reads through
`context()`. Feature 034 exception rows 8 and 10 are both about this page.

It is also the page every other page reaches back through. `_get_source()` and
`_get_target()` on the other nine pages all resolve
`wizard.page_project_ws()` -> `page.context()`, which is why this page can own a
lot without any page importing it: the coupling is a duck-typed method call
through a named wizard accessor, never a class reference.

What is deliberately absent
---------------------------
* The writing-system decision. Binding a pair of projects and mapping their
  writing systems are separate decisions and the second is not answerable until
  the first is done, so they are two pages (feature 036 FR-006) -- see
  `wizard_page_ws.py`.
* `_PageProjectWS`. The old two-in-one page's name survives only as
  `SelectionWizard.page_project_ws()`, the accessor every other page calls.
  Keeping the accessor name while the class was renamed is deliberate: nine
  `_get_source`/`_get_target` implementations name it.
"""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

if __package__:
    from .. import api as gt_api
    from .source_picker import SourcePickerDialog
    from .target_picker import TargetPickerDialog
    from .wizard_page_base import _FlowPage
    from .wizard_widgets import _page_progress
else:
    import api as gt_api  # type: ignore
    from source_picker import SourcePickerDialog  # type: ignore
    from target_picker import TargetPickerDialog  # type: ignore
    from wizard_page_base import _FlowPage  # type: ignore
    from wizard_widgets import _page_progress  # type: ignore


# ---------------------------------------------------------------------------
# Page 1 -- Projects  (feature 036 T010, FR-006/FR-007)
# ---------------------------------------------------------------------------
# WHY THIS PAGE IS NO LONGER "Project + Writing Systems"
# -----------------------------------------------------
# One page used to ask two unrelated questions: which two projects, and how
# every source writing system maps into the target. The second question is
# answerable only *after* the first, so the WS tables sat empty for the whole
# time the operator was reading the page they were on -- and the page's
# subtitle promised a table that was not usable yet. Feature 036 FR-006 splits
# them: this page binds a pair of projects and nothing else, and
# `_PageWritingSystems` (the step after it) owns the mapping and repopulates
# itself from the two bound handles on every entry.
#
# The accessor name `page_project_ws()` is deliberately NOT renamed: 25 call
# sites across this module and the test suite reach the source handle and the
# bound context through it, and renaming a name that still means the same thing
# ("the page that owns the projects") would be churn with no reader benefit.
# The *attribute* behind it is `_page_projects`.


class _PageProjects(_FlowPage):
    """Page 1: bind the source + target projects. Nothing else.

    Under FlexTools the source is already bound (the host's open project,
    passed in at wizard construction time) and the user picks only the target.

    A host with no open project -- the standalone -- passes a `source_binder`,
    and the source becomes a picked project too: the Source row grows a "Pick
    source project..." button that mirrors the Target row's, using the twin
    dialog in `source_picker.py` (feature 034 exception 7). This page is then
    the application's entry point, which is why the choice lives here rather
    than in a separate dialog the host throws up before the wizard opens.

    Same-project is refused in both directions: the source's own project is
    excluded from `list_target_candidates` and refused by `bind_target`, and a
    bound target is excluded from the source list. Re-picking the source
    releases a bound target, because everything downstream -- the writing-system
    mapping on the next page most of all -- is a statement about a *pair* of
    projects and cannot outlive either half.

    Advancing off this page requires BOTH handles (FR-008). Two mechanisms,
    deliberately, because they say different things: the `target_ready*`
    required field greys the Next button, and `validatePage()` plus the inline
    reason label say *why* on the page itself. A greyed button with no
    explanation is the defect FR-008 names.
    """

    def __init__(self, stub, host_project, parent=None, *,
                 source_binder=None, report_sink=None):
        super().__init__(parent)
        self._stub = stub
        self._host = host_project
        # Feature 034 exception 7. `None` (every FlexTools construction) means
        # "the source is host-supplied": no button, no picker, no behaviour
        # change. Callable means "this host has no source of its own"; it takes
        # a project name and returns an open read-only handle. The host keeps
        # ownership of that handle, because the host is what has to close it.
        self._source_binder = source_binder
        self._report = report_sink
        self._context = None   # set when target is bound

        # Unnumbered here on purpose: the run's flow assigns the number on
        # entry (`SelectionWizard._apply_step_number`), because a position is a
        # fact about a *run* and this class cannot know one. The literal that
        # used to be here claimed a total of ten while eleven pages were
        # registered -- the total was already a lie before any page was skipped.
        # (The literal itself is banned from this file by a source-level test,
        # which is why even a comment does not spell one out.)
        self.setTitle("Projects")
        self.setSubTitle(
            (
                "Pick the source project to read from and the target project "
                "to write to. Both are required before you can continue."
            )
            if source_binder is not None else
            # Under FlexTools the source is not picked, so the page describes
            # exactly one choice and must not invite the operator to change a
            # project the host owns (SC-013).
            "Bind the target project to write to. The source project is "
            "already open and cannot be changed here."
        )
        self._build_ui()
        self.registerField("target_ready*", self, "target_ready_prop",
                            self.target_ready_changed)

    # Qt property for the required-field completion gate.
    _target_ready = False
    target_ready_changed = QtCore.pyqtSignal()

    @QtCore.pyqtProperty(bool, notify=target_ready_changed)
    def target_ready_prop(self) -> bool:
        return self._target_ready

    def _set_target_ready(self, val: bool) -> None:
        if val != self._target_ready:
            self._target_ready = val
            self.target_ready_changed.emit()
            self.completeChanged.emit()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # The two project rows are built the same way on purpose: same layout,
        # same label-then-button shape, same dialog mechanics. The only
        # difference is that the Source row's button exists solely for a host
        # that does not supply a source (feature 034 exception 7).
        src_row = QtWidgets.QHBoxLayout()
        src_row.addWidget(QtWidgets.QLabel("Source:", self))
        self._src_label = QtWidgets.QLabel(self._initial_source_text(), self)
        src_row.addWidget(self._src_label, 1)
        self._pick_source_btn = None
        if self._source_binder is not None:
            self._pick_source_btn = QtWidgets.QPushButton(
                "Pick source project...", self
            )
            self._pick_source_btn.clicked.connect(self._on_pick_source)
            src_row.addWidget(self._pick_source_btn)
        layout.addLayout(src_row)

        tgt_row = QtWidgets.QHBoxLayout()
        tgt_row.addWidget(QtWidgets.QLabel("Target:", self))
        self._tgt_label = QtWidgets.QLabel("<i>(not picked)</i>", self)
        tgt_row.addWidget(self._tgt_label, 1)
        self._pick_target_btn = QtWidgets.QPushButton("Pick target project...", self)
        self._pick_target_btn.clicked.connect(self._on_pick_target)
        tgt_row.addWidget(self._pick_target_btn)
        layout.addLayout(tgt_row)
        # Target-after-source is not a preference, it is what makes the
        # same-project rule enforceable by *omission*: the target list is built
        # by excluding the source, so there has to be a source first. Disabled
        # only in the deferred-source case; under FlexTools there always is one.
        if not self._source_is_bound():
            self._pick_target_btn.setEnabled(False)
            self._pick_target_btn.setToolTip(
                "Pick the source project first — the target list is everything "
                "except the source."
            )

        # T011 / FR-008: the refusal, stated on the page. A disabled Next button
        # is the *consequence* of a missing binding, not an explanation of it;
        # an operator who cannot see which of the two halves is missing has to
        # guess. Updated by `_refresh_reason` on every binding change, and read
        # back by `validatePage()` so the two can never disagree.
        self._reason_label = QtWidgets.QLabel("", self)
        self._reason_label.setWordWrap(True)
        layout.addWidget(self._reason_label)
        layout.addStretch(1)
        self._refresh_reason()

    # ------------------------------------------------------------------
    # The advance gate (T011, FR-008)
    # ------------------------------------------------------------------

    def _missing_binding_reason(self) -> str:
        """Why this page will not advance, or "" when it will.

        Names the half that is missing rather than the pair, because "pick your
        projects" is not actionable to someone who has already picked one.
        """
        if not self._source_is_bound():
            if self._source_binder is None:
                # FlexTools with no open project: the operator cannot fix this
                # from here, so say where it is fixed.
                return ("No source project is open. GramTrans reads grammar "
                        "from the project open in FieldWorks; open one and run "
                        "GramTrans again.")
            return "Pick the source project to read from."
        if self._context is None:
            return "Pick the target project to write to."
        return ""

    def _refresh_reason(self) -> None:
        """Show or clear the inline reason. Never raises: it is only a label."""
        label = getattr(self, "_reason_label", None)
        if label is None:
            return
        reason = self._missing_binding_reason()
        label.setText(f"<i>{reason}</i>" if reason else "")
        label.setVisible(bool(reason))

    def validatePage(self) -> bool:
        """Refuse to advance until BOTH projects are bound (FR-008).

        `target_ready*` already greys Next, so this hook is not what stops a
        click in the normal case -- it is what stops every *other* way forward
        (Enter on a focused field, a programmatic `next()`, a future Commit
        button).

        No dialog: the reason is already on the page, and a modal that repeats
        a sentence the operator can see would be the third window feature 034
        removed. `_refresh_reason` is re-run here so the label cannot be stale
        at the moment the refusal happens.
        """
        reason = self._missing_binding_reason()
        self._refresh_reason()
        return not reason

    # ------------------------------------------------------------------
    # Source binding (feature 034 exception 7)
    # ------------------------------------------------------------------

    def _source_is_bound(self) -> bool:
        return bool(getattr(self._stub, "source_project_name", ""))

    def _initial_source_text(self) -> str:
        if not self._source_is_bound():
            return "<i>(not picked)</i>"
        if self._source_binder is None:
            # FlexTools: unchanged wording, because there it is the truth.
            return f"<b>{self._stub.source_project_name}</b> (open in FlexTools)"
        return f"<b>{self._stub.source_project_name}</b> (read-only)"

    def _on_pick_source(self) -> None:
        """Pick + open the source, mirroring `_on_pick_target` step for step."""
        if self._source_binder is None:      # defensive: no button exists
            return
        if self._context is not None and not self._confirm_release_target():
            return

        candidates = gt_api.list_source_candidates(
            getattr(self._stub, "projects_root", ""),
            # The other half of the same-project rule. `list_target_candidates`
            # excludes the source; this excludes a target already bound, so the
            # pair can never collapse onto one project from either direction.
            exclude_names=tuple(
                n for n in (self._bound_target_name(),) if n
            ),
            exclude_paths=tuple(
                p for p in (self._bound_target_path(),) if p
            ),
        )
        dlg = SourcePickerDialog(candidates, parent=self)
        if not candidates:
            # Show the dialog anyway: its empty-list message says what to do,
            # where a QMessageBox here would say it in a different voice.
            dlg.exec()
            return
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        choice = dlg.selected_candidate()
        if choice is None:
            return

        # FR-023 row 1. No cheap total exists -- nothing can be counted before
        # the project is open -- so this is the elapsed-time trigger by
        # construction (FR-014b/FR-014d): indeterminate, and shown only if
        # opening takes longer than the threshold. `_page_progress` reads that
        # off `rate_for("bind_source") is None`, so the choice is declared in the
        # calibration table rather than repeated here.
        try:
            with _page_progress(self, "bind_source"):
                handle = self._source_binder(choice.project_name)
        except Exception as exc:  # noqa: BLE001 -- LCM raises a variety of types
            # FR-034: attributed to the project that would not open, with the
            # rest of the list still choosable.
            QtWidgets.QMessageBox.critical(
                self, "GramTrans",
                f"GramTrans could not open {choice.project_name!r} as the "
                f"source project.\n\nIf it is open in FieldWorks Language "
                f"Explorer, close it and try again, or choose a different "
                f"project.\n\nDetails: {exc!s}",
            )
            self._log(f"[GramTrans] Could not open source "
                      f"{choice.project_name!r}: {exc}", error=True)
            return

        self._release_bound_target()
        self._bind_source_handle(handle, choice.project_name, choice.project_path)

    def _bind_source_handle(self, handle, project_name: str,
                            project_path: str) -> None:
        """Adopt an opened source handle: stub, labels, and the wizard's `_host`.

        `dataclasses.replace` rather than a fresh `initialize_run` so `run_id`
        and `started_at` survive re-picking. They are stamped into the residue
        tag of everything a Move writes, and a run that changed its identity
        halfway through choosing projects would be untraceable afterwards.
        """
        import dataclasses

        self._host = handle
        self._stub = dataclasses.replace(
            self._stub,
            source_handle=handle,
            source_project_name=project_name,
            source_project_path=project_path,
        )
        # Same shape as the target row's label, so the pair reads as a pair.
        if project_path:
            self._src_label.setText(
                f"<b>{project_name}</b> (read-only) (<code>{project_path}</code>)"
            )
        else:
            self._src_label.setText(f"<b>{project_name}</b> (read-only)")
        # Downstream pages resolve the source through `wizard._host` (or through
        # the bound context); keep the wizard's copy in step with ours.
        wizard = self.wizard()
        if wizard is not None:
            wizard._host = handle
            # T014: the ONE place a bind refreshes the cheap-count snapshot the
            # page-skip predicates read. Doing it here, at the bind, is what
            # keeps `nextId()` free of project queries (D5b).
            if hasattr(wizard, "refresh_source_counts"):
                wizard.refresh_source_counts(handle)
        self._pick_target_btn.setEnabled(True)
        self._pick_target_btn.setToolTip("")
        self._refresh_reason()
        self._log(f"  Source (read-only): {project_name!r}")

    def _confirm_release_target(self) -> bool:
        """Changing the source after a target is bound: ask, then release.

        The writing-system mapping, and every inventory the later pages build,
        are statements about a *pair* of projects. Silently keeping the target
        bound while the source changes underneath it would leave the WS table
        describing a pairing that no longer exists.
        """
        answer = QtWidgets.QMessageBox.question(
            self, "GramTrans — Change the source project?",
            f"{self._bound_target_name() or 'The target project'} is currently "
            "bound as the target.\n\nChanging the source releases it and clears "
            "your writing-system choices, and you will need to pick the target "
            "again.\n\nChange the source anyway?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes

    def _release_bound_target(self) -> None:
        """Close a previously-bound target and reset everything that named it.

        `CloseProject()` matters here and is not merely tidy: `bind_target`
        opened it write-enabled, so a dropped handle would leave the project
        locked for the rest of the process with nothing left holding a
        reference to unlock it. `gramtrans.py._run_gui` only ever closes the
        *current* context's handle.
        """
        ctx = self._context
        if ctx is None:
            return
        target = getattr(ctx, "target_handle", None)
        name = getattr(ctx, "target_project_name", "")
        self._context = None
        if target is not None:
            try:
                target.CloseProject()
                self._log(f"[GramTrans] Target project {name!r} released "
                          "(source changed).")
            except Exception as exc:  # noqa: BLE001
                self._log(f"[GramTrans] Could not close target project "
                          f"{name!r}: {exc}", warning=True)
        self._tgt_label.setText("<i>(not picked)</i>")
        self._set_target_ready(False)
        self._refresh_reason()
        # The WS row state that named the released target is NOT cleared from
        # here any more, and must not be: after the FR-006 split this page has
        # no reference to those tables. `_PageWritingSystems.initializePage`
        # rebuilds them from scratch on every entry, so a released project's
        # rows cannot survive into the next visit (data-model s1 edge case).
        # Clearing across the split would be a second owner of the same state.

    def _bound_target_name(self) -> str:
        return getattr(self._context, "target_project_name", "") \
            if self._context is not None else ""

    def _bound_target_path(self) -> str:
        return getattr(self._context, "target_project_path", "") \
            if self._context is not None else ""

    def _log(self, message: str, *, warning: bool = False,
             error: bool = False) -> None:
        """Best-effort line to the host's report sink; never raises."""
        sink = self._report
        if sink is None:
            return
        try:
            if error:
                sink.Error(message)
            elif warning:
                sink.Warning(message)
            else:
                sink.Info(message)
        except Exception:  # noqa: BLE001 -- logging must not break the picker
            pass

    # ------------------------------------------------------------------
    def _on_pick_target(self) -> None:
        if not self._source_is_bound():
            QtWidgets.QMessageBox.information(
                self, "GramTrans",
                "Pick the source project first. GramTrans copies grammar from "
                "one project into another, so the target list is everything "
                "except the source.",
            )
            return
        candidates = gt_api.list_target_candidates(self._stub)
        if not candidates:
            QtWidgets.QMessageBox.warning(
                self,
                "GramTrans",
                "No candidate target projects found in the FieldWorks projects directory.",
            )
            return
        dlg = TargetPickerDialog(candidates, parent=self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        choice = dlg.selected_candidate()
        if choice is None:
            return
        # FR-023 row 2. Same shape as the source bind above, and the same reason:
        # a project has no cheap size until it is open.
        try:
            with _page_progress(self, "bind_target"):
                self._context = gt_api.bind_target(self._stub, choice)
        except gt_api.SameProjectError as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        except gt_api.TargetUnavailable as e:
            QtWidgets.QMessageBox.critical(self, "GramTrans", str(e))
            return
        self._tgt_label.setText(
            f"<b>{choice.project_name}</b> (<code>{choice.project_path}</code>)"
        )
        # The target WS enumeration and the MAP/CREATE/SKIP tables used to be
        # built from here, on this page. They now belong to the step after this
        # one, which enumerates on `initializePage` from the two handles this
        # page bound -- so binding a target no longer pays for a WS walk the
        # operator may never look at (FR-006).
        self._set_target_ready(True)
        self._refresh_reason()

    def context(self):
        return self._context

    def isComplete(self) -> bool:
        return self._target_ready
