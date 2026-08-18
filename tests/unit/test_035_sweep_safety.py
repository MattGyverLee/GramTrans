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

import json
import os
import re
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug import fullsweep as sweep  # noqa: E402


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
        sweep.assert_distinct_target_pool(("Target", "Target"),
                                           frozen_sources=("Esperanto",))


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
    # Patch the DEFINING module's global, not the ``import *`` copy bound onto
    # the package namespace -- ``assert_concurrency_gate_satisfied`` reads
    # ``pool.CONCURRENCY_TRIAL_ARTIFACT``, so patching ``sweep.`` is inert.
    # (See test_the_gate_reads_the_defining_modules_global_not_the_reexported_copy
    # below, which pins that distinction directly.)
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT",
                        tmp_path / "no-such-file.json")
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(2)


# ===========================================================================
# T017 (US4) -- write-safety hardening: boundary independence, falsy inputs,
# name-shape rejection, and one-destination-per-worker.
# Source: specs/035-fullsweep-fidelity/tasks.md Phase 3, FR-011..FR-019,
# FR-023, FR-024.
# ===========================================================================

import pytest  # noqa: E402


def _ok_kwargs(**over):
    kw = dict(source_name="Esperanto", frozen_sources=("Esperanto",),
              allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(_ROOT))
    kw.update(over)
    return kw


# --- FR-012: an archived directory whose name BEGINS with the pattern ------

def test_archived_directory_beginning_with_pattern_is_refused_at_both_boundaries():
    """FR-012 + FR-013: the real archived-evidence shape on this machine
    (``Target.pre025bak``) must be refused, and refused INDEPENDENTLY at each
    of the two boundaries -- not once, by whichever happens to run first."""
    for boundary_fn in (sweep.assert_restore_boundary, sweep.assert_first_write_boundary):
        with pytest.raises(sweep.WriteSafetyError):
            boundary_fn("Target.pre025bak", **_ok_kwargs())


# --- FR-013: both boundaries evaluated; skipping one cannot skip the other --

def test_each_boundary_records_all_five_assertions_independently():
    ledger = sweep.AssertionLedger(project="Esperanto")
    sweep.assert_restore_boundary("Target", ledger=ledger, **_ok_kwargs())
    assert ledger.evaluated(sweep.BOUNDARY_RESTORE) == set(sweep.REQUIRED_ASSERTIONS)
    # Boundary (b) has evaluated NOTHING yet -- (a) passing did not satisfy it.
    assert ledger.evaluated(sweep.BOUNDARY_FIRST_WRITE) == set()
    sweep.assert_first_write_boundary("Target", ledger=ledger, **_ok_kwargs())
    assert ledger.evaluated(sweep.BOUNDARY_FIRST_WRITE) == set(sweep.REQUIRED_ASSERTIONS)


def test_skipping_the_restore_boundary_cannot_be_covered_by_the_write_boundary():
    """FR-013's core claim: 'a defect that skips one MUST NOT be able to skip
    the other'. A run that evaluated only boundary (b) must FAIL the
    completeness check, not pass because some evaluation happened."""
    ledger = sweep.AssertionLedger(project="Esperanto")
    sweep.assert_first_write_boundary("Target", ledger=ledger, **_ok_kwargs())
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_both_boundaries_evaluated(ledger)


def test_skipping_the_write_boundary_cannot_be_covered_by_the_restore_boundary():
    ledger = sweep.AssertionLedger(project="Esperanto")
    sweep.assert_restore_boundary("Target", ledger=ledger, **_ok_kwargs())
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_both_boundaries_evaluated(ledger)


def test_both_boundaries_evaluated_passes_only_when_both_ran():
    ledger = sweep.AssertionLedger(project="Esperanto")
    sweep.assert_restore_boundary("Target", ledger=ledger, **_ok_kwargs())
    sweep.assert_first_write_boundary("Target", ledger=ledger, **_ok_kwargs())
    sweep.assert_both_boundaries_evaluated(ledger)  # must not raise


def test_absent_ledger_is_a_failure_not_a_pass():
    """FR-015's principle applied to the evidence itself: an absent record is
    not an absent violation."""
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_boundary_fully_evaluated(None, sweep.BOUNDARY_RESTORE)


