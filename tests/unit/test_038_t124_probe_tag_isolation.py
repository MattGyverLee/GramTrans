"""Feature 038 T124 -- offline unit test for the probe-output tag leak.

`debug/run038_t124_recensus.py` writes two families of probe artifacts under
`probes/<tag>/`: the Wave 1 owner probe (`_probe_path`, e.g.
`owner-probe-GT038-T124-Ngoreme.json`) and the T124 supplements file
(`t124-supplements-<source>.json`), both built from what used to be a
module-level constant `_PROBE_OUT = _MAIN / "probes" / "t124"` frozen at
import time. `RUN_TAG` is set later, from argv, inside `main()` -- so a
`--tag smoke` run still wrote both files into `probes/t124/`, the exact
directory the tag exists to protect. This is the residue the driver's own
`# TAGGED TOO` comment (on `recensus-038-<tag>-<pair>.json`) already records
having happened once before, on a *different* output path.

`_PROBE_OUT` is now a function, `_probe_out_dir()`, that reads the current
`RUN_TAG` at call time. These tests lock that: the default tag reproduces
the historical path unchanged, and a non-default tag lands somewhere else
entirely.

No FLEx/LCM import happens at module import time -- every `SIL.LCModel`
import in the driver is local to a function -- so this test runs with no
project open and no `FLExInitialize` call.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEBUG = _ROOT / "debug"
if str(_DEBUG) not in sys.path:
    sys.path.insert(0, str(_DEBUG))

import run038_t124_recensus as recensus  # noqa: E402


def _restore_default_tag():
    recensus.RUN_TAG = "t124"


def test_default_tag_keeps_the_historical_probe_directory():
    _restore_default_tag()
    assert recensus._probe_out_dir() == recensus._MAIN / "probes" / "t124"


def test_a_non_default_tag_yields_a_distinct_probe_directory():
    _restore_default_tag()
    default_dir = recensus._probe_out_dir()
    try:
        recensus.RUN_TAG = "smoke"
        tagged_dir = recensus._probe_out_dir()
        assert tagged_dir != default_dir
        assert tagged_dir == recensus._MAIN / "probes" / "smoke"
    finally:
        _restore_default_tag()


def test_the_owner_probe_filename_is_isolated_by_tag():
    """`_probe_path` (the owner-probe artifact) must move with the tag too.

    This is the file whose default-tag counterpart
    (`probes/t124/owner-probe-GT038-T124-Ngoreme.json`) is committed on
    `main` as a pinned comparand -- the one a leaking tag can silently
    overwrite.
    """
    _restore_default_tag()
    default_path = recensus._probe_path("GT038 T124 Ngoreme")
    try:
        recensus.RUN_TAG = "smoke"
        tagged_path = recensus._probe_path("GT038 T124 Ngoreme")
        assert tagged_path != default_path
        assert tagged_path.name == default_path.name  # same filename
        assert tagged_path.parent == recensus._MAIN / "probes" / "smoke"
        assert default_path.parent == recensus._MAIN / "probes" / "t124"
    finally:
        _restore_default_tag()


def test_the_supplements_filename_directory_is_isolated_by_tag():
    """`t124-supplements-<source>.json` is built directly off `_probe_out_dir()`
    inline in `_run_pair`; this pins the directory half of that construction,
    which is the half that leaked.
    """
    _restore_default_tag()
    default_dir = recensus._probe_out_dir()
    try:
        recensus.RUN_TAG = "smoke"
        tagged_dir = recensus._probe_out_dir()
        default_supp = default_dir / "t124-supplements-Ngoreme-FLEx.json"
        tagged_supp = tagged_dir / "t124-supplements-Ngoreme-FLEx.json"
        assert tagged_supp != default_supp
        assert tagged_supp.parent != default_supp.parent
    finally:
        _restore_default_tag()
