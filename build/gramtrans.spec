# -*- mode: python ; coding: utf-8 -*-
"""The single packaging definition (FR-046).

Exactly **one** `Analysis`, feeding both a `COLLECT` (onedir, which Inno Setup
wraps into the supported installer) and a onefile `EXE` (the best-effort
portable). One Analysis is the requirement, not a convenience: two would let
the two artifacts drift in content, and a divergence between them is a defect
by definition — the smoke test would then be testing two different programs.

Build through `build\\build.py`, never by invoking PyInstaller directly. The
orchestrator creates the throwaway venv, installs from the hash-pinned lock
with no fallback, and stamps `_buildinfo.py` — none of which a bare
`pyinstaller` run does.

Targets are selected with `--` arguments from `build.py`:

    pyinstaller gramtrans.spec -- --onedir
    pyinstaller gramtrans.spec -- --onefile
    pyinstaller gramtrans.spec              # both
"""
import os
import sys
from pathlib import Path

# `__file__` is not defined when PyInstaller execs a spec, but SPECPATH is.
BUILD_DIR = Path(SPECPATH).resolve()          # noqa: F821 — PyInstaller global
REPO_ROOT = BUILD_DIR.parent
SRC = REPO_ROOT / "src"

sys.path.insert(0, str(BUILD_DIR))
import hiddenimports as _hi  # noqa: E402

# Fail the build rather than ship a bundle in which `import api` might resolve
# to somebody else's module (research R6).
_collisions = _hi.check_collisions()
if _collisions:
    raise SystemExit(
        "[FAIL] flat-name collision with a bundled distribution: "
        f"{_collisions}. See build/hiddenimports.py."
    )

HIDDEN = _hi.hidden_imports()

# Distribution metadata (`*.dist-info`) must be collected explicitly.
# PyInstaller does not ship it by default, and without it
# `importlib.metadata.version("pyflexicon")` raises `PackageNotFoundError`
# inside the bundle -- which the first real build turned into a self-check
# reporting "Bundled components: none found" on a perfectly good artifact.
# Exactly the class of false negative FR-036 exists to prevent, and it is only
# visible in a frozen build, which is why the smoke test asserts it (check 6).
from PyInstaller.utils.hooks import copy_metadata  # noqa: E402

METADATA = []
for _dist in ("pyflexicon", "PyQt6", "PyQt6-Qt6", "pyqt6-sip", "pythonnet",
              "clr-loader", "cffi", "pycparser", "flextoolslib", "flexlibs",
              "cdfutils"):
    try:
        METADATA += copy_metadata(_dist)
    except Exception as _exc:  # noqa: BLE001
        # Not fatal here: the smoke test is what decides whether a missing
        # component blocks the release. Failing the freeze on a metadata
        # lookup would hide the more useful, more specific smoke failure.
        print(f"[WARN] no metadata collected for {_dist}: {_exc}")

# Which targets to emit. Parsed from PyInstaller's post-`--` argv so one spec
# serves all three invocations without duplicating the Analysis.
_args = sys.argv[1:]
_want_onedir = "--onefile" not in _args
_want_onefile = "--onedir" not in _args

APP_NAME = "GramTrans"

a = Analysis(                                  # noqa: F821
    [str(SRC / "gramtrans" / "standalone" / "__main__.py")],
    pathex=[str(SRC), str(SRC / "gramtrans" / "Lib"),
            str(SRC / "gramtrans" / "Lib" / "ui")],
    binaries=[],
    datas=METADATA,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(BUILD_DIR / "rthook_isolate.py")],
    # Nothing is excluded. The temptation is to strip tkinter and friends for
    # size, but the bundle is ~25 MB before PyQt6 and an over-eager exclude
    # that breaks a transitive import surfaces on a user's machine, not here.
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)                              # noqa: F821

if _want_onedir:
    exe_onedir = EXE(                          # noqa: F821
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,          # UPX-packed binaries trip antivirus heuristics,
                            # and the artifact is already unsigned (FR-051).
        console=False,      # A GUI application. `--self-check` still writes to
                            # stdout when a console is attached, and always to
                            # its own window (research R12).
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(                            # noqa: F821
        exe_onedir,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )

if _want_onefile:
    exe_onefile = EXE(                         # noqa: F821
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=f"{APP_NAME}-portable",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