def test_a_partially_evaluated_boundary_is_a_failure():
    ledger = sweep.AssertionLedger(project="Esperanto")
    ledger.record(sweep.ASSERTION_ALLOWLIST, sweep.BOUNDARY_RESTORE)
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_boundary_fully_evaluated(ledger, sweep.BOUNDARY_RESTORE)


# --- FR-015: a falsy comparison input RAISES rather than skipping ----------

@pytest.mark.parametrize("falsy", [None, "", 0, False])
def test_falsy_source_name_raises_rather_than_skipping(falsy):
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe("Target", **_ok_kwargs(source_name=falsy))


@pytest.mark.parametrize("falsy", [None, (), [], "", set()])
def test_falsy_frozen_sources_raises_rather_than_skipping(falsy):
    """An EMPTY manifest makes the manifest-wide test vacuously true. FR-015
    names 'absent, empty, or otherwise falsy' precisely so this cannot pass."""
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe("Target", **_ok_kwargs(frozen_sources=falsy))


# --- FR-018: separators, drive designators, relative components -----------

@pytest.mark.parametrize("bad", [
    "Target/x", "Target\\x", "C:Target", "C:\\Target", "/Target", "\\Target",
    "../Target", "./Target", "..", ".", "", "Target/..",
])
def test_name_shape_rejection_covers_separators_drives_and_relatives(bad):
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_destination_safe(bad, **_ok_kwargs(allowlist=(re.escape(bad),)))


def test_name_shape_is_checked_before_the_allowlist():
    """FR-018 says 'rejected BEFORE use ... checked before any allowlist
    match'. An allowlist that would happily full-match the bad name must not
    rescue it."""
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_name_allowlisted("Target/../Esperanto",
                                       (r"Target/\.\./Esperanto",))


# --- FR-019/FR-034: no two workers ever hold one destination --------------

def test_two_concurrent_claims_on_one_destination_are_refused(tmp_path):
    first = sweep.ExclusiveTargetClaim("Target", tmp_path)
    first.acquire()
    try:
        second = sweep.ExclusiveTargetClaim("Target", tmp_path)
        with pytest.raises(sweep.WriteSafetyError):
            second.acquire()
    finally:
        first.release()


def test_a_released_claim_can_be_reacquired(tmp_path):
    with sweep.ExclusiveTargetClaim("Target", tmp_path):
        pass
    with sweep.ExclusiveTargetClaim("Target", tmp_path):
        pass  # must not raise


def test_claim_lost_mid_project_is_detected(tmp_path):
    """FR-034: the claim is held for the ENTIRE duration. Losing it mid-run
    silently readmits a second worker, so an acquisition-time check alone is
    not enough."""
    claim = sweep.ExclusiveTargetClaim("Target", tmp_path)
    claim.acquire()
    claim.assert_held()  # must not raise while genuinely held
    (tmp_path / "claims" / "Target.claim").unlink()
    with pytest.raises(sweep.WriteSafetyError):
        claim.assert_held()


def test_claim_taken_over_by_another_process_is_detected(tmp_path):
    claim = sweep.ExclusiveTargetClaim("Target", tmp_path)
    claim.acquire()
    path = tmp_path / "claims" / "Target.claim"
    path.write_text(json.dumps({"pid": os.getpid() + 1, "target": "Target"}),
                    encoding="utf-8")
    with pytest.raises(sweep.WriteSafetyError):
        claim.assert_held()


def test_unacquired_claim_never_reads_as_held(tmp_path):
    claim = sweep.ExclusiveTargetClaim("Target", tmp_path)
    with pytest.raises(sweep.WriteSafetyError):
        claim.assert_held()


# --- FR-149: untracked evidence is not admissible -------------------------

def test_untracked_evidence_is_refused(tmp_path):
    scratch = tmp_path / "untracked-roster.json"
    scratch.write_text("{}", encoding="utf-8")
    with pytest.raises(sweep.EvidenceProvenanceError):
        sweep.assert_tracked(scratch, kind=sweep.EVIDENCE_KIND_ROSTER)


def test_a_tracked_contract_file_is_admissible():
    tracked = Path(_ROOT) / "specs" / "035-fullsweep-fidelity" / "contracts" / "guards.md"
    sweep.assert_tracked(tracked, kind=sweep.EVIDENCE_KIND_CAPABILITY)  # must not raise


