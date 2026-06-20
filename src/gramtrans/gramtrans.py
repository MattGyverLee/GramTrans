"""
GramTrans — additive grammar-piece transfer between FLEx projects.

FlexTools entry point (FLExTrans-style: docs dict + MainFunction). Helpers
live under sibling `Lib/`, loaded via `site.addsitedir(r"Lib")`.

Phase 0 (Additive) — see specs/001-phase0-additive-transfer/. Copies grammar
pieces (POS, affix templates, slots, affix entries with MSAs + allomorphs +
environments, ...) from a SOURCE project to the currently-open TARGET project.
FR-009 explicitly permits duplicates. New target objects are tagged with a
structured residue marker (`[GT-Tag]: GT|<run_id>|<source>|<iso_ts>`) for
later audit.

T-Spike (constitution v5.0.0 Principle III closing clause, 2026-06-19):
the inline Move logic that lived in the previous version of this file is now
split into:
  - Lib/preview.py   — plan builder (never mutates target)
  - Lib/transfer.py  — plan executor (the only Move-mode writer)
  - Lib/residue.py   — Import Residue tag + Carrier A/B dispatchers
  - Lib/report.py    — RunReport aggregation
  - Lib/types.py     — dataclasses (RunContext, RunPlan, RunReport, ...)
"""
from flextoolslib import *  # noqa: F401,F403 — FlexTools host names

import datetime
import os
import site

# Make `Lib/` importable per the FLExTrans module convention.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.join(_THIS_DIR, "Lib"))

# ============================================================================
# CRITICAL: explicit flexlibs2 imports (template-mandatory)
#
# FlexTools loads stable flexlibs by default; without explicit flexlibs2
# imports, FieldWorks silently uses the wrong (stable) wrappers and grammar
# coverage falls off. Requires the patched MattGyverLee/flexlibs2 fork — see
# CLAUDE.md "flexlibs2 fork dependency".
# ============================================================================
from flexlibs2 import (  # noqa: F401 — pinned for the patched fork
    FLExProject,
    POSOperations,
    MorphRuleOperations,
    LexEntryOperations,
    LexSenseOperations,
    AllomorphOperations,
    EnvironmentOperations,
    InflectionFeatureOperations,
)

# Helpers under Lib/ (resolved via site.addsitedir above).
from preview import build_run_plan
from transfer import execute
from residue import ImportResidueTag
from report import render_text_summary, to_snapshot_json
from models import (
    GrammarCategory,
    RunContext,
    RunMode,
    Selection,
    WSMapping,
)


__version__ = "0.1.0"


# ============================================================================
# Module metadata (FLExTrans convention — FlexTools reads this dict to render
# the module list entry)
# ============================================================================

docs = {
    FTM_Name       : "GramTrans — Additive Grammar Transfer",
    FTM_Version    : __version__,
    FTM_ModifiesDB : True,
    FTM_Synopsis   : "Copy grammar pieces from a toy source project into the host target.",
    FTM_Help       : "",
    FTM_Description:
"""
Phase 0 (Additive) of GramTrans. Reads the configured SOURCE project
(currently hard-coded to 'Ejagham Mini' — FR-002 target picker arrives in a
future iteration) and copies its Verb POS + affix templates + slots into the
currently-open TARGET project. New objects preserve source GUIDs and are
tagged with a structured residue marker of the form
`GT|<run_id>|<source>|<iso_ts>` — look in Residue (Lex* classes) or the
object's Description ([GT-Tag]: line) to find this run's additions.

Phase 0 is additive only: duplicates are permitted (FR-009). FLEx's Ctrl+Z
undoes the entire run.

See CLAUDE.md for the flexlibs2 fork install instructions and STATUS.md for
the latest session's validated work.
""",
}


# Hard-coded source project for the MVP. The PyQt picker (FR-002) replaces
# this in a future iteration.
DEFAULT_SOURCE_PROJECT = "Ejagham Mini"


# ============================================================================
# Entry point
# ============================================================================

