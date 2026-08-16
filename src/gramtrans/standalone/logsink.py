"""The report sink the standalone hands `MainFunction` (FR-008, FR-038).

FlexTools supplies an object with exactly four methods — `Info`, `Warning`,
`Error`, `Blank` — and the engine writes its whole narrative through them.
This is that object for the other host, teeing every call to two places:

* the in-app log view (FR-009/FR-010), so the user can watch the run and copy
  the result out afterwards;
* `%LOCALAPPDATA%\\GramTrans\\logs\\gramtrans-<run_id>.log`, retained across
  runs (FR-038), so a support request has something to attach.

The filename carries the **run_id**, which is the same `GT-<YYYYmmdd-HHMMSS>`
string as the run's Import Residue tag (research R11). That is what makes
FR-026's partial-failure instruction one step instead of two: the log the user
is looking at is named after the tag they need to search for in FLEx.

FR-039 (no project content beyond what identifies the objects in the run) is a
constraint on what the *engine* emits, not something this sink filters — it
writes the report stream verbatim, because a sink that silently dropped lines
would make the log lie about the run. See T053.
"""
from __future__ import annotations

import datetime
import os
from typing import Callable, List, Optional

__all__ = ["make_run_id", "default_log_dir", "LogSink"]


def make_run_id(now: Optional[datetime.datetime] = None) -> "tuple[str, str]":
    """`(run_id, started_at)` in the engine's existing formats.

    Deliberately the same shapes `gramtrans._make_run_id` produces, so the
    log filename, the Import Residue tag and the report header all agree.
    """
    now = now or datetime.datetime.now()
    return "GT-" + now.strftime("%Y%m%d-%H%M%S"), now.strftime("%Y-%m-%dT%H:%M:%S")


def default_log_dir() -> str:
    """`%LOCALAPPDATA%\\GramTrans\\logs`, or a sane fallback.

    `%LOCALAPPDATA%` needs no elevation and survives the uninstaller (R11).
    The fallback keeps a developer run working on a machine where the variable
    is unset rather than failing at startup over a log directory.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "GramTrans", "logs")


class LogSink:
    """A FlexTools-shaped report sink that tees to a view and a file.

    Exposes **exactly** the four methods FlexTools supplies. Extra methods
    would be a place for the shell and the engine to grow a private channel,
    which is the coupling FR-015 exists to prevent.
    """

    def __init__(
        self,
        run_id: str,
        log_dir: Optional[str] = None,
        view_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.run_id = run_id
        self._log_dir = log_dir or default_log_dir()
        self.log_path = os.path.join(self._log_dir, f"gramtrans-{run_id}.log")
        self._view_callback = view_callback
        self._lines: List[str] = []
        self._handle = None
        self._file_error: Optional[str] = None
        self._open_file()

    # -- lifecycle ---------------------------------------------------------

    def _open_file(self) -> None:
        """Create the directory on demand and open the run's log.

        A log we cannot write is recorded and reported, never fatal: refusing
        to run a transfer because a log file could not be created would be a
        worse outcome than running without one. `file_error` surfaces in the
        self-check's "Log location" check, so the failure is still visible.
        """
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            # SIM115 does not apply: the log is open for the lifetime of the
            # run, written to from many call sites, and closed by `close()`.
            # A context manager here would close it before the first line.
            self._handle = open(  # noqa: SIM115
                self.log_path, "a", encoding="utf-8", buffering=1
            )
        except OSError as exc:
            self._handle = None
            self._file_error = f"{type(exc).__name__}: {exc}"

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._handle.flush()
                self._handle.close()
            except OSError:
                pass
            finally:
                self._handle = None

    def __enter__(self) -> "LogSink":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- the FlexTools sink protocol --------------------------------------

    def Info(self, msg: str = "") -> None:  # noqa: N802 — host-mandated name
        self._emit("INFO", msg)

    def Warning(self, msg: str = "") -> None:  # noqa: N802
        self._emit("WARN", msg)

    def Error(self, msg: str = "") -> None:  # noqa: N802
        self._emit("ERROR", msg)

    def Blank(self) -> None:  # noqa: N802
        self._emit("", "")

    # -- internals ---------------------------------------------------------

    def _emit(self, level: str, msg: str) -> None:
        line = f"[{level}] {msg}" if level else ""
        self._lines.append(line)
        if self._handle is not None:
            try:
                self._handle.write(line + "\n")
            except OSError as exc:
                # Stop trying, record why, keep the run going. Losing the log
                # mid-run must not take the transfer down with it.
                self._file_error = f"{type(exc).__name__}: {exc}"
                self.close()
        if self._view_callback is not None:
            # Left as an explicit try/except rather than contextlib.suppress so
            # the reason for swallowing is readable at the swallow site.
            try:  # noqa: SIM105
                self._view_callback(level, msg)
            except Exception:  # noqa: BLE001
                # A view that raises must not abort a run in progress; the
                # file copy is the one that has to survive.
                pass

    # -- what the view and the self-check read ----------------------------

    @property
    def file_error(self) -> Optional[str]:
        """Why the log file is not being written, or `None` if it is."""
        return self._file_error

    @property
    def writable(self) -> bool:
        return self._handle is not None

    def lines(self) -> List[str]:
        """Everything emitted so far, for the in-app view and Save/Copy."""
        return list(self._lines)

    def text(self) -> str:
        return "\n".join(self._lines)

    def attach_view(self, view_callback: Callable[[str, str], None]) -> None:
        """Point the sink at a view after construction.

        The sink has to exist before the window does — prerequisite failures
        are logged before there is anywhere to show them — so the view is
        wired up afterwards and replays what it missed.
        """
        self._view_callback = view_callback