def test_evidence_provenance_is_classified_as_a_whole_run_abort():
    """FR-149 + FR-175: inadmissible evidence is a PROVENANCE failure, and
    provenance failures abort the whole run. Classified by CODE, never by
    matching message text (FR-176)."""
    code = sweep.classify_exception(sweep.EvidenceProvenanceError("x"))
    assert code == sweep.FAILURE_CODE_PROVENANCE
    assert code in sweep.ABORT_WHOLE_RUN_CODES


# ===========================================================================
# T018 (US4) -- baseline pinning. Source: FR-170..FR-173, S-10.
# ===========================================================================

def _make_backup(tmp_path, name="Target", extra_members=(), data_name=None):
    """Build a minimal .fwbackup-shaped zip: one top-level .fwdata plus a
    settings directory."""
    archive = tmp_path / ("%s.fwbackup" % name)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(data_name or ("%s.fwdata" % name),
                   '<?xml version="1.0"?><languageproject version="7000072"/>')
        z.writestr("ConfigurationSettings/settings.xml", "<settings/>")
        for member, content in extra_members:
            z.writestr(member, content)
    return archive


def test_restore_without_a_pinned_hash_refuses_to_start(tmp_path):
    """FR-170/S-10: a run that cannot name and hash its baseline does not
    start. Absent hash is a failure, never 'skip the check'."""
    archive = _make_backup(tmp_path)
    for absent in (None, "", "   "):
        with pytest.raises(sweep.BaselineError):
            sweep.pin_baseline(archive, absent)


def test_baseline_named_without_an_archive_refuses():
    with pytest.raises(sweep.BaselineError):
        sweep.pin_baseline(None, "a" * 64)


def test_baseline_whose_hash_does_not_match_is_refused(tmp_path):
    archive = _make_backup(tmp_path)
    with pytest.raises(sweep.BaselineError):
        sweep.pin_baseline(archive, "0" * 64)


def test_baseline_with_a_matching_hash_is_accepted(tmp_path):
    archive = _make_backup(tmp_path)
    digest = sweep.sha256_file(archive)
    pinned = sweep.pin_baseline(archive, digest.upper())  # case-insensitive
    assert pinned.sha256 == digest


def test_a_malformed_hash_is_refused(tmp_path):
    archive = _make_backup(tmp_path)
    with pytest.raises(sweep.BaselineError):
        sweep.pin_baseline(archive, "not-a-sha256")


def test_no_newest_archive_glob_fallback_exists_anywhere():
    """FR-170: 'The sweep MUST NEVER select a baseline by recency, by
    directory scan, or by any other implicit rule.'

    ``harness/restore.py`` DOES have such a fallback (``newest_backup``, and
    ``restore_target(backup_path=None)`` calls it). This test pins that no
    035 sweep module reaches it: not by import, not by name, and not by
    globbing ``*.fwbackup`` itself.
    """
    pkg_dir = Path(_ROOT) / "debug" / "fullsweep"
    sources = sorted(pkg_dir.glob("*.py")) + [Path(_ROOT) / "debug" / "run_fullcopy_sweep.py"]
    offenders = []
    for src in sources:
        text = src.read_text(encoding="utf-8")
        # Strip docstrings/comments crudely: only executable references matter,
        # and every mention below is a NAME reference, not prose.
        for needle in ("newest_backup", "restore_target", '"*.fwbackup"', "'*.fwbackup'"):
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if needle in line and not stripped.startswith("#") \
                        and not stripped.startswith("*") \
                        and "``" not in line:
                    offenders.append("%s:%d: %s" % (src.name, lineno, stripped[:90]))
    assert not offenders, (
        "FR-170: a newest-archive/recency fallback is reachable from the sweep:\n  "
        + "\n  ".join(offenders))


def test_archive_with_more_than_one_top_level_data_file_is_refused(tmp_path):
    archive = _make_backup(tmp_path, extra_members=[("Other.fwdata", "<x/>")])
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    with pytest.raises(sweep.BaselineError):
        sweep.assert_baseline_shape(pinned, destination_name="Target")


