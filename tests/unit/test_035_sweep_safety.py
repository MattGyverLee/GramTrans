"""Feature 035 -- offline unit tests for the fullsweep write-safety choke
point (``debug/run_fullcopy_sweep.py``).

These tests run with NO FLEx project and NO LCM: everything exercised here is
pure Python (regex matching, path shape checks, dataclass wiring). Per the
dispatch brief, this file covers AT MINIMUM:

  * the anchored allowlist accepts ``Target`` / ``Target1`` / ``Target12``
  * the anchored allowlist REJECTS ``Target.pre025bak``, ``TargetX``,
    ``"Target "`` (trailing space), and ``""`` (empty)
  * a destination equal to its own source is refused
  * an empty/absent allowlist raises rather than silently admitting or
    denying

A handful of additional cheap, offline cases (path-separator/drive/relative
rejection, the frozen-source-manifest check, and the distinct-target-pool
check) are included too since they cost nothing extra to verify and exercise
the same choke point from a different angle.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEBUG = _ROOT / "debug"
if str(_DEBUG) not in sys.path:
    sys.path.insert(0, str(_DEBUG))

import run_fullcopy_sweep as sweep  # noqa: E402


# ---------------------------------------------------------------------------
# Anchored allowlist: accept
# ---------------------------------------------------------------------------

def test_allowlist_accepts_bare_target_and_numbered_variants():
    for name in ("Target", "Target1", "Target12"):
        # Must not raise.
        sweep.assert_name_allowlisted(name, sweep.DEFAULT_ALLOWLIST)


# ---------------------------------------------------------------------------
# Anchored allowlist: reject (FR-011/FR-012 near-miss corpus, minimum set)
# ---------------------------------------------------------------------------

def test_allowlist_rejects_archived_backup_directory_name():
    """The whole point of FR-012: a name that merely BEGINS with the
    allowlisted pattern and continues with more characters (the real
    archived-evidence shape on this machine) must never be admitted."""
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("Target.pre025bak", sweep.DEFAULT_ALLOWLIST)


def test_allowlist_rejects_non_numeric_suffix():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("TargetX", sweep.DEFAULT_ALLOWLIST)


def test_allowlist_rejects_trailing_space():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("Target ", sweep.DEFAULT_ALLOWLIST)


def test_allowlist_rejects_empty_name():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("", sweep.DEFAULT_ALLOWLIST)


def test_allowlist_rejects_near_miss_corpus_extended():
    """FR-012's own recorded near-miss corpus: leading space, letter case,
    an appended path separator, an appended relative-path component, an
    appended decimal fraction."""
    import pytest
    near_misses = (
        " Target",           # leading space
        "target",            # letter case
        "Target/",           # appended path separator
        "Target/../x",       # appended relative-path component
        "Target.5",          # appended decimal fraction
        "Target.pre029bak",  # the other real archive on this machine
    )
    for bad in near_misses:
        with pytest.raises(sweep.WriteSafetyError):
            sweep.assert_name_allowlisted(bad, sweep.DEFAULT_ALLOWLIST)


# ---------------------------------------------------------------------------
# Empty/absent allowlist MUST raise, never silently admit or deny
# ---------------------------------------------------------------------------

def test_empty_allowlist_raises():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("Target", [])


def test_absent_allowlist_raises():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("Target", None)


# ---------------------------------------------------------------------------
# assert_destination_safe: target != source, manifest-wide, path shape
# ---------------------------------------------------------------------------

def test_destination_equal_to_source_is_refused():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(
            "Target", source_name="Target", frozen_sources=("Ejagham Mini",),
            allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT),
        )


def test_destination_present_in_frozen_source_manifest_is_refused():
    """FR-016 manifest-wide form: even if the destination differs from the
    CURRENT source in hand, it must be refused if it appears anywhere in the
    frozen source manifest (a mis-ordered pairing / stale retry)."""
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(
            "Target", source_name="Esperanto",
            frozen_sources=("Esperanto", "Target"),
            allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT),
        )


def test_omitted_source_name_raises_rather_than_bypassing():
    """FR-015: a comparison whose input is omitted must fail, not silently
    skip the comparison."""
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(
            "Target", source_name=None, frozen_sources=("Esperanto",),
            allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT),
        )


def test_omitted_frozen_sources_raises_rather_than_bypassing():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(
            "Target", source_name="Esperanto", frozen_sources=None,
            allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT),
        )


def test_destination_with_path_separator_is_rejected_before_allowlist_check():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(
            "Target/../Esperanto", source_name="Esperanto",
            frozen_sources=("Esperanto",), allowlist=("Target/../Esperanto",),
            projects_root=str(_ROOT),
        )


def test_valid_destination_resolves_under_projects_root():
    dest = sweep.assert_destination_safe(
        "Target", source_name="Esperanto", frozen_sources=("Esperanto",),
        allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT),
    )
    assert dest == (Path(_ROOT).resolve() / "Target")


# ---------------------------------------------------------------------------
# Distinct target pool (FR-034)
# ---------------------------------------------------------------------------

def test_distinct_target_pool_rejects_duplicates():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_distinct_target_pool(("Target", "Target"), frozen_sources=())


def test_distinct_target_pool_rejects_collision_with_a_frozen_source():
    import pytest
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_distinct_target_pool(("Target", "Esperanto"),
                                           frozen_sources=("Esperanto",))


def test_distinct_target_pool_accepts_a_clean_pool():
    sweep.assert_distinct_target_pool(("Target", "Target2", "Target3"),
                                       frozen_sources=("Esperanto", "Ejagham Mini"))


def test_default_target_pool_is_all_allowlisted():
    pool = sweep.default_target_pool(3)
    assert len(pool) == 3
    for name in pool:
        sweep.assert_name_allowlisted(name, sweep.DEFAULT_ALLOWLIST)


# ---------------------------------------------------------------------------
# Concurrency gate (FR-031/FR-032): default of 1 never gated; >1 refused
# without a recorded trial artifact.
# ---------------------------------------------------------------------------

def test_single_worker_never_gated():
    sweep.assert_concurrency_gate_satisfied(1)


def test_multi_worker_refused_without_a_recorded_trial(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(sweep, "CONCURRENCY_TRIAL_ARTIFACT", tmp_path / "no-such-file.json")
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(2)
