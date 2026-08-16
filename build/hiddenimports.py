"""Generate PyInstaller `hiddenimports` for the flat-import convention (research R6).

`gramtrans.py` puts `Lib/` and `Lib/ui/` on `sys.path` with `site.addsitedir`,
so 31 modules under `src/` import each other by **flat top-level name**
(`preview`, `selection_wizard`, ...) and carry `if __package__:` dual-mode
guards that depend on it. PyInstaller's static analysis cannot follow
`addsitedir`, so every one of those flat names has to be declared or the frozen
bundle raises `ModuleNotFoundError` on the first real import.

FR-018 forbids refactoring the imports away, and rightly — 31 files, all
working. Packaging absorbs the convention instead.

**Generated, never hand-listed.** A hand-maintained list rots the first time
someone adds a helper module, and rots *silently*: the build succeeds and the
failure surfaces at runtime on a user's machine. Globbing means a new module
needs no build-file edit.

Each module is emitted under **both** names — flat (`preview`) and package
(`gramtrans.Lib.preview`) — because the dual-mode guards use the flat branch
under `addsitedir` and the package branch elsewhere, and both branches exist in
the frozen code.

The flat namespace claims some very generic top-level names: `api`, `models`,
`report`, `selection`, `texts`, `preview`, `transfer`, ... None collide today,
but a future dependency shipping a top-level `models` would shadow ours inside
the bundle and the symptom would be a bizarre runtime error far from the cause.
:func:`check_collisions` is the cheap insurance, run at build time.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List, Set

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parent
LIB_DIR = REPO_ROOT / "src" / "gramtrans" / "Lib"

#: Distributions we deliberately do not scan for collisions -- ours.
_OURS = {"gramtrans", "pyflexicon"}


def _module_paths() -> List[Path]:
    return [
        p for p in sorted(LIB_DIR.rglob("*.py"))
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    ]


def flat_names() -> List[str]:
    """Top-level names, as `addsitedir` would expose them.

    Both `Lib/` and `Lib/ui/` go on `sys.path`, so a module in either directory
    is importable by its bare stem — `preview` and `selection_wizard` alike.
    """
    return sorted({p.stem for p in _module_paths()})


def package_names() -> List[str]:
    """Dotted names, as `gramtrans.Lib.…` / `gramtrans.Lib.ui.…`."""
    names = set()
    for p in _module_paths():
        rel = p.relative_to(REPO_ROOT / "src").with_suffix("")
        names.add(".".join(rel.parts))
    # The packages themselves, so their `__init__` is collected.
    names.update({"gramtrans", "gramtrans.Lib", "gramtrans.Lib.ui",
                  "gramtrans.standalone"})
    return sorted(names)


def hidden_imports() -> List[str]:
    """Everything the `.spec` should declare."""
    return sorted(set(flat_names()) | set(package_names()))


# ---------------------------------------------------------------------------
# Collision check
# ---------------------------------------------------------------------------

def _third_party_top_levels(site_packages: Path) -> Set[str]:
    """Top-level module names provided by everything installed alongside us.

    Read from the filesystem rather than `importlib.metadata`, because the
    question is "what name would win an import inside the bundle", and that is
    decided by what is on the path, not by what a distribution declares.
    """
    found: Set[str] = set()
    if not site_packages.is_dir():
        return found
    for entry in site_packages.iterdir():
        name = entry.name
        if name.startswith((".", "_")) or name in {"__pycache__"}:
            continue
        if entry.is_dir() and (entry / "__init__.py").is_file():
            found.add(name)
        elif entry.suffix == ".py":
            found.add(entry.stem)
        elif entry.suffix == ".pyd":
            found.add(name.split(".")[0])
    return {n for n in found if n.lower() not in _OURS}


def check_collisions(site_packages: Path = None) -> List[str]:
    """Flat names that a bundled third-party distribution would shadow.

    Returns the offending names. An empty list is the pass condition; the
    build treats a non-empty one as fatal, because the alternative is shipping
    a bundle in which `import api` silently resolves to somebody else's.
    """
    if site_packages is None:
        site_packages = Path(sys.prefix) / "Lib" / "site-packages"
    third_party = _third_party_top_levels(Path(site_packages))
    return sorted(set(flat_names()) & third_party)


def _stdlib_collisions() -> List[str]:
    """Flat names that shadow a *standard library* module.

    Separated from the third-party check because the remedy differs: a stdlib
    clash is our own naming problem and cannot be fixed by pinning.
    """
    return sorted(set(flat_names()) & set(getattr(sys, "stdlib_module_names", set())))


def main(argv: Iterable[str] = ()) -> int:
    flat = flat_names()
    pkg = package_names()
    print(f"[INFO] {len(flat)} flat name(s), {len(pkg)} package name(s) "
          f"-> {len(hidden_imports())} hiddenimports")
    for name in flat:
        print(f"         flat: {name}")

    stdlib = _stdlib_collisions()
    if stdlib:
        print(f"[WARN] flat names that shadow the standard library: {stdlib}")

    collisions = check_collisions()
    if collisions:
        print("[FAIL] flat-name collision with a bundled distribution:")
        for name in collisions:
            print(f"         {name}")
        print("       Inside the frozen bundle one of these would shadow ours "
              "and the symptom would be a runtime error far from the cause. "
              "Rename ours, or drop the colliding dependency.")
        return 1
    print("[PASS] no flat-name collision with any bundled distribution.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