def test_archive_whose_data_file_names_another_project_is_refused(tmp_path):
    """FR-170's named accident: an archive of a REAL project restored under
    the disposable target's name would make every later comparison run
    against a secret clone."""
    archive = _make_backup(tmp_path, name="Esperanto")
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    with pytest.raises(sweep.BaselineError):
        sweep.assert_baseline_shape(pinned, destination_name="Target")


def test_archive_identity_may_be_declared_separately(tmp_path):
    archive = _make_backup(tmp_path, name="Esperanto")
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    shape = sweep.assert_baseline_shape(
        pinned, destination_name="Target", expected_baseline_identity="Esperanto")
    assert shape.top_level_data_file == "Esperanto.fwdata"


@pytest.mark.parametrize("escaping", [
    "../escape.txt", "..\\escape.txt", "/abs.txt", "C:/abs.txt",
    "ConfigurationSettings/../../escape.txt",
])
def test_archive_member_escaping_the_destination_is_refused(tmp_path, escaping):
    """FR-171/FR-169: archive-controlled relative or absolute components can
    direct a write outside the destination while every NAME assertion
    passes."""
    archive = _make_backup(tmp_path, extra_members=[(escaping, "x")])
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    with pytest.raises(sweep.BaselineError):
        sweep.assert_baseline_shape(pinned, destination_name="Target")


def test_item_containment_is_proven_from_the_resolved_destination(tmp_path):
    dest = tmp_path / "Target"
    dest.mkdir()
    sweep.assert_item_contained(dest, dest / "a" / "b.txt")  # must not raise
    with pytest.raises(sweep.BaselineError):
        sweep.assert_item_contained(dest, tmp_path / "elsewhere.txt")
    with pytest.raises(sweep.BaselineError):
        sweep.assert_item_contained(dest, dest / ".." / "escape.txt")


def test_post_restore_file_set_must_equal_the_baseline_plus_evidence(tmp_path):
    """FR-173: equality, not containment. Residue is tolerated only where
    DECLARED, and the observed delta is recorded either way."""
    archive = _make_backup(tmp_path)
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    shape = sweep.assert_baseline_shape(pinned, destination_name="Target")

    dest = tmp_path / "projects" / "Target"
    (dest / "ConfigurationSettings").mkdir(parents=True)
    (dest / "Target.fwdata").write_text("<x/>", encoding="utf-8")
    (dest / "ConfigurationSettings" / "settings.xml").write_text("<s/>", encoding="utf-8")
    (dest / sweep.RESTORE_EVIDENCE_NAME).write_text("{}", encoding="utf-8")

    delta = sweep.assert_post_restore_file_set(dest, shape, "Target")
    assert delta["unexpected"] == [] and delta["missing"] == []

    # Undeclared residue -> refuse.
    (dest / "leftover.tmp").write_text("x", encoding="utf-8")
    with pytest.raises(sweep.BaselineError):
        sweep.assert_post_restore_file_set(dest, shape, "Target")

    # Declared residue -> tolerated, and still RECORDED.
    delta = sweep.assert_post_restore_file_set(
        dest, shape, "Target", tolerated_residue=("leftover.tmp",))
    assert delta["unexpected"] == ["leftover.tmp"]
    assert delta["untolerated_residue"] == []

    # A MISSING file is never tolerable.
    (dest / "Target.fwdata").unlink()
    with pytest.raises(sweep.BaselineError):
        sweep.assert_post_restore_file_set(
            dest, shape, "Target", tolerated_residue=("leftover.tmp",))


def test_a_directory_that_merely_exists_is_not_usable(tmp_path):
    """FR-172: 'a worker killed mid-restore leaves a directory that exists
    and is rubble'."""
    archive = _make_backup(tmp_path)
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    dest = tmp_path / "projects" / "Target"
    dest.mkdir(parents=True)
    assert sweep.destination_is_usable(dest, pinned=pinned, destination_name="Target") is False


def test_restore_evidence_round_trips_and_validates(tmp_path):
    archive = _make_backup(tmp_path)
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    shape = sweep.assert_baseline_shape(pinned, destination_name="Target")
    dest = tmp_path / "projects" / "Target"
    dest.mkdir(parents=True)
    sweep.write_restore_evidence(dest, pinned=pinned, destination_name="Target",
                                  shape=shape)
    assert sweep.destination_is_usable(dest, pinned=pinned, destination_name="Target")
    # Evidence for a DIFFERENT baseline does not validate.
    other = sweep.PinnedBaseline(archive=pinned.archive, sha256="b" * 64)
    assert not sweep.destination_is_usable(dest, pinned=other, destination_name="Target")


