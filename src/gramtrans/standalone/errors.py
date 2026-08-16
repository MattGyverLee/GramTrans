"""Plain-language messages for every way the standalone can refuse to run.

`contracts/cli-and-selfcheck.md` §3. Under FlexTools a failure lands in a
report pane a technical user is already reading. This host's users may have
never installed a developer tool in their lives, so every failure here is a
sentence that says what happened and what to do about it — never a traceback,
and always naming the log file so a support request can start with something
concrete.

The messages live in one module, separate from the code that raises them,
for two reasons:

* **The FR-031 / FR-033 split is a correctness property, not a wording
  preference.** "FieldWorks is not installed" and "the language-model runtime
  did not start" send the user to completely different places, and getting
  them the wrong way round on a healthy machine is the specific harm
  `standalone/fwglobals.py` exists to prevent. Keeping both texts adjacent
  makes the distinction visible rather than scattered across raise sites.
* Tests can assert on the text without constructing the failure.

Nothing here imports PyQt6 or flexicon: a message about a missing prerequisite
has to be renderable on the machine that is missing it.
"""
from __future__ import annotations

from typing import Optional

__all__ = [
    "log_file_line",
    "fieldworks_not_installed",
    "unsupported_fieldworks_version",
    "runtime_failed_to_start",
    "target_locked",
    "project_cannot_be_opened",
    "migration_required",
    "same_project",
    "no_projects_found",
    "describe_startup_failure",
]


def log_file_line(log_path: str) -> str:
    """The trailing line every message carries (FR-038).

    One phrasing, used everywhere, so a user learns where to look once.
    """
    return f"\n\nFull details are in the log file:\n{log_path}"


def _with_log(body: str, log_path: Optional[str]) -> str:
    return body + (log_file_line(log_path) if log_path else "")


# ---------------------------------------------------------------------------
# Prerequisites (FR-031 .. FR-033)
# ---------------------------------------------------------------------------

def fieldworks_not_installed(log_path: Optional[str] = None) -> str:
    """FR-031. Reached only when `import flexicon` fails.

    Never used for a value that reads back empty after a successful import —
    that is :func:`runtime_failed_to_start`. Telling someone with a working
    FieldWorks to install FieldWorks is the worst outcome this module can
    produce, so the two are kept deliberately far apart in wording as well as
    in code.
    """
    return _with_log(
        "GramTrans needs FieldWorks 9, which does not appear to be installed "
        "on this computer.\n\n"
        "Install FieldWorks 9 and run GramTrans again. If FieldWorks 9 is "
        "already installed, it may have been installed for a different Windows "
        "user account; try running GramTrans from the account that installed "
        "it.",
        log_path,
    )


def unsupported_fieldworks_version(
    detected: str, supported, log_path: Optional[str] = None
) -> str:
    """FR-032. Reports flexicon's supported range rather than defining one."""
    if isinstance(supported, str):
        supported_text = supported
    else:
        versions = [str(v) for v in supported]
        supported_text = " or ".join(versions) if versions else "9"
    return _with_log(
        f"This computer has FieldWorks {detected}.\n\n"
        f"GramTrans supports FieldWorks {supported_text}. It cannot run "
        "against this version.",
        log_path,
    )


def runtime_failed_to_start(
    component: str, detail: str = "", log_path: Optional[str] = None
) -> str:
    """FR-033. Names the component and points at the self-check.

    The user cannot act on "pythonnet raised"; they can act on "send us the
    self-check". So the message routes them there rather than describing the
    internals.
    """
    body = (
        "GramTrans found FieldWorks on this computer, but could not start the "
        f"language-model runtime it needs.\n\nThe component that failed was: "
        f"{component}."
    )
    if detail:
        body += f"\n{detail}"
    body += (
        "\n\nChoose Help -> Self-check... to produce a diagnostic report, and "
        "send it with the log file when you ask for help."
    )
    return _with_log(body, log_path)


# ---------------------------------------------------------------------------
# Projects (FR-029, FR-034, FR-035, FR-028)
# ---------------------------------------------------------------------------

def target_locked(project_name: str, log_path: Optional[str] = None) -> str:
    """FR-029. Names *which* project, and never shows raw `TargetUnavailable`.

    The FR-030 restatement is deliberate: this is the moment the user finds
    out, and "but I only ran a Preview" is the objection the sentence answers.
    """
    return _with_log(
        f"GramTrans could not open the target project {project_name!r} because "
        "something else is using it.\n\n"
        f"Close {project_name!r} in FieldWorks Language Explorer and try again. "
        "The target must be closed even for a Preview.",
        log_path,
    )


def project_cannot_be_opened(
    project_name: str, reason: str = "", log_path: Optional[str] = None
) -> str:
    """FR-034. Attributed to that project by name; the rest stay usable."""
    body = f"GramTrans could not open the project {project_name!r}."
    if reason:
        body += f"\n\nReason: {reason}"
    body += (
        "\n\nThe other projects in the list are unaffected and can still be "
        "chosen."
    )
    return _with_log(body, log_path)


def migration_required(project_name: str, log_path: Optional[str] = None) -> str:
    """FR-035. Told *before* anything proceeds; we never migrate as a side effect.

    Raised by flexicon as `FP_MigrationRequired`, caught by type. Migrating
    someone's project because they opened a transfer tool would be a
    substantial, irreversible change made without asking.
    """
    return _with_log(
        f"The project {project_name!r} was made with an older version of "
        "FieldWorks and needs to be updated before it can be used.\n\n"
        "Open it in FieldWorks Language Explorer first and let FieldWorks "
        "perform the update, then run GramTrans again. GramTrans will not "
        "update the project for you.",
        log_path,
    )


def same_project(project_name: str, log_path: Optional[str] = None) -> str:
    """FR-028. Rendered instead of letting `SameProjectError` surface raw."""
    return _with_log(
        f"The source and the target are the same project ({project_name!r}).\n\n"
        "GramTrans copies grammar from one project into another, so it needs "
        "two different projects. Choose a different target.",
        log_path,
    )


def no_projects_found(projects_root: str, log_path: Optional[str] = None) -> str:
    """An empty list gets a message, not an empty dialog (FR-034 neighbour)."""
    return _with_log(
        "GramTrans did not find any FieldWorks projects on this computer.\n\n"
        f"It looked in:\n{projects_root}\n\n"
        "Create or restore a project in FieldWorks Language Explorer first.",
        log_path,
    )


# ---------------------------------------------------------------------------
# The mapper
# ---------------------------------------------------------------------------

def describe_startup_failure(exc: BaseException, log_path: Optional[str] = None) -> str:
    """Map a startup exception onto the right message, by **type**.

    By type, not by string matching: the FR-031/FR-033 distinction is exactly
    the one a substring check would get wrong, and getting it wrong is the
    failure `fwglobals` was written to prevent. Anything unrecognised falls
    through to FR-033, which is the honest answer for "something went wrong
    inside the runtime" — never FR-031, which is a claim about the user's
    machine that we would have no evidence for.
    """
    from gramtrans.standalone.fwglobals import (
        FieldWorksNotDetected,
        FieldWorksRuntimeUnavailable,
    )

    if isinstance(exc, FieldWorksNotDetected):
        return fieldworks_not_installed(log_path)
    if isinstance(exc, FieldWorksRuntimeUnavailable):
        return runtime_failed_to_start("FieldWorks language model", str(exc), log_path)
    return runtime_failed_to_start(
        type(exc).__name__, str(exc), log_path
    )
