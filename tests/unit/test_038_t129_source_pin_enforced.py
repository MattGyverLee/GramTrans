"""Feature 038 T129 (1) -- the harness must notice its own source pin moving.

`debug/run038_t124_recensus.py` recorded
`$.projects.source.fwdata_sha256_{before,after}` in every artifact it ever
emitted, and its module docstring asserted "Every SOURCE is on its pin. The
drift is entirely destination-side". The recorded value was never READ BACK, so
when two of the three sources did move the driver went on printing a confident
`vs T078` diff over a comparand that no longer applied -- and a
`LexEntryType SHORTFALL -> MATCHED (net 0 -> 12)` reading was relayed off that
section and then retracted. A recorded value that nothing checks is not a pin.

THESE TESTS ASSERT AGAINST THE COMMITTED ARTIFACTS, NOT AGAINST FIXTURES THEY
BUILT. That is deliberate and it is the whole difference from the failure this
spurt already recorded once -- "a pinning test that SET the value it then
asserted". The digests below were written by live census runs on dates this
file had nothing to do with; if someone re-pins a comparand or re-runs a pair,
these tests change their mind because the DATA changed, which is what makes
them capable of failing. Only the two synthetic cases at the bottom -- which
exercise the `unknown` branch, a state no committed artifact is in -- construct
their own input, and they assert the branch rather than a digest.

Offline: pure JSON reads, no FLEx/LCM import, no project opened.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DEBUG = _ROOT / "debug"
_SNAPS = _ROOT / "tests" / "integration" / "_snapshots"
if str(_DEBUG) not in sys.path:
    sys.path.insert(0, str(_DEBUG))

import run038_t124_recensus as recensus  # noqa: E402


def _artifact(name: str) -> dict:
    path = _SNAPS / name
    if not path.is_file():  # pragma: no cover - a missing comparand is a state
        pytest.skip("no committed artifact at %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The three sanctioned pairs, measured. `ejagham` is the control: if the check
# fired on everything it would be useless, and a test suite in which no case is
# expected to PASS cannot distinguish "correctly refused" from "refuses always".
# ---------------------------------------------------------------------------

def test_ejagham_source_is_still_on_its_t078_pin():
    """The control. Ejagham never moved, so its comparand stays usable."""
    pin = recensus._source_pin_status(
        _artifact("census-038-t126-ejagham.json"),
        _artifact("census-038-t078-ejagham.json"))
    assert pin["status"] == "match", pin
    assert pin["run_source_sha256"].startswith("5ad15c10")
    assert pin["run_source_sha256"] == pin["comparand_source_sha256"]


@pytest.mark.parametrize("tag", ["t126", "t123b", "t123c", "t123d", "t123e"])
def test_every_ngoreme_run_from_t126_on_is_off_the_t078_pin(tag):
    """Ngoreme moved between t124 and t126 -- THREE WEEKS before T128 noticed
    the mbugwe half, and T129 asked for this exact check rather than an
    assumption. Parametrised over every committed tag from t126 forward because
    the claim being locked is not "one run drifted" but "every `vs T078`
    reading on ngoreme since t126 crosses a source change", which is what makes
    the six "FIXED" entries relayed off those sections inadmissible.
    """
    artifact = _artifact("census-038-%s-ngoreme.json" % tag)
    pin = recensus._source_pin_status(
        artifact, _artifact("census-038-t078-ngoreme.json"))
    assert pin["status"] == "moved", pin
    assert pin["comparand_source_sha256"].startswith("838b7635")
    assert pin["run_source_sha256"].startswith("d0ab2c66")


def test_ngoreme_was_still_on_pin_at_t124_so_the_drift_is_dated():
    """t124 is the last ngoreme run that CAN cite T078, which is what turns
    "ngoreme drifted" into "ngoreme drifted between t124 and t126". A check
    that cannot date the change cannot tell anyone which readings survive.
    """
    pin = recensus._source_pin_status(
        _artifact("census-038-t124-ngoreme.json"),
        _artifact("census-038-t078-ngoreme.json"))
    assert pin["status"] == "match", pin


@pytest.mark.parametrize("tag", ["t123c", "t123d"])
def test_mbugwe_runs_after_t126_are_off_the_t078_pin(tag):
    """T128's finding, now enforced rather than recorded."""
    pin = recensus._source_pin_status(
        _artifact("census-038-%s-mbugwe.json" % tag),
        _artifact("census-038-t078-mbugwe.json"))
    assert pin["status"] == "moved", pin
    assert pin["comparand_source_sha256"].startswith("fb6aadab")
    assert pin["run_source_sha256"].startswith("3fb29a29")


def test_mbugwe_was_still_on_pin_at_t126():
    """Dates the mbugwe drift to after t126, matching T128's mtime evidence."""
    pin = recensus._source_pin_status(
        _artifact("census-038-t126-mbugwe.json"),
        _artifact("census-038-t078-mbugwe.json"))
    assert pin["status"] == "match", pin


# ---------------------------------------------------------------------------
# The `unknown` branch. No committed artifact is missing its digests, so this
# is the one place a fixture is the honest instrument rather than a shortcut.
# ---------------------------------------------------------------------------

def test_a_missing_digest_is_unknown_and_never_a_match():
    """"No evidence of drift" is not "evidence of no drift". An artifact that
    records no digest must not be silently comparable -- that reading is the
    unverifiable pin this whole row exists to stop trusting.
    """
    known = {"projects": {"source": {"fwdata_sha256_after": "a" * 64}}}
    blank = {"projects": {"source": {}}}
    assert recensus._source_pin_status(blank, known)["status"] == "unknown"
    assert recensus._source_pin_status(known, blank)["status"] == "unknown"
    assert recensus._source_pin_status(blank, blank)["status"] == "unknown"


def test_after_is_preferred_over_before():
    """A run that somehow moved its own source is compared on the digest it
    finished with, not the one it started from.
    """
    art = {"projects": {"source": {"fwdata_sha256_before": "b" * 64,
                                   "fwdata_sha256_after": "a" * 64}}}
    assert recensus._source_digest(art) == "a" * 64


def test_identical_digests_match():
    same = {"projects": {"source": {"fwdata_sha256_after": "c" * 64}}}
    assert recensus._source_pin_status(same, dict(same))["status"] == "match"