def test_end_to_end_pinned_restore_is_contained_and_leaves_evidence(tmp_path, monkeypatch):
    """The whole T020 path: safety choke point, shape, containment, removals,
    extraction, FR-174 location check, evidence, file-set equality."""
    root = tmp_path / "projects"
    root.mkdir()
    archive = _make_backup(tmp_path)
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    result = sweep.restore_from_pinned_baseline(
        "Target", pinned=pinned, source_name="Esperanto",
        frozen_sources=("Esperanto",), allowlist=sweep.DEFAULT_ALLOWLIST,
        projects_root=str(root),
    )
    dest = root / "Target"
    assert (dest / "Target.fwdata").is_file()
    assert (dest / sweep.RESTORE_EVIDENCE_NAME).is_file()
    assert result.residue_delta["untolerated_residue"] == []
    assert result.declared_locations["LinkedFilesRootDir"]["contained"] is True


def test_pinned_restore_refuses_a_destination_that_is_a_source(tmp_path):
    """FR-023: the refusal happens BEFORE a directory is created, a lock is
    removed, or a data file is removed."""
    root = tmp_path / "projects"
    root.mkdir()
    archive = _make_backup(tmp_path)
    pinned = sweep.pin_baseline(archive, sweep.sha256_file(archive))
    with pytest.raises(sweep.WriteSafetyError):
        sweep.restore_from_pinned_baseline(
            "Target", pinned=pinned, source_name="Esperanto",
            frozen_sources=("Esperanto", "Target"),
            allowlist=sweep.DEFAULT_ALLOWLIST, projects_root=str(root),
        )
    assert not (root / "Target").exists(), (
        "FR-023: nothing may be created before the write-safety refusal")


def test_linked_files_pointing_outside_the_destination_is_refused(tmp_path):
    """FR-174: a baseline restored under a new name can carry an ABSOLUTE
    linked-files location pointing at the project it was archived from.
    Because such writes are additive, a data-file-only fingerprint can never
    detect them."""
    dest = tmp_path / "Target"
    dest.mkdir()
    (dest / "Target.fwdata").write_text(
        '<?xml version="1.0"?><languageproject><LinkedFilesRootDir>'
        + str(tmp_path / "SomeRealProject" / "LinkedFiles")
        + "</LinkedFilesRootDir></languageproject>", encoding="utf-8")
    with pytest.raises(sweep.BaselineError):
        sweep.assert_declared_locations_contained(dest, "Target")


def test_linked_files_beneath_the_destination_is_accepted(tmp_path):
    dest = tmp_path / "Target"
    dest.mkdir()
    (dest / "Target.fwdata").write_text(
        '<?xml version="1.0"?><languageproject><LinkedFilesRootDir>'
        + str(dest / "LinkedFiles")
        + "</LinkedFilesRootDir></languageproject>", encoding="utf-8")
    record = sweep.assert_declared_locations_contained(dest, "Target")
    assert record["LinkedFilesRootDir"]["contained"] is True


# ===========================================================================
# T021 -- concurrency gate: the trial artifact must be PRESENT AND VALID.
# Also closes the latent test weakness recorded in .crew-handoff.json: the
# original test patched the flat re-exported COPY on the package namespace,
# not pool.py's module global that the gate actually reads.
# ===========================================================================

def test_the_gate_reads_the_defining_modules_global_not_the_reexported_copy(tmp_path,
                                                                            monkeypatch):
    """Patching ``sweep.CONCURRENCY_TRIAL_ARTIFACT`` (the ``import *`` copy)
    must NOT change what the gate consults; patching
    ``sweep.pool.CONCURRENCY_TRIAL_ARTIFACT`` must."""
    valid = tmp_path / "trial.json"
    valid.write_text(json.dumps({
        "schema_version": 1, "max_workers_demonstrated": 4,
        "host_service": "fw-db", "recorded_at": "2026-01-01",
    }), encoding="utf-8")

    # Patching the package-level copy is INERT for the gate.
    monkeypatch.setattr(sweep, "CONCURRENCY_TRIAL_ARTIFACT", valid)
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT",
                        tmp_path / "no-such-file.json")
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(2)

    # Patching the DEFINING module's global is what counts.
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT", valid)
    sweep.assert_concurrency_gate_satisfied(2)  # must not raise


