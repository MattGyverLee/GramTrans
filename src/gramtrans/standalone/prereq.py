"""Prerequisite detection and the self-check report (FR-031..FR-033, FR-036).

`data-model.md` "PrerequisiteReport". One ordered list of independently
verdicted checks, rendered by `selfcheck.py` into the single copyable block
FR-037 asks for.

Two rules shape everything here.

**Every FieldWorks value comes through `fwglobals`.** This module names no
flexicon global directly, and `tests/unit/test_034_fwglobals_only.py` fails the
build if it starts to. A detection wired to a stale or empty read reports
"FieldWorks not detected" on a working machine, which is the worst thing a
diagnostic can do.

**No `winreg` access of our own** (FR-044). flexicon's `InitialiseFWGlobals()`
already probes `HKCU`/`HKLM`, validates that `FieldWorks.exe` exists under the
code directory, and puts that directory on `sys.path`. A second probe here
could report a code directory *different from the one whose assemblies were
actually loaded* — a diagnostic that disagrees with reality is worse than none.

A check that fails **must** carry a remedy (FR-036, SC-006). That is enforced
in :meth:`PrerequisiteReport.__post_init__`, not left to reviewers, because a
`[FAIL]` with no next step is precisely the dead end this feature exists to
remove.
"""
from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

__all__ = ["Verdict", "PrerequisiteCheck", "PrerequisiteReport", "run_checks"]


class Verdict(enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PrerequisiteCheck:
    name: str
    detected: str
    expected: str
    verdict: Verdict
    remedy: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PrerequisiteCheck.name must be non-empty")
        if self.verdict is Verdict.FAIL and not self.remedy.strip():
            raise ValueError(
                f"check {self.name!r} FAILs with no remedy — FR-036/SC-006 "
                "require every failing check to name a concrete next step"
            )


@dataclass(frozen=True)
class PrerequisiteReport:
    checks: List[PrerequisiteCheck] = field(default_factory=list)
    app_version: str = ""
    generated_at: str = ""
    log_path: str = ""

    @property
    def overall(self) -> Verdict:
        """FAIL if any check failed, else PASS.

        `UNKNOWN` deliberately does not fail the report: it means "could not
        determine", and a self-check that refuses to say PASS because one
        optional fact was unreadable would train users to ignore it.
        """
        if any(c.verdict is Verdict.FAIL for c in self.checks):
            return Verdict.FAIL
        return Verdict.PASS

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.verdict is Verdict.PASS)

    @property
    def total(self) -> int:
        return len(self.checks)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _app_version() -> str:
    """The stamped build version, falling back for a source checkout (R10)."""
    try:
        from gramtrans import _buildinfo  # type: ignore

        described = getattr(_buildinfo, "VERSION", "") or ""
        built = getattr(_buildinfo, "BUILT_AT", "")
        return f"{described} (built {built})" if built else described
    except Exception:  # noqa: BLE001 — absent on every developer run
        try:
            from gramtrans.gramtrans import __version__ as v
        except Exception:  # noqa: BLE001
            v = "unknown"
        return f"{v} (source checkout)"


def _distribution_versions(names: Sequence[str]) -> "dict[str, str]":
    from importlib import metadata

    found = {}
    for name in names:
        try:
            found[name] = metadata.version(name)
        except Exception:  # noqa: BLE001 — PackageNotFoundError and friends
            found[name] = ""
    return found


def _check_ui_toolkit() -> PrerequisiteCheck:
    """FR-006. First, and load-bearing: if this fails there is no application.

    Constructing a `QApplication` — not merely importing PyQt6 — because the
    import can succeed on a machine where the platform plugin cannot start,
    and it is the construction that `MainFunction` needs in order not to take
    its no-interface branch (which is what makes FR-005 hold).
    """
    try:
        from PyQt6 import QtCore, QtWidgets
    except Exception as exc:  # noqa: BLE001
        return PrerequisiteCheck(
            name="UI toolkit",
            detected=f"PyQt6 could not be imported ({type(exc).__name__}: {exc})",
            expected="importable and constructible",
            verdict=Verdict.FAIL,
            remedy=(
                "This is a packaging fault, not something you can fix on this "
                "computer. Reinstall GramTrans, and if it happens again send "
                "the log file to whoever supplied it."
            ),
        )
    try:
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        _ = app  # constructed is the assertion
        version = QtCore.QT_VERSION_STR
    except Exception as exc:  # noqa: BLE001
        return PrerequisiteCheck(
            name="UI toolkit",
            detected=f"a window system could not be started ({exc})",
            expected="importable and constructible",
            verdict=Verdict.FAIL,
            remedy=(
                "GramTrans needs a normal Windows desktop session. If you are "
                "running it over a remote connection or as a service, try "
                "again from a signed-in desktop."
            ),
        )
    return PrerequisiteCheck(
        name="UI toolkit",
        detected=f"PyQt6 (Qt {version})",
        expected="importable and constructible",
        verdict=Verdict.PASS,
    )


