"""The **sole** reader of flexicon's FieldWorks globals (T012, research R1).

No other module in this repository may name ``FWCodeDir``, ``FWProjectsDir``,
``FWExecutable``, ``FWShortVersion``, ``FWLongVersion`` or
``FW_SUPPORTED_VERSIONS``. ``tests/unit/test_034_fwglobals_only.py`` AST-scans
``src/gramtrans/`` and ``build/`` and fails the regression gate on any other
reader, so this is a rule the build enforces rather than one reviewers
remember.

Verified behaviour of flexicon 4.3.1 (measured on this machine, 2026-08-17)
-------------------------------------------------------------------------
Research R1 predicted that ``flexicon.FWCodeDir`` and friends would be ``None``
forever, because ``FLExGlobals.py`` binds them to ``None`` at line 37 and
``InitialiseFWGlobals()`` rebinds only the *module* globals. **That is not what
4.3.1 does**, and the difference matters:

* ``FLExInit.py`` calls ``FLExGlobals.InitialiseFWGlobals()`` at **module
  scope** (line 44, indentation 0) — it runs on ``import``, not on
  ``FLExInitialize()``.
* ``flexicon/__init__.py`` imports ``.code.FLExInit`` *before*
  ``.code.FLExGlobals``, so by the time the re-exports are bound the globals
  are already populated. Measured: ``flexicon.FWCodeDir is
  flexicon.code.FLExGlobals.FWCodeDir`` -> ``True``, both
  ``'C:\\Program Files\\SIL\\FieldWorks 9\\'``, *before* ``FLExInitialize()``.
* ``InitialiseFWGlobals()`` **raises** when the registry key is absent or
  ``FieldWorks.exe`` is missing, and nothing guards the call. So on a machine
  without FieldWorks, ``import flexicon`` itself fails. ``FLExInitialize()`` is
  never reached, and cannot be the thing that detects FR-031.

Two consequences the rest of the shell depends on:

1. **FieldWorks-missing (FR-031) is an import-time failure.** :func:`probe`
   wraps the import, not the initialise. The contract's startup order still
   holds — UI toolkit, then flexicon, then reads — but step 2's failure surface
   is ``import flexicon``.
2. **The re-exports are snapshots, not live reads.** They happen to be correct
   today because nothing re-runs ``InitialiseFWGlobals()``. Reading the module
   attribute at call time, as this module does, is correct under both the
   observed behaviour and R1's predicted behaviour — which is why the discipline
   is worth keeping even though the specific trap turned out not to exist.

A ``None`` where a value is expected therefore means something genuinely
unexpected happened, and :class:`FieldWorksRuntimeUnavailable` says so. It maps
to the FR-033 "language-model runtime failed to initialise" message and
**never** to the FR-031 "FieldWorks is not installed" message: a bug in this
module must not turn into a lie about the user's machine.
"""
from __future__ import annotations

from typing import Any, List, Optional

__all__ = [
    "FieldWorksNotDetected",
    "FieldWorksRuntimeUnavailable",
    "probe",
    "mark_initialized",
    "is_initialized",
    "code_dir",
    "projects_dir",
    "executable",
    "short_version",
    "long_version",
    "supported_versions",
    "mark_uninitialized",
    "reset_for_tests",
]


class FieldWorksNotDetected(Exception):
    """No usable FieldWorks 9 install (FR-031).

    Raised by :func:`probe` when ``import flexicon`` fails, which on this
    flexicon is what a missing registry key or a missing ``FieldWorks.exe``
    produces. The shell renders the "install FieldWorks 9" message for this and
    for nothing else.
    """


class FieldWorksRuntimeUnavailable(Exception):
    """FieldWorks is present but the language-model runtime is not usable (FR-033).

    Covers ``FLExInitialize()`` failing, and any global that reads back ``None``
    or empty after initialisation. Deliberately distinct from
    :class:`FieldWorksNotDetected`: this one points the user at Help ->
    Self-check and the log file rather than telling them to install software
    they already have.
    """