def test_a_present_but_invalid_trial_artifact_does_not_unlock_concurrency(tmp_path,
                                                                          monkeypatch):
    """SC-012 says PRESENT AND VALID. Mere existence must not be enough."""
    empty = tmp_path / "trial.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT", empty)
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(2)


def test_a_trial_demonstrating_fewer_workers_does_not_authorize_more(tmp_path,
                                                                     monkeypatch):
    trial = tmp_path / "trial.json"
    trial.write_text(json.dumps({
        "schema_version": 1, "max_workers_demonstrated": 2,
        "host_service": "fw-db", "recorded_at": "2026-01-01",
    }), encoding="utf-8")
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT", trial)
    sweep.assert_concurrency_gate_satisfied(2)
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(3)


def test_a_corrupt_trial_artifact_raises_rather_than_reading_as_absent(tmp_path,
                                                                       monkeypatch):
    trial = tmp_path / "trial.json"
    trial.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sweep.pool, "CONCURRENCY_TRIAL_ARTIFACT", trial)
    with pytest.raises(sweep.WriteSafetyError):
        sweep.assert_concurrency_gate_satisfied(2)


def test_no_trial_artifact_is_shipped_in_this_repo():
    """FR-032/FR-033: the gate is UNSATISFIED as of this checkpoint. If this
    test ever fails, a trial artifact appeared -- confirm it records a real
    measurement before letting it stand."""
    assert not sweep.pool.concurrency_trial_path().is_file()


# --- FR-028/FR-029/FR-030: admission is measured, provisional, unnamed ----

def test_memory_model_is_stamped_provisional_wherever_it_is_used():
    decision = sweep.decide_admission("Whatever", 10.0)
    assert decision.model["status"] == "PROVISIONAL"
    assert "one-point regression" in decision.model["derivation"]
    assert decision.as_dict()["memory_model"]["status"] == "PROVISIONAL"


def test_no_named_project_or_size_rank_admission_rule_exists():
    """FR-029: 'The sweep MUST NOT bound peak memory by a rule about which
    named or size-ranked projects may run together.'"""
    assert sweep.pool.NAMED_PROJECT_ADMISSION_RULES == ()


def test_observed_actuals_are_preferred_over_the_model(monkeypatch):
    """FR-030: 'Once observed actuals exist ... the admission check MUST
    prefer them over the model's prediction'."""
    monkeypatch.setattr(sweep.pool, "free_memory_mb", lambda: 100000.0)
    modelled = sweep.decide_admission("Esperanto", 100.0)
    assert modelled.source == "provisional-model"
    measured = sweep.decide_admission("Esperanto", 100.0,
                                       observed_actuals={"Esperanto": 42.0})
    assert measured.source == "observed-actual" and measured.predicted_mb == 42.0


def test_unmeasurable_free_memory_fails_toward_waiting(monkeypatch):
    monkeypatch.setattr(sweep.pool, "free_memory_mb", lambda: None)
    decision = sweep.decide_admission("Esperanto", 1.0)
    assert decision.admitted is False


def test_memory_shortfall_never_shares_the_write_safety_error_path(monkeypatch):
    """FR-177: an operational retry and a safety abort must never share an
    error path."""
    monkeypatch.setattr(sweep.pool, "free_memory_mb", lambda: 1.0)
    with pytest.raises(sweep.MemoryShortfall):
        sweep.assert_memory_admits_project("Esperanto", 10000.0)
    assert not issubclass(sweep.MemoryShortfall, sweep.WriteSafetyError)
    assert sweep.classify_exception(sweep.MemoryShortfall("x")) \
        == sweep.FAILURE_CODE_MEMORY_SHORTFALL
    assert sweep.FAILURE_CODE_MEMORY_SHORTFALL not in sweep.ABORT_WHOLE_RUN_CODES


