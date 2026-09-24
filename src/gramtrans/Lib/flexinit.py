"""Process-wide FieldWorks / SLDR initialisation discipline.

WHY THIS MODULE EXISTS -- a measured, destructive defect
=======================================================

`flexicon.FLExInitialize()` initialises three things: the FieldWorks registry
helper, ICU, and the **SLDR** (SIL Locale Data Repository) via
`Sldr.Initialize(True)`. `flexicon.FLExCleanup()` calls `Sldr.Cleanup()`, which
tears the SLDR down again **process-wide**.

Both are global, and that is the trap. Every standalone entry point in this repo
used to guard its initialisation with a module-level boolean latch::

    _FLEX_INITIALIZED = False

    def _ensure_flex_initialized():
        global _FLEX_INITIALIZED
        if _FLEX_INITIALIZED:
            return
        FLExInitialize()
        _FLEX_INITIALIZED = True

The latch records that *we* called `FLExInitialize()` -- it does NOT track
whether the SLDR is still up. So this sequence, all inside ONE process, leaves
the SLDR down with no way back:

1. something calls `FLExInitialize()`               -> SLDR up, latch True
2. a `HostSession.release()` / teardown calls
   `FLExCleanup()`                                  -> SLDR **down**, latch still True
3. a later `OpenProject(...)` runs                   -> latch short-circuits, no re-init

Verified live on this machine::

    before init : False
    after  init : True
    after clean : False

WHAT IT COSTS: opening a FieldWorks project with the SLDR down does not raise a
clean error. LibLCM's LDML-in-folder writing-system repository fails to parse
**every** file in `WritingSystemStore/`, declares each one bad, and RENAMES it::

    (8/19/2026 3:41:58 PM UTC)
    Encountered a bad LDML file in a writing system repository.
    Exception: The SLDR has not been initialized.
    Moved ...\\Esperanto\\WritingSystemStore\\en.ldml to en.ldml.bad

Once `en.ldml` is gone the project has no English writing system, and the next
consumer reports the user-visible symptom: *"Can't add EN writing system"*.

This is silent corpus damage, and a **read-only** open is enough to cause it --
`writeEnabled=False` protects the `.fwdata`, not the writing-system store. It hit
`Esperanto` (8 files quarantined in one day), which this repo documents as
read-only in the strong sense.

THE RULE: never trust a latch for the SLDR. `Sldr.IsInitialized` is the only
authority, it is cheap to read, and it must be re-checked before EVERY project
open -- an arbitrary amount of unrelated code (including another feature's
teardown) may have run in between.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

#: Latch for the parts of `FLExInitialize()` that are genuinely once-per-process
#: (registry helper, ICU). Deliberately NOT used to gate the SLDR check below --
#: that is the whole bug this module exists to prevent.
_FLEX_INITIALIZED = False


def ensure_flex_initialized() -> None:
    """Make the FieldWorks libraries AND the SLDR ready for an `OpenProject`.

    Call this immediately before every project open in a non-FlexTools-host
    process. Idempotent and cheap: the one-time initialisation runs once, and
    the SLDR state is re-verified on every call because `FLExCleanup()` anywhere
    in the process invalidates it (see the module docstring).

    Skipping the one-time half surfaces as `RegistryHelper.get_CompanyKey()`
    throwing `ArgumentNullException` on the first open. Skipping the SLDR half
    silently quarantines the project's LDML writing-system files.
    """
    global _FLEX_INITIALIZED
    if not _FLEX_INITIALIZED:
        # Function-level import: nothing here may touch FieldWorks at import
        # time (see Lib/census.py's module docstring on what an unconditional
        # `FLExInitialize()` at import time does to a test session).
        from flexicon import FLExInitialize  # noqa: PLC0415

        FLExInitialize()
        _FLEX_INITIALIZED = True
    ensure_sldr_initialized()


def ensure_sldr_initialized() -> bool:
    """Re-initialise the SLDR if it is down. Returns True when it is up after.

    Separate from `ensure_flex_initialized` so a caller that knows the host
    already initialised FieldWorks (the FlexTools add-on path) can still defend
    the writing-system store without re-running registry/ICU setup.

    Fail-soft on purpose: a host without FieldWorks, or a `SIL.WritingSystems`
    that does not expose `IsInitialized`, must not turn a project open into a
    crash. It logs and returns False instead -- the open then behaves exactly as
    it did before this module existed.
    """
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        _log.debug("ensure_sldr_initialized: SIL.WritingSystems absent (%s)", exc)
        return False

    try:
        if Sldr.IsInitialized:
            return True
    except Exception as exc:  # noqa: BLE001
        _log.debug("ensure_sldr_initialized: IsInitialized unreadable (%s)", exc)

    try:
        # Offline mode (True): there is no reason for a transfer or a census to
        # reach the network, and the online path is what makes initialisation
        # slow and flaky.
        Sldr.Initialize(True)
    except Exception as exc:  # noqa: BLE001
        # Already-initialised races land here harmlessly; a genuine failure is
        # worth a warning because the next open may quarantine LDML files.
        _log.warning(
            "ensure_sldr_initialized: Sldr.Initialize(True) raised (%s) -- a "
            "project open with the SLDR down can rename WritingSystemStore "
            "*.ldml files to *.ldml.bad",
            exc,
        )

    try:
        return bool(Sldr.IsInitialized)
    except Exception:  # noqa: BLE001
        return False
