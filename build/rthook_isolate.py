"""PyInstaller runtime hook: isolate the bundle from any host Python (FR-043, SC-009).

Runs before **any** application import. Two jobs:

1. Scrub `PYTHONPATH`, `PYTHONHOME` and `PYTHONSTARTUP` from `os.environ`.
2. Assert `sys.prefix` resolves inside the bundle.

PyInstaller's bootloader already sets `Py_IgnoreEnvironmentFlag`, so this is
belt and braces. It earns its place because of *which* failure it guards
against: the flat-import convention (research R6) claims generic top-level
names — `api`, `models`, `report`, `preview`, `selection` — and a stray
`PYTHONPATH` on a linguist's machine (left by an old FLExTools install, a
Python course, an ArcGIS install) could put a different `models.py` ahead of
ours. The symptom would be an inexplicable error deep inside a transfer, with
nothing on screen connecting it to an environment variable the user does not
know exists.

`PYTHONSTARTUP` is scrubbed for a different reason: it names a script that
would otherwise execute inside a process that is about to open and write to
the user's language data.

A failure here is a clear message, not a traceback — this runs before the
application's own error handling exists, so it has to do its own.
"""
import os
import sys

_SCRUBBED = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")


def _isolate():
    removed = [name for name in _SCRUBBED if os.environ.pop(name, None) is not None]
    if removed:
        # Not an error: a set PYTHONPATH is common and harmless once removed.
        # Reported so it appears in the log when a support case turns out to
        # be environmental after all.
        print(
            "[GramTrans] Ignoring environment variable(s) from the host system: "
            + ", ".join(removed),
            file=sys.stderr,
        )

    # `sys.prefix` inside a PyInstaller bundle points at the extraction/bundle
    # directory (`_MEIPASS`). If it does not, something has substituted an
    # interpreter and the flat-name guarantees no longer hold.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        # Not frozen — the hook is being imported directly (by a test, say).
        # Nothing to assert.
        return

    prefix = os.path.normcase(os.path.abspath(sys.prefix))
    bundle = os.path.normcase(os.path.abspath(meipass))
    if not prefix.startswith(bundle) and not bundle.startswith(prefix):
        sys.stderr.write(
            "GramTrans could not start.\n\n"
            "It is running against a different Python installation than the "
            "one it ships with, which means it cannot load its own components "
            "reliably.\n\n"
            f"  expected: {bundle}\n"
            f"  found   : {prefix}\n\n"
            "This is usually caused by another program's Python settings. "
            "Restarting the computer and running GramTrans again is the "
            "simplest fix.\n"
        )
        raise SystemExit(1)


_isolate()