def _fieldworks_checks() -> List[PrerequisiteCheck]:
    """The FieldWorks block: install, runtime, version, and the two locations.

    Ordered so a reader sees causes before consequences. When the import
    fails, the remaining checks are reported `UNKNOWN` rather than `FAIL` —
    they were not tested, and saying otherwise would put four red lines on the
    screen for one problem.
    """
    from gramtrans.standalone import fwglobals

    checks: List[PrerequisiteCheck] = []

    try:
        flexicon = fwglobals.probe()
    except fwglobals.FieldWorksNotDetected as exc:
        checks.append(PrerequisiteCheck(
            name="FieldWorks installed",
            detected=f"not found ({exc})",
            expected="a directory containing FieldWorks.exe",
            verdict=Verdict.FAIL,
            remedy=(
                "Install FieldWorks 9 and run GramTrans again. If it is "
                "already installed, it may belong to a different Windows user "
                "account — try the account that installed it."
            ),
        ))
        for name, expected in (
            ("Language-model runtime", "initialises without error"),
            ("Projects enumerated", "at least one FieldWorks project"),
            ("FieldWorks version", "a supported major version"),
            ("FieldWorks code location", "an existing directory"),
            ("FieldWorks projects location", "an existing directory"),
        ):
            checks.append(PrerequisiteCheck(
                name=name,
                detected="not tested (FieldWorks was not found)",
                expected=expected,
                verdict=Verdict.UNKNOWN,
            ))
        return checks

    checks.append(PrerequisiteCheck(
        name="FieldWorks installed",
        detected="found",
        expected="a directory containing FieldWorks.exe",
        verdict=Verdict.PASS,
    ))

    try:
        flexicon.FLExInitialize()
        fwglobals.mark_initialized()
    except Exception as exc:  # noqa: BLE001
        checks.append(PrerequisiteCheck(
            name="Language-model runtime",
            detected=f"failed to start ({type(exc).__name__}: {exc})",
            expected="initialises without error",
            verdict=Verdict.FAIL,
            remedy=(
                "Repair or reinstall FieldWorks 9, then run GramTrans again. "
                "Send this report and the log file if it keeps happening."
            ),
        ))
        for name, expected in (
            ("Projects enumerated", "at least one FieldWorks project"),
            ("FieldWorks version", "a supported major version"),
            ("FieldWorks code location", "an existing directory"),
            ("FieldWorks projects location", "an existing directory"),
        ):
            checks.append(PrerequisiteCheck(
                name=name, detected="not tested (the runtime did not start)",
                expected=expected, verdict=Verdict.UNKNOWN,
            ))
        return checks

    runtime = "initialised"
    versions = _distribution_versions(("pythonnet", "clr_loader"))
    if versions.get("pythonnet"):
        runtime += f" (pythonnet {versions['pythonnet']})"
    checks.append(PrerequisiteCheck(
        name="Language-model runtime",
        detected=runtime,
        expected="initialises without error",
        verdict=Verdict.PASS,
    ))

    checks.append(_check_projects_enumerated(flexicon))
    checks.append(_check_version(fwglobals))
    checks.append(_check_directory(
        fwglobals, "FieldWorks code location", fwglobals.code_dir,
        "an existing directory containing FieldWorks.exe",
        "Repair or reinstall FieldWorks 9 — its program files are not where "
        "Windows records them.",
    ))
    checks.append(_check_directory(
        fwglobals, "FieldWorks projects location", fwglobals.projects_dir,
        "an existing directory",
        "Open FieldWorks Language Explorer once to create the projects "
        "folder, or restore it if it was moved or deleted.",
    ))
    return checks


def _check_projects_enumerated(flexicon) -> PrerequisiteCheck:
    """Can we actually list projects? (smoke check 3, FR-048)

    Distinct from "the projects directory exists": this exercises the whole
    LCM path — `AllProjectNames()` goes through `FwDirectoryFinder`, which
    means assemblies loaded, CLR alive, and FieldWorks' own idea of where
    projects live. It is the cheapest end-to-end proof that the runtime works,
    and inside a frozen bundle it is the check that catches a hook that failed
    to collect a native DLL.

    Zero projects is `UNKNOWN`, not `FAIL`: a machine with FieldWorks and no
    projects yet is unusual but not broken, and the remedy is not GramTrans's
    to give.
    """
    try:
        names = list(flexicon.AllProjectNames())
    except Exception as exc:  # noqa: BLE001
        return PrerequisiteCheck(
            name="Projects enumerated",
            detected=f"could not list projects ({type(exc).__name__}: {exc})",
            expected="at least one FieldWorks project",
            verdict=Verdict.FAIL,
            remedy=(
                "GramTrans could reach FieldWorks but not its project list. "
                "Open FieldWorks Language Explorer once, then try again; send "
                "this report and the log file if it does not help."
            ),
        )
    if not names:
        return PrerequisiteCheck(
            name="Projects enumerated",
            detected="0",
            expected="at least one FieldWorks project",
            verdict=Verdict.UNKNOWN,
        )
    return PrerequisiteCheck(
        name="Projects enumerated", detected=str(len(names)),
        expected="at least one FieldWorks project", verdict=Verdict.PASS,
    )