def MainFunction(project, report, modifyAllowed):
    """Standard FlexTools entry.

    Args:
        project: FLExProject connected to the user's TARGET project (per
            FlexTools convention — `MainFunction`'s `project` is the host's
            currently-open project, which we treat as the SOURCE per
            Clarification Q2).
        report: report.Info / .Warning / .Error / .Blank for log output.
        modifyAllowed: True when FlexTools is running write-enabled.

    Phase 0 semantics: additive only. Each source piece becomes a new
    target object with the same GUID (FR-012). Duplicates allowed (FR-009).
    The FlexTools host wraps this call in a UOW (research.md R10), so
    `Ctrl+Z` once in FLEx undoes the entire run.

    UI scaffolding (T057): If PyQt is available, this opens the GramTrans
    PyQt main window dialog (FR-002 picker + category toggles + Preview/Move).
    Headless fallback (no PyQt available, or running under T-Spike step 3
    parity-verification scaffolding) runs the verb-vertical against
    `DEFAULT_SOURCE_PROJECT` directly.
    """
    try:
        run_id, started_at = _make_run_id()
        source_name = DEFAULT_SOURCE_PROJECT
        tag = ImportResidueTag.make(
            run_id=run_id,
            source_project_name=source_name,
            timestamp=started_at,
        )

        report.Info(f"[GramTrans] Phase 0 additive transfer  run_id={run_id}")
        report.Info(f"  Source: {source_name!r}")
        report.Info(f"  Target: {project.ProjectName()!r}")
        report.Info(f"  Mode:   {'MOVE' if modifyAllowed else 'PREVIEW (read-only)'}")
        report.Info(f"  Tag:    {tag.serialize()}")
        report.Blank()

        source = FLExProject()
        source.OpenProject(projectName=source_name, writeEnabled=False)
        try:
            context = RunContext(
                source_handle=source,
                source_project_name=source_name,
                source_project_path=_safe_project_path(source),
                target_handle=project,
                target_project_name=project.ProjectName(),
                target_project_path=_safe_project_path(project),
                run_id=run_id,
                started_at=started_at,
            )

            # MVP: the Selection / WSMapping UI doesn't exist yet (T055, T057).
            # For the T-Spike parity run we hard-code the equivalent of the
            # spike's "all-Verb-vertical" selection.
            selection = Selection(
                categories={
                    GrammarCategory.POS: True,
                    GrammarCategory.TEMPLATES: True,
                    GrammarCategory.SLOTS: True,
                },
                include_closure=True,
            )
            ws_mapping = WSMapping(entries=())  # identity-only until FR-011 lands

            # Preview (never mutates target) — Principle III gate.
            plan = build_run_plan(context, selection, ws_mapping, source, project)
            report.Info(f"[Preview]  actions={len(plan.actions)}  skips={len(plan.skips)}")
            for a in plan.actions:
                report.Info(f"  + {a.category.value:10s} {a.source_guid}  {a.summary}")
            for s in plan.skips:
                report.Info(f"  - {s.category.value:10s} {s.source_guid}  {s.reason.value}: {s.detail}")
            report.Blank()

            if not modifyAllowed:
                report.Info("(Preview-only run: no writes performed.)")
                return

            # Move — the only mutating call path.
            run_report = execute(plan, source, project, report, tag)

            report.Blank()
            for line in render_text_summary(run_report):
                report.Info(line)

        finally:
            source.CloseProject()

    except Exception as e:  # noqa: BLE001 — FlexTools silences raw exceptions
        report.Error(f"[GramTrans] Fatal: {e}")
        import traceback
        report.Error(traceback.format_exc())


# ============================================================================
# Utilities
# ============================================================================

def _make_run_id() -> "tuple[str, str]":
    now = datetime.datetime.now()
    return (
        "GT-" + now.strftime("%Y%m%d-%H%M%S"),
        now.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _safe_project_path(flex_project) -> str:
    """Best-effort retrieval of a FLExProject's on-disk path. flexlibs2 doesn't
    expose this directly; fall back to an empty string so RunContext construction
    doesn't blow up when introspection isn't available."""
    for attr in ("ProjectPath", "ProjectFilename", "ProjectFolder"):
        try:
            v = getattr(flex_project, attr)
            return v() if callable(v) else str(v)
        except Exception:
            continue
    return ""
