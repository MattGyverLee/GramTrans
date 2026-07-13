"""End-to-end plan/preview/execute + re-run tests for feature 031.

Fix Inflection-Feature Linking to Grammatical Categories.

Scaffold (T002): test class skeletons and pytest imports only — no assertions
yet. The tests below are authored in Phase 3 (US1, T006-T008, T013) and Phase 5
(US3, T019) per specs/031-fix-inflection-feature-linking/tasks.md. They MUST be
written to FAIL before the corresponding implementation lands.

Contracts under test:
- C1  link gathering (COUNT / NO-WRITE / DEDUP)
- C2  wiring post-pass (IDEMPOTENT / DEFERRED-NOT-DANGLING / ORDER-INDEPENDENT /
      REPORTED)
- diagnosis-report  (COMPLETE / READ-ONLY)
"""
from __future__ import annotations

import pytest


# ============================================================================
# US1 — feature->category link (T006-T008, T013)
# ============================================================================

class TestLinkGathering:
    """C1 — plan-time link gathering from source POS.InflectableFeatsRC."""


class TestWiringPostPass:
    """C2 — Move-time wiring post-pass (_run_infl_feature_link_pass)."""


class TestSkipReporting:
    """T013 — emitted Skips surface in the post-run statistics panel."""


# ============================================================================
# US3 — read-only diagnosis (T019)
# ============================================================================

class TestDiagnosisReport:
    """diagnosis-report — report shape + COMPLETE classification."""