# ===========================================================================
# T022 -- capability preflight (FR-124..FR-132, SC-008).
# ===========================================================================

def test_an_unpinned_fingerprint_is_a_mismatch_not_a_pass(tmp_path, monkeypatch):
    """FR-132: no best-effort degradation. A scaffold fingerprint means the
    preflight cannot say what it expected, so it must refuse."""
    scaffold = tmp_path / "flexicon-capability.json"
    scaffold.write_text(json.dumps({"schema_version": 1, "introspected": {}}),
                        encoding="utf-8")
    # ``load_pinned_fingerprint`` imports ``assert_tracked`` from ``safety`` at
    # call time, so the DEFINING module is what must be patched. Trackedness is
    # a separate requirement (FR-149) with its own tests above; this one is
    # about an UNPINNED expectation.
    monkeypatch.setattr(sweep.safety, "assert_tracked", lambda *a, **k: None)
    result = sweep.run_preflight(tmp_path)
    assert result.ok is False
    assert result.verdict == "PREFLIGHT_MISMATCH"
    assert result.exit_code == 6


def test_the_pinned_fingerprint_in_this_repo_matches_the_live_dependency():
    """T023's capture, re-verified. A failure here is real capability drift
    and requires a deliberate, recorded update to the pinned expectation
    (FR-132) -- never a loosened test."""
    result = sweep.run_preflight()
    assert result.ok, sweep.format_diff_report(result, max_rows=10)


def test_a_changed_default_is_reported_as_a_field_level_difference():
    """FR-125's load-bearing fact: a breaking DEFAULT can change while the
    version string stays fixed. FR-131: the report names the symbol, the
    expected value, the actual value, and the kind."""
    pinned = sweep.load_pinned_fingerprint()
    tampered = json.loads(json.dumps(pinned["introspected"]))
    sig = tampered["signatures"]["flexicon.FLExProject.OpenProject"]
    sig["parameters"]["undoable"] = "False"
    diffs = sweep.diff_capabilities(tampered, sweep.introspect_capabilities())
    changed = [d for d in diffs if d.kind == "changed" and d.symbol.endswith("undoable")]
    assert len(changed) == 1
    assert changed[0].expected == "False" and changed[0].actual == "True"


def test_a_removed_symbol_is_reported_as_missing():
    pinned = sweep.load_pinned_fingerprint()
    tampered = json.loads(json.dumps(pinned["introspected"]))
    tampered["signatures"]["flexicon.Imaginary.Symbol"] = {"parameters": {}, "order": []}
    diffs = sweep.diff_capabilities(tampered, sweep.introspect_capabilities())
    assert any(d.kind == "missing" and "Imaginary" in d.symbol for d in diffs)


def test_diff_kinds_are_exactly_the_four_the_spec_names():
    assert sweep.preflight.DIFF_KINDS == ("missing", "added", "changed", "renamed")
    with pytest.raises(ValueError):
        sweep.preflight.CapabilityDiff(symbol="x", expected=1, actual=2, kind="weird")


def test_the_guid_preserving_create_surface_is_pinned_and_present():
    """FR-128: a missing identity-preserving creation capability must fail
    LOUDLY at preflight rather than surface later as a laundered, generic
    creation failure."""
    measured = sweep.introspect_capabilities()
    surface = measured["guid_create_surface"]
    assert len(surface) == 8
    for key, shape in surface.items():
        assert "error" not in shape, "%s did not resolve: %r" % (key, shape.get("error"))
        assert shape.get("accepts_guid_kwarg") is True, key


def test_all_eight_grammar_overrides_are_declared_not_inherited():
    """FR-130 + this repo's CLAUDE.md: the MCP indexer's static analysis does
    not follow inheritance, so the override must be DECLARED on each class."""
    measured = sweep.introspect_capabilities()
    overrides = measured["grammar_overrides"]
    assert len(overrides) == 8
    assert all(v.get("declared") is True for v in overrides.values()), overrides


def test_the_dead_lexicon_accessor_must_not_resolve():
    measured = sweep.introspect_capabilities()
    assert measured["dead_accessors"]["lexicon"]["present"] is False