def _check_version(fwglobals) -> PrerequisiteCheck:
    """FR-032, reporting flexicon's supported range rather than our own."""
    try:
        detected = fwglobals.short_version()
        supported = fwglobals.supported_versions()
        major = fwglobals.major_version()
    except fwglobals.FieldWorksRuntimeUnavailable as exc:
        return PrerequisiteCheck(
            name="FieldWorks version",
            detected=f"could not be read ({exc})",
            expected="a supported major version",
            verdict=Verdict.FAIL,
            remedy=(
                "Repair or reinstall FieldWorks 9. Choose Help -> Self-check... "
                "again afterwards and send this report if it does not change."
            ),
        )
    expected = "major version " + " or ".join(supported)
    if major in supported:
        return PrerequisiteCheck(
            name="FieldWorks version", detected=detected,
            expected=expected, verdict=Verdict.PASS,
        )
    return PrerequisiteCheck(
        name="FieldWorks version",
        detected=detected,
        expected=expected,
        verdict=Verdict.FAIL,
        remedy=(
            f"GramTrans supports FieldWorks {' or '.join(supported)}. Install a "
            "supported version to use GramTrans on this computer."
        ),
    )


def _check_directory(fwglobals, name, reader, expected, remedy) -> PrerequisiteCheck:
    try:
        value = reader()
    except fwglobals.FieldWorksRuntimeUnavailable as exc:
        return PrerequisiteCheck(
            name=name, detected=f"not reported ({exc})", expected=expected,
            verdict=Verdict.FAIL, remedy=remedy,
        )
    if not os.path.isdir(value):
        return PrerequisiteCheck(
            name=name, detected=f"{value} (does not exist)", expected=expected,
            verdict=Verdict.FAIL, remedy=remedy,
        )
    return PrerequisiteCheck(
        name=name, detected=value, expected=expected, verdict=Verdict.PASS,
    )


def _check_components() -> PrerequisiteCheck:
    """What is actually installed, for comparison with `build/requirements.lock`.

    Reported, not verdicted against the lock: the lock is a *build* artifact,
    and a source checkout legitimately has different versions. The smoke test
    (T045 check 6) is where the frozen artifact is held to the pinned set.
    """
    names = ("pyflexicon", "PyQt6", "pythonnet", "flextoolslib")
    found = _distribution_versions(names)
    missing = [n for n, v in found.items() if not v]
    detected = ", ".join(f"{n} {v}" for n, v in found.items() if v) or "none found"
    if missing:
        return PrerequisiteCheck(
            name="Bundled components",
            detected=f"{detected}; not found: {', '.join(missing)}",
            expected="the versions in build/requirements.lock",
            verdict=Verdict.FAIL,
            remedy=(
                "A component GramTrans ships with is missing. Reinstall "
                "GramTrans; do not copy individual files between installations."
            ),
        )
    return PrerequisiteCheck(
        name="Bundled components", detected=detected,
        expected="the versions in build/requirements.lock", verdict=Verdict.PASS,
    )


def _check_log_location(log_path: str, log_error: Optional[str]) -> PrerequisiteCheck:
    directory = os.path.dirname(log_path) if log_path else ""
    if log_error:
        return PrerequisiteCheck(
            name="Log location", detected=f"{directory} ({log_error})",
            expected="writable", verdict=Verdict.FAIL,
            remedy=(
                "GramTrans could not write its log. Check that your Windows "
                f"profile folder is available and not full:\n{directory}"
            ),
        )
    return PrerequisiteCheck(
        name="Log location", detected=directory or "(not started)",
        expected="writable",
        verdict=Verdict.PASS if directory else Verdict.UNKNOWN,
    )


def run_checks(log_path: str = "", log_error: Optional[str] = None,
               generated_at: Optional[str] = None) -> PrerequisiteReport:
    """Run every check, in the order they are rendered.

    Safe to call before anything else: this is the one thing that must work on
    a machine where nothing else does.
    """
    import datetime

    checks: List[PrerequisiteCheck] = [_check_ui_toolkit()]
    checks.extend(_fieldworks_checks())
    checks.append(_check_components())
    checks.append(_check_log_location(log_path, log_error))

    return PrerequisiteReport(
        checks=checks,
        app_version=_app_version(),
        generated_at=generated_at or datetime.datetime.now().strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        log_path=log_path,
    )
