"""Feature 035 -- full-corpus, double-Move fidelity sweep (EXECUTABLE SKELETON).

Standalone CLI. NOT a plugin-host module; run it directly with
``python debug/run_fullcopy_sweep.py ...``.

THIN CLI ENTRY POINT (T008, specs/035-fullsweep-fidelity/tasks.md Phase 1):
this file used to hold the sweep's six mechanical implementation groups
directly; they have been promoted, unchanged, into the ``debug/fullsweep``
package (see ``debug/fullsweep/__init__.py`` for the map). What remains here:

  * the per-project double-move loop (``run_one_project``), wiring Groups
    B/D/K together for exactly one project;
  * the COMPARATOR / VERDICT TAXONOMY extension point (``compare_objects``),
    deliberately a stub -- see its docstring;
  * the CLI itself (``list`` / ``project`` / ``batch`` subcommands), with
    every existing flag spelling preserved exactly.

SCOPE (per the feature-035 dispatch brief, 2026-08-18): build everything the
spec has already settled -- Group A (corpus enumeration), Group B (write
safety), Group C (parallel target pool), Group D (double-move and
idempotency), Group K (artifact/provenance), Group L (batched, gated,
fix-forward execution) -- and leave the COMPARATOR / VERDICT TAXONOMY
(spec.md Groups E, F, G, H, and the identity-substitution rules of Group P)
as an explicit, documented extension point. That taxonomy is still in review
(cycle3-amendments.md / cycle3-safety-amendments.md are not yet folded into
spec.md's settled requirement groups) and MUST NOT be invented here. See
``compare_objects`` below for the pluggable seam.

Reused rather than reinvented (per instructions):
  * ``debug/prescan_type_coverage.py`` -- corpus enumeration
    (``_enumerate``/``_walk_flex_projects``), the anchored
    ``^Target[0-9]*$`` refusal pattern, its ``_fingerprint`` helper shape, and
    its subprocess-isolation driver pattern.
  * ``tests/integration/harness/restore.py`` -- ``restore_target`` (see the
    HAZARD note on ``ExclusiveTargetClaim`` and ``self_heal_stale_lock``
    below: it unconditionally deletes ``*.lock`` and rmtrees settings dirs
    for WHATEVER name it is given, so this driver never calls it without
    first passing every name through ``assert_destination_safe``).
  * ``tests/integration/harness/full_run.py`` -- ``build_full_selection`` and
    ``run_full_transfer``. This driver ALWAYS calls
    ``build_full_selection(exclude=frozenset())`` -- an explicit EMPTY
    exclusion set -- because ``full_run``'s own default excludes
    ``GrammarCategory.STEMS`` and the user has explicitly decided stems are
    required for this sweep. The resulting coverage set is recorded in every
    artifact (Group K, FR-142).
  * ``debug/audit_guid_preservation.py`` -- the ``AllInstances`` identity-keyed
    inventory shape (``{class_name: {guid, ...}}``), reused here as
    ``census_project``.

WRITE SAFETY (Group B) is the highest-severity section of this driver's
dependency package. See ``debug.fullsweep.safety.assert_destination_safe`` --
the single choke-point every restore call and every write-enabled-open call
in this driver goes through, computed fresh from the literal value about to
be used, never cached or inherited from an enumeration helper
(FR-013/FR-014/FR-015).

NO SILENT ANYTHING (per the dispatch brief): every recorded exception below
carries its ``traceback.format_exc()``; there is no bare ``except: pass`` in
this file; a project's per-project artifact is written even on an unhandled
failure (best-effort, itself never silently swallowed); the driver's exit
code is non-zero if anything failed.

ASCII-only console output (Windows-terminal safe).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional, Sequence

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from debug.fullsweep import *  # noqa: F401,F403,E402 -- the package's public surface

VALID_RUN_INTENTS = ("baseline", "gate")

# ---------------------------------------------------------------------------
# T024 CLI surface constants (contracts/sweep-cli.md)
# ---------------------------------------------------------------------------

#: CHANGED DEFAULT (research D-10): per-run result artifacts are EVIDENCE, not
#: reviewed source, so they move out of the tracked spec folder into the
#: gitignored runtime dir. What stays tracked is exactly what FR-149 names --
#: the driver, the rosters, the allowlist, the capability fingerprint, the
#: negative-control artifact and the ledger.
DEFAULT_ARTIFACTS_DIR = DEFAULT_RUNTIME_DIR / "artifacts"

#: FR-149 tracked inputs.
DEFAULT_CONTRACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
DEFAULT_LEDGER_PATH = _ROOT / "specs" / "035-fullsweep-fidelity" / "ledger.json"

#: ``--diagnostic-level`` is set explicitly and recorded; it is NEVER
#: setdefault-ed from the environment, because a level silently inherited
#: from an operator's shell makes two runs incomparable while both look
#: configured.
DIAGNOSTIC_LEVELS = ("quiet", "normal", "verbose")


# ===========================================================================
# GROUP E/F/G/H PLUGGABLE SEAM -- NOT BUILT HERE (still in review)
# ===========================================================================

def compare_objects(source_inventory: dict, target_inventory: dict) -> list[dict]:
    """EXTENSION POINT for the field-level fidelity comparator.

    Deliberately NOT the taxonomy from spec.md Groups E (field-level
    semantics), F (vacuity guards), G (verdict/exit model), H (loss
    allowlist), or the identity-substitution rules of Group P -- those are
    still in review as of 2026-08-18 (cycle3-amendments.md and
    cycle3-safety-amendments.md have not yet been folded into spec.md's
    settled requirement groups) and inventing them here would hardcode a
    taxonomy this feature does not yet have authority to hardcode.

    Contract for the eventual real implementation:
        source_inventory / target_inventory: ``{class_name: {guid, ...}}``,
            the same identity-keyed shape ``census_project`` returns.
        Returns: ``list[dict]`` "findings". Per FR-145 (settled, Group K),
            every real finding MUST eventually carry AT LEAST:
                {"class": str, "category": str | None, "field": str | None,
                 "source_value": Any, "target_value": Any,
                 "verdict": str, "guid": str}
            -- but the legal ``verdict`` vocabulary (RESOLVED / DANGLING /
            SILENTLY_UNSET / LOST-BUT-ACCOUNTED / RESOLVED-BY-EQUIVALENCE for
            links; DISTORTED / EXPECTED_DIVERGENT / etc. for field content;
            the five FR-094..FR-099 vacuity guards; the allowlist-consumption
            accounting of Group H) is exactly what has not been settled.

    TODO(035-verdict-taxonomy): replace this stub once Groups E-P leave
    review. Until then this performs ONLY the total-accounting
    presence/absence reconciliation that the identity-keyed census already
    gives for free -- no taxonomy decision required for that much: a source
    GUID is either present in the target's post-transfer inventory for its
    class, or it is not.

    ``run_one_project`` (below) takes this function as an injectable
    parameter (default: this stub) so a future comparator can be wired in
    without touching the driver's control flow.
    """
    findings: list[dict] = []
    for cls, src_guids in source_inventory.items():
        tgt_guids = target_inventory.get(cls, set())
        for g in sorted(src_guids - tgt_guids):
            findings.append({
                "class": cls, "category": None, "field": None,
                "source_value": g, "target_value": None,
                "verdict": "NOT_YET_CLASSIFIED_MISSING_FROM_TARGET",
                "guid": g,
            })
    return findings


# ===========================================================================
# PER-PROJECT DOUBLE-MOVE LOOP (Groups B/D/K wired together)
# ===========================================================================

def run_one_project(
    source_name: str,
    *,
    target_name: str,
    frozen_sources: tuple,
    allowlist: Sequence[str],
    run_intent: str,
    pinned_baseline,
    exclude_categories: Sequence[str],
    diagnostic_level: str,
    projects_root: Optional[str] = None,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    comparator: Callable[[dict, dict], list] = compare_objects,
    tolerated_residue: Sequence[str] = (),
) -> ProjectArtifact:
    """FR-043: restore -> census -> Move #1 -> census -> Move #2 -> census ->
    restore, for exactly one project, with the write-safety choke point
    re-evaluated INDEPENDENTLY at each of FR-013's two boundaries (never
    cached, never inherited).

    ``pinned_baseline`` is a REQUIRED ``PinnedBaseline`` (T020): the restore
    goes through ``restore_from_pinned_baseline``, never through
    ``harness.restore_target``, so there is no newest-archive glob fallback
    on this path and every restored item's containment is proven before a
    byte is written.
    """
    if run_intent not in VALID_RUN_INTENTS:
        raise ValueError("run_intent must be one of %r" % (VALID_RUN_INTENTS,))
    if diagnostic_level not in DIAGNOSTIC_LEVELS:
        raise ValueError("diagnostic_level must be one of %r" % (DIAGNOSTIC_LEVELS,))
    if pinned_baseline is None:
        raise BaselineError(
            "[FR-170] run_one_project requires a pinned baseline. A run that "
            "cannot name and hash its baseline does not start."
        )

    from harness import full_run

    artifact = ProjectArtifact(
        project=source_name, run_intent=normalize_intent(run_intent), revision_pair=revision_pair(),
        dirty_gramtrans=None, coverage_categories=[], started_at=time.time(),
    )
    rp = artifact.revision_pair
    artifact.dirty_gramtrans = rp.get("gramtrans", {}).get("dirty")
    artifact.excluded_categories = list(exclude_categories)
    artifact.diagnostic_level = diagnostic_level
    artifact.baseline = pinned_baseline.as_dict()

    # FR-024: the per-project record that each assertion was IN FACT
    # evaluated, at which boundary, against which literal values.
    ledger = AssertionLedger(project=source_name)

    root = resolve_projects_root(projects_root)
    target_path = str(root / target_name)

    src_fp_before = capture_fingerprint(source_name, projects_root)
    artifact.source_fingerprint_before = asdict(src_fp_before)
    flush_artifact(artifact, artifacts_dir)

    try:
        # ---- boundary (a): pinned, contained restore --------------------
        # assert_restore_boundary fires INSIDE restore_from_pinned_baseline,
        # before the archive is even opened and long before the first removal
        # (FR-023's load-bearing ordering).
        restored = restore_from_pinned_baseline(
            target_name, pinned=pinned_baseline, source_name=source_name,
            frozen_sources=frozen_sources, allowlist=allowlist,
            projects_root=projects_root, tolerated_residue=tolerated_residue,
            ledger=ledger,
        )
        artifact.restore_evidence = restored.as_dict()
        artifact.phases_completed.append("restore_initial")
        advance_phase(artifact, "restore", artifacts_dir)

        census_before = census_project(target_name)
        artifact.census_before = {k: sorted(v) for k, v in census_before.items()}
        artifact.phases_completed.append("census_before")
        flush_artifact(artifact, artifacts_dir)  # still within the "restore" phase (T013)

        excluded = frozenset(exclude_categories)
        selection = full_run.build_full_selection(exclude=excluded)
        artifact.coverage_categories = sorted(c.value for c, on in selection.categories.items() if on)

        # ---- boundary (b): re-asserted immediately before the first byte
        # written beneath the target, computed fresh from the literal
        # target_name about to be used. An INDEPENDENT evaluation -- it
        # shares no flag with boundary (a) ------------------------------
        assert_first_write_boundary(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root, ledger=ledger,
        )
        plan1, report1 = full_run.run_full_transfer(source_name, target_name, target_path)
        artifact.phases_completed.append("first_transfer")
        advance_phase(artifact, "transfer_1", artifacts_dir)

        census_after_1 = census_project(target_name)
        artifact.census_after_first = {k: sorted(v) for k, v in census_after_1.items()}
        artifact.phases_completed.append("census_after_first")
        advance_phase(artifact, "census_1", artifacts_dir)

        written = written_classes(census_before, census_after_1)
        artifact.written_classes = written

        assert_first_write_boundary(
            target_name, source_name=source_name, frozen_sources=frozen_sources,
            allowlist=allowlist, projects_root=projects_root, ledger=ledger,
        )
        plan2, report2 = full_run.run_full_transfer(source_name, target_name, target_path)
        artifact.phases_completed.append("second_transfer")
        advance_phase(artifact, "transfer_2", artifacts_dir)

        census_after_2 = census_project(target_name)
        artifact.census_after_second = {k: sorted(v) for k, v in census_after_2.items()}
        artifact.phases_completed.append("census_after_second")
        advance_phase(artifact, "census_2", artifacts_dir)

        idem = check_idempotency(census_after_1, census_after_2, written)
        artifact.idempotency = asdict(idem)
        if idem.harness_error:
            raise HarnessError(idem.harness_error)

        source_inventory = census_project(source_name)
        artifact.findings = comparator(source_inventory, census_after_2)

        artifact.status = "passed" if (idem.passed and not artifact.findings) else "failed"
        artifact.reason = "" if artifact.status == "passed" else (
            idem.harness_error or "unresolved findings (see .findings) / idempotency divergence"
        )
    except Exception as exc:  # noqa: BLE001 -- recorded loudly, never swallowed
        artifact.status = "failed"
        artifact.reason = "%s: %s" % (type(exc).__name__, exc)
        artifact.errors.append({
            "phase": artifact.phases_completed[-1] if artifact.phases_completed else "setup",
            "error": artifact.reason,
            "traceback": traceback.format_exc(),
        })
        raise
    finally:
        # FR-050: restore the target to baseline and write the artifact even
        # on an unhandled failure. FR-172: recovery is idempotent per project
        # -- always restore, never resume mid-transfer.
        try:
            restored_final = restore_from_pinned_baseline(
                target_name, pinned=pinned_baseline, source_name=source_name,
                frozen_sources=frozen_sources, allowlist=allowlist,
                projects_root=projects_root, tolerated_residue=tolerated_residue,
                ledger=ledger,
            )
            artifact.restore_evidence_final = restored_final.as_dict()
            artifact.phases_completed.append("restore_final")
            artifact.phase_reached = "restore_final"
        except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
            artifact.errors.append({
                "phase": "restore_final", "error": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            })

        src_fp_after = capture_fingerprint(source_name, projects_root)
        artifact.source_fingerprint_after = asdict(src_fp_after)
        fp_verdict = classify_fingerprint_delta(src_fp_before, src_fp_after)
        artifact.fingerprint_verdict = fp_verdict
        if fp_verdict not in (FINGERPRINT_VERDICT_UNCHANGED, FINGERPRINT_VERDICT_MIGRATION):
            artifact.status = "failed"
            artifact.reason = ("SOURCE TAMPER GUARD: %s -- %s" % (fp_verdict, artifact.reason)).strip(" -")

        # ---- FR-024: the assertion record goes into the artifact, and both
        # FR-013 boundaries must have been independently evaluated. Recorded
        # BEFORE the check, so a run that failed the check still shows what
        # it did evaluate. -----------------------------------------------
        artifact.assertions = ledger.as_list()
        try:
            assert_both_boundaries_evaluated(ledger)
            artifact.assertions_complete = True
        except WriteSafetyError as exc:
            artifact.assertions_complete = False
            artifact.errors.append({
                "phase": artifact.phase_reached or "setup",
                "error": "%s: %s" % (type(exc).__name__, exc), "traceback": "",
            })
            artifact.status = "failed"
            artifact.reason = ("%s -- %s" % (exc, artifact.reason)).strip(" -")

        # ---- T016: wire registry -> verdict -> artifact -----------------
        # FR-109 meta-rule: asserted BOTH before the verdict is computed AND
        # again before the artifact is flushed. Every run reports VACUOUS
        # today because no guard in the registry has real pass/fail logic
        # yet (Phase 2 taxonomy-spine scope, T011-T014) -- that is the
        # correct answer for an instrument that cannot yet prove anything.
        guard_results = run_all_guards(RunContext(project=source_name))
        artifact.guards = guard_block_as_dict(guard_results)
        assert_guard_block_complete(artifact.guards)
        artifact.verdict = verdict_for_guard_results(guard_results)
        artifact.exit_code = exit_code_for(artifact.verdict)
        assert_guard_block_complete(artifact.guards)

        artifact.finished_at = time.time()
        flush_artifact(artifact, artifacts_dir)

    return artifact


# ===========================================================================
# CLI
# ===========================================================================

def _preflight_gate(args) -> Optional[int]:
    """FR-124/SC-008: performed ONCE at startup, BEFORE any restore or write.

    Returns an exit code when the run must refuse, or None to proceed. There
    is no third outcome: FR-132 forbids a best-effort degradation and FR-133
    forbids selecting a different runtime path around a mismatch.
    """
    result = run_preflight(Path(args.contracts_dir))
    if result.ok:
        return None
    print(format_diff_report(result, max_rows=getattr(args, "max_console_rows", None)))
    artifact_path = write_preflight_artifact(result, Path(args.artifacts_dir))
    print("[ARTIFACT] %s" % artifact_path)
    print("[REFUSED] capability preflight mismatch -- no project database was "
          "touched, no restore and no write attempted (SC-008).")
    return result.exit_code


def _pinned_baseline_from_args(args):
    """FR-170: build the pinned baseline from the caller's EXPLICIT --backup
    and --baseline-sha256. Absent both, the run has no baseline to pin and
    ``run_one_project`` refuses -- there is deliberately no fallback here
    that would select one."""
    if not getattr(args, "backup", None):
        return None
    return pin_baseline(args.backup, args.baseline_sha256)


def _cmd_list(args) -> int:
    corpus = enumerate_corpus(args.projects_root)
    admitted = [e for e in corpus if e.admitted]
    excluded = [e for e in corpus if not e.admitted]
    print("[INFO] admitted sources: %d" % len(admitted))
    for e in admitted:
        print("  %-38s %8.2f MB" % (e.project, e.fwdata_mb))
    print("[INFO] excluded: %d" % len(excluded))
    for e in excluded:
        print("  %-38s %s" % (e.project, e.reason))
    return 0


def _cmd_project(args) -> int:
    """Worker mode: run the full double-move loop for exactly ONE project,
    in THIS process (intended to be launched as a subprocess by the batch
    driver, per FR-026/FR-037/FR-038 -- one OS process, one log file, per
    project)."""
    corpus = enumerate_corpus(args.projects_root)
    frozen = freeze_source_manifest(corpus)
    if args.source not in frozen:
        # T013/T016: a project this run never attempts (excluded from the
        # frozen admitted-source manifest) MUST STILL get a written
        # artifact naming it SKIPPED (FR-151/FR-188) -- never a bare CLI
        # error with nothing recorded to back it. No FLEx project is
        # opened on this path.
        reason = ("[FR-004/FR-006] %r is not in the frozen admitted-source "
                  "manifest -- no work attempted" % (args.source,))
        print("[SKIP] %s" % reason)
        artifact_path = write_skipped_artifact(
            args.source, reason=reason, run_intent=args.intent,
            artifacts_dir=Path(args.artifacts_dir),
        )
        print("[ARTIFACT] %s" % artifact_path)
        print("[RESULT] %s -> %s (verdict=VACUOUS, exit=%d)"
              % (args.source, STATUS_SKIPPED, exit_code_for("VACUOUS")))
        return exit_code_for("VACUOUS")
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    refused = _preflight_gate(args)
    if refused is not None:
        return refused
    try:
        artifact = run_one_project(
            args.source, target_name=args.target, frozen_sources=frozen,
            allowlist=allowlist, run_intent=args.intent,
            pinned_baseline=_pinned_baseline_from_args(args),
            exclude_categories=args.exclude_categories,
            diagnostic_level=args.diagnostic_level,
            projects_root=args.projects_root,
            artifacts_dir=Path(args.artifacts_dir),
        )
    except (WriteSafetyError, SourceTamperError, EvidenceProvenanceError) as exc:
        # These MUST abort the whole run -- re-raise after making that loud.
        print("[ABORT-WHOLE-RUN] %s: %s" % (type(exc).__name__, exc))
        raise
    print("[RESULT] %s -> %s (verdict=%s, exit=%d)"
          % (args.source, artifact.status, artifact.verdict, artifact.exit_code))
    return artifact.exit_code


def _cmd_batch(args) -> int:
    """Driver mode skeleton: admits a batch of --batch-size projects,
    running each as an isolated subprocess (FR-026), gated by the memory
    admission check (FR-028) and the concurrency-trial gate (FR-032). This
    skeleton runs workers SERIALLY when --workers=1 (the FR-031 default);
    it refuses to do otherwise without a recorded concurrency-trial
    artifact (assert_concurrency_gate_satisfied)."""
    refused = _preflight_gate(args)
    if refused is not None:
        return refused
    # FR-149: the driver, the capability expectation and the ledger this
    # verdict will depend on must be tracked and un-ignored BEFORE any work.
    assert_evidence_base_tracked({
        EVIDENCE_KIND_DRIVER: [Path(__file__).resolve()],
        EVIDENCE_KIND_CAPABILITY: [Path(args.contracts_dir) / "flexicon-capability.json"],
    })
    assert_concurrency_gate_satisfied(args.workers)
    corpus = enumerate_corpus(args.projects_root)
    frozen = freeze_source_manifest(corpus)
    allowlist = tuple(args.allowlist) if args.allowlist else DEFAULT_ALLOWLIST
    target_pool = default_target_pool(args.workers)
    assert_distinct_target_pool(target_pool, frozen)

    manifest_fp = capture_source_manifest(frozen, args.projects_root)
    print("[INFO] captured fingerprints for %d frozen sources" % len(manifest_fp))

    ledger = Ledger(Path(args.ledger))  # FR-149: tracked, not a runtime artifact
    pending = [n for n in frozen if (ledger.get(n) or {}).get("status") != "passed"]
    if args.canary and args.canary not in pending:
        pending = [args.canary] + pending  # FR-159: canary re-runs every batch
    batch = pending[: args.batch_size]

    print("[INFO] batch of %d: %s" % (len(batch), ", ".join(batch)))
    exit_code = 0
    for i, source in enumerate(batch):
        target = target_pool[i % len(target_pool)]
        row = next((e for e in corpus if e.project == source), None)
        try:
            assert_memory_admits_project(source, row.fwdata_mb if row else 0.0)
        except MemoryShortfall as exc:
            print("[WAIT] %s: %s (admitting fewer workers / waiting is an "
                  "operational concern, NOT a safety abort)" % (source, exc))
            exit_code = exit_code or 3
            continue
        ledger.set_status(source, "running")
        worker_env = dict(os.environ)
        for ambient in ("GRAMTRANS_PROJECTS_ROOT",):
            worker_env.pop(ambient, None)
        worker_env["GRAMTRANS_PROJECTS_ROOT"] = str(resolve_projects_root(args.projects_root))
        cmd = [sys.executable, str(Path(__file__).resolve())]
        if args.projects_root:
            cmd += ["--projects-root", args.projects_root]
        cmd += ["--artifacts-dir", args.artifacts_dir, "--runtime-dir", args.runtime_dir,
                "--contracts-dir", args.contracts_dir, "--ledger", args.ledger,
                "project", "--source", source, "--target", target, "--intent", args.intent,
                "--exclude-categories", ",".join(args.exclude_categories),
                "--diagnostic-level", args.diagnostic_level]
        if args.backup:
            cmd += ["--backup", args.backup, "--baseline-sha256", args.baseline_sha256]
        log_dir = Path(args.runtime_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / ("%s.log" % re.sub(r"[^A-Za-z0-9._ -]", "_", source))
        with ExclusiveTargetClaim(target, Path(args.runtime_dir)):
            with open(log_path, "w", encoding="utf-8") as logf:
                cp = subprocess.run(cmd, env=worker_env, stdout=logf, stderr=subprocess.STDOUT)
        status = "passed" if cp.returncode == 0 else "failed"
        ledger.set_status(source, status, reason="" if status == "passed" else
                           "worker exited %d; see %s" % (cp.returncode, log_path),
                           revision_pair=revision_pair())
        if status != "passed":
            exit_code = 1
        print("[BATCH] %-38s %s (see %s)" % (source, status, log_path))

    print("\n[INFO] batch complete; stopping for analysis before any further "
          "batch is admitted (FR-153).")
    return exit_code


def _cmd_preflight(args) -> int:
    """T024/FR-124/SC-008: introspect the dependency against the pinned
    fingerprint and exit. Touches no database, performs no restore and no
    write. Exit 0 on match, 6 with a field-by-field diff on mismatch."""
    result = run_preflight(Path(args.contracts_dir))
    print(format_diff_report(result, max_rows=args.max_console_rows))
    artifact_path = write_preflight_artifact(result, Path(args.artifacts_dir))
    print("[ARTIFACT] %s" % artifact_path)
    return result.exit_code


class _ArgumentErrorExits5(argparse.ArgumentParser):
    """Contracts/sweep-cli.md, "Exit codes": there is no separate CLI-usage
    exit-code space. An argument error raises BEFORE any verdict exists and
    exits 5 (``HARNESS_ERROR``), since a run that could not be configured
    measured nothing.

    argparse's own default is exit 2, which collides with ``NON_IDEMPOTENT``
    -- a misconfigured invocation would otherwise be indistinguishable from a
    real second-transfer divergence in a batch driver reading exit codes.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("[HARNESS_ERROR] %s: %s\n" % (self.prog, message))
        raise SystemExit(exit_code_for("HARNESS_ERROR"))