def test_a_site_packages_resolution_fails_the_preflight(monkeypatch):
    """FR-126: a dependency resolved from a stale packaged copy rather than
    the tracked working installation MUST fail."""
    real = sweep.preflight.dependency_provenance()
    monkeypatch.setattr(sweep.preflight, "dependency_provenance",
                        lambda: dict(real, from_site_packages=True))
    result = sweep.run_preflight()
    assert result.ok is False and result.exit_code == 6


def test_preflight_never_reads_the_version_string_as_the_decision():
    """FR-125: introspection decides; the version string is recorded only."""
    result = sweep.run_preflight()
    assert result.ok
    # The live installation's own metadata disagrees with itself (dist says
    # 4.3.1, MCP reports 4.4.0, __version__ is None). The preflight passes
    # regardless, because it never consults any of them.
    assert result.provenance["reported_version"] in (None, "4.3.1", "4.4.0")


# ===========================================================================
# T024 -- CLI surface (contracts/sweep-cli.md).
# ===========================================================================

def _driver_module():
    import importlib.util
    path = Path(_ROOT) / "debug" / "run_fullcopy_sweep.py"
    spec = importlib.util.spec_from_file_location("_sweep_driver_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_an_argument_error_exits_5_not_argparses_default_2():
    """contracts/sweep-cli.md, Exit codes: a run that could not be configured
    measured nothing, so it is HARNESS_ERROR (5). argparse's own default of 2
    would collide with NON_IDEMPOTENT."""
    driver = _driver_module()
    with pytest.raises(SystemExit) as exc:
        driver.main(["project", "--source", "X", "--target", "Target",
                     "--intent", "gate"])
    assert exc.value.code == sweep.exit_code_for("HARNESS_ERROR") == 5


def test_baseline_sha256_is_required_with_backup():
    driver = _driver_module()
    with pytest.raises(SystemExit) as exc:
        driver.main(["project", "--source", "X", "--target", "Target",
                     "--intent", "gate", "--exclude-categories", "",
                     "--diagnostic-level", "normal", "--backup", "x.fwbackup"])
    assert exc.value.code == 5


def test_exclude_categories_and_diagnostic_level_are_required_and_explicit():
    driver = _driver_module()
    for missing in (["--diagnostic-level", "normal"], ["--exclude-categories", ""]):
        with pytest.raises(SystemExit) as exc:
            driver.main(["project", "--source", "X", "--target", "Target",
                         "--intent", "gate"] + missing)
        assert exc.value.code == 5


def test_exclude_categories_may_be_explicitly_empty():
    driver = _driver_module()
    assert driver._split_categories("") == []
    assert driver._split_categories("stems, senses") == ["stems", "senses"]


def test_artifacts_dir_default_moved_out_of_the_tracked_spec_folder():
    """Research D-10: per-run result artifacts are EVIDENCE, not reviewed
    source. What stays tracked is exactly what FR-149 names."""
    driver = _driver_module()
    default = Path(driver.DEFAULT_ARTIFACTS_DIR)
    assert default.parts[-2:] == ("035_sweep", "artifacts")
    assert "specs" not in default.parts


def test_the_tracked_inputs_have_tracked_defaults():
    driver = _driver_module()
    assert Path(driver.DEFAULT_CONTRACTS_DIR).name == "contracts"
    assert Path(driver.DEFAULT_LEDGER_PATH).name == "ledger.json"
    assert "specs" in Path(driver.DEFAULT_LEDGER_PATH).parts


def test_the_preflight_subcommand_exists_and_touches_no_database(tmp_path):
    """SC-008: the preflight runs, and may refuse, before any restore or
    write; the subcommand itself opens nothing."""
    driver = _driver_module()
    rc = driver.main(["--artifacts-dir", str(tmp_path), "preflight"])
    assert rc == 0
    assert (tmp_path / "preflight.json").is_file()
    # Nothing resembling a project directory was created.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["preflight.json"]


def test_run_one_project_refuses_without_a_pinned_baseline():
    driver = _driver_module()
    with pytest.raises(sweep.BaselineError):
        driver.run_one_project(
            "Esperanto", target_name="Target", frozen_sources=("Esperanto",),
            allowlist=sweep.DEFAULT_ALLOWLIST, run_intent="gate",
            pinned_baseline=None, exclude_categories=[],
            diagnostic_level="normal",
        )