# Set by `mark_initialized()`, which the shell calls immediately after a
# successful `FLExInitialize()`. Accessors refuse to read before that, so a
# caller cannot accidentally observe pre-initialisation state and report it as
# fact.
_initialized = False


def is_initialized() -> bool:
    return _initialized


def mark_initialized() -> None:
    """Record that ``flexicon.FLExInitialize()`` returned successfully."""
    global _initialized
    _initialized = True


def mark_uninitialized() -> None:
    """Clear the initialised flag.

    Called by `HostSession.release()` after `FLExCleanup()`, so a subsequent
    read cannot quietly succeed against a runtime that has been shut down, and
    by tests that need a clean slate.
    """
    global _initialized
    _initialized = False


#: Readability alias for test code, where the intent is "reset the module".
reset_for_tests = mark_uninitialized


def probe():
    """Import flexicon, mapping its failure modes onto our two typed errors.

    Returns the ``flexicon`` module. Does **not** call ``FLExInitialize()`` —
    the caller owns startup ordering (contract §6) and the distinction between
    "could not import" and "could not initialise" is exactly the FR-031 /
    FR-033 split.
    """
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001 — flexicon raises bare Exception
        raise FieldWorksNotDetected(str(exc)) from exc
    return flexicon


def _globals_module():
    """The live ``FLExGlobals`` module, post-initialisation.

    Imported here and nowhere else. Note the import is of the *module*, so
    every read below is an attribute lookup at call time rather than a name
    bound once at import — the R1 discipline, kept for the reason in the
    module docstring even though 4.3.1's re-exports happen to be correct.
    """
    if not _initialized:
        raise FieldWorksRuntimeUnavailable(
            "FieldWorks globals were read before FLExInitialize() completed. "
            "This is a startup-ordering bug in GramTrans, not a problem with "
            "the FieldWorks installation."
        )
    try:
        import flexicon.code.FLExGlobals as flex_globals
    except Exception as exc:  # noqa: BLE001
        raise FieldWorksRuntimeUnavailable(
            f"flexicon.code.FLExGlobals is not importable: {exc}"
        ) from exc
    return flex_globals


def _read(name: str) -> Any:
    value = getattr(_globals_module(), name, None)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise FieldWorksRuntimeUnavailable(
            f"FieldWorks reported no value for {name} after initialisation. "
            "The FieldWorks installation was found but the language-model "
            "runtime did not come up completely."
        )
    return value


def code_dir() -> str:
    """The FieldWorks code directory (contains ``FieldWorks.exe``)."""
    return str(_read("FWCodeDir"))


def projects_dir() -> str:
    """Where FieldWorks itself records that projects live (FR-001).

    This is what the shell injects into ``api.initialize_run(projects_root=...)``
    so a relocated projects directory is honoured instead of the hard-coded
    ``C:\\ProgramData\\SIL\\FieldWorks\\Projects`` default.
    """
    return str(_read("FWProjectsDir"))


def executable() -> str:
    return str(_read("FWExecutable"))


def short_version() -> str:
    """e.g. ``"9.3.10.1448"``.

    flexicon stores a CLR ``System.Version`` here, not a ``str``; stringifying
    at the boundary keeps every consumer on plain Python types.
    """
    return str(_read("FWShortVersion"))


def long_version() -> str:
    """e.g. ``"Version: 9.3.10.1448   2026-07-09  (64 bit)"``."""
    return str(_read("FWLongVersion"))


def supported_versions() -> List[str]:
    """The major versions flexicon will talk to — ``["9"]`` today (FR-032).

    Reported, never redefined: the supported range is flexicon's fact about
    itself, and a copy here would drift the moment flexicon grew FieldWorks 10
    support.
    """
    value = _read("FW_SUPPORTED_VERSIONS")
    return [str(v) for v in value]


def major_version() -> Optional[str]:
    """The leading component of :func:`short_version`, for the FR-032 check."""
    text = short_version()
    head = text.split(".", 1)[0].strip()
    return head or None