def _split_categories(value: str) -> list:
    """``--exclude-categories`` is REQUIRED AND EXPLICIT, and may legitimately
    be EMPTY. An empty string therefore means "exclude nothing", stated
    deliberately -- never a default argument that silently excludes STEMS the
    way ``full_run.build_full_selection`` does on its own."""
    if value is None:
        raise argparse.ArgumentTypeError(
            "--exclude-categories must be given explicitly (pass '' to exclude "
            "nothing); it is never defaulted"
        )
    return [c.strip() for c in value.split(",") if c.strip()]


def main(argv=None) -> int:
    ap = _ArgumentErrorExits5(description=__doc__)
    ap.add_argument("--projects-root")
    ap.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR),
                     help="per-run result artifacts (evidence, not reviewed source)")
    ap.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
    ap.add_argument("--allowlist", nargs="*", default=None,
                     help="anchored regex patterns; default: this sweep's own "
                          "Target[0-9]* pool only")
    # ---- T024 NEW globals -------------------------------------------------
    ap.add_argument("--contracts-dir", default=str(DEFAULT_CONTRACTS_DIR),
                     help="where the tracked rosters, allowlist and capability "
                          "fingerprint are read from")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH),
                     help="the tracked per-project status ledger")
    ap.add_argument("--max-console-rows", type=int, default=None,
                     help="truncate CONSOLE listings only, always stating the "
                          "omitted count; the artifact never truncates (FR-144)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="enumerate the corpus")
    p_list.set_defaults(func=_cmd_list)

    p_preflight = sub.add_parser(
        "preflight", help="capability check: introspect the dependency against "
                          "the pinned fingerprint and exit (touches no database)")
    p_preflight.set_defaults(func=_cmd_preflight)

    p_project = sub.add_parser("project", help="worker mode: run one project")
    p_project.add_argument("--source", required=True)
    p_project.add_argument("--target", required=True)
    p_project.add_argument("--backup", default=None)
    p_project.add_argument("--baseline-sha256", default=None,
                            help="REQUIRED with --backup. A run that cannot name "
                                 "and hash its baseline does not start; there is "
                                 "no newest-archive glob fallback (FR-170)")
    p_project.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_project.add_argument("--exclude-categories", required=True,
                            type=_split_categories,
                            help="EXPLICIT, possibly empty (pass ''). A non-empty "
                                 "value forces COVERAGE_REDUCED")
    p_project.add_argument("--diagnostic-level", required=True,
                            choices=DIAGNOSTIC_LEVELS,
                            help="set explicitly and recorded; never setdefault "
                                 "from the environment")
    p_project.set_defaults(func=_cmd_project)

    p_batch = sub.add_parser("batch", help="driver mode: admit and run one batch")
    p_batch.add_argument("--batch-size", type=int, default=3)
    p_batch.add_argument("--workers", type=int, default=1)
    p_batch.add_argument("--canary", default=CANARY_PROJECTS[0])
    p_batch.add_argument("--intent", required=True, choices=VALID_RUN_INTENTS)
    p_batch.add_argument("--backup", default=None)
    p_batch.add_argument("--baseline-sha256", default=None)
    p_batch.add_argument("--exclude-categories", required=True,
                          type=_split_categories)
    p_batch.add_argument("--diagnostic-level", required=True,
                          choices=DIAGNOSTIC_LEVELS)
    p_batch.set_defaults(func=_cmd_batch)

    args = ap.parse_args(argv)

    # FR-170: --baseline-sha256 is required WITH --backup. Enforced here rather
    # than by argparse because argparse has no native "required-with" relation;
    # routing it through ap.error() keeps the exit code at 5 (HARNESS_ERROR).
    if getattr(args, "backup", None) and not getattr(args, "baseline_sha256", None):
        ap.error("--baseline-sha256 is REQUIRED with --backup (FR-170: a "
                  "baseline is pinned by content hash by the caller; the sweep "
                  "never selects one by recency or directory scan)")

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
