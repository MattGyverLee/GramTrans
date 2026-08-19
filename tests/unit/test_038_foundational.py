"""Feature 038 (transfer fidelity gaps) -- Phase 2 foundational layer.

Covers T013: every new dataclass rejects its invalid states; the roster
accessor returns no-basis for an absent class and raises for an off-roster
class reaching the natural-key step; `build_run_plan` raises on an unverified
closure edge; and the empty registry changes no existing plan.

These are deliberately invariant tests, not behaviour tests -- Phase 2 changes
no behaviour. The property being pinned is that the foundational types make
invalid states UNCONSTRUCTIBLE, because a silently-wrong identity match or an
unaudited dependency edge is the exact defect class this feature exists to
remove.
"""
import json

import pytest

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.models import (
    CategoryReport,
    ClosureEdge,
    DependencyKind,
    EnrichedCollection,
    EnrichmentRecord,
    GrammarCategory,
    IncompletenessRecord,
    MatchBasis,
    MatchBasisRecord,
    NaturalKeyRosterEntry,
    PlannedAction,
    PlannedOverwrite,
    ProcessRuleTransferRecord,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Skip,
    SkipReason,
)

SRC = (GrammarCategory.AFFIXES, "guid-affix-1")
DEP = (GrammarCategory.GRAM_CATEGORIES, "guid-pos-1")


def _ctx():
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path=r"C:\p\Src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path=r"C:\p\Tgt",
        run_id="GT-20260819-000000",
        started_at="2026-08-19T00:00:00",
    )


# ---------------------------------------------------------------------------
# MatchBasisRecord -- identity accounting
# ---------------------------------------------------------------------------

class TestMatchBasisRecord:
    def test_identity_match_is_accepted(self):
        rec = MatchBasisRecord(
            basis=MatchBasis.IDENTITY, object_class="PhPhoneme",
            source_guid="s", target_guid="t")
        assert rec.basis is MatchBasis.IDENTITY
        assert rec.candidate_count == 0

    def test_none_basis_must_have_empty_target_guid(self):
        MatchBasisRecord(basis=MatchBasis.NONE, object_class="PhPhoneme",
                         source_guid="s")
        with pytest.raises(ValueError, match="empty target_guid"):
            MatchBasisRecord(basis=MatchBasis.NONE, object_class="PhPhoneme",
                             source_guid="s", target_guid="t")

    def test_non_none_basis_requires_target_guid(self):
        with pytest.raises(ValueError, match="non-empty target_guid"):
            MatchBasisRecord(basis=MatchBasis.IDENTITY,
                             object_class="PhPhoneme", source_guid="s")

    def test_natural_key_must_carry_the_key_it_matched_on(self):
        with pytest.raises(ValueError, match="key_expression"):
            MatchBasisRecord(basis=MatchBasis.NATURAL_KEY,
                             object_class="PhPhoneme", source_guid="s",
                             target_guid="t")
        with pytest.raises(ValueError, match="key_value"):
            MatchBasisRecord(basis=MatchBasis.NATURAL_KEY,
                             object_class="PhPhoneme", source_guid="s",
                             target_guid="t", key_expression="Name")

    @pytest.mark.parametrize("kwargs,match", [
        (dict(object_class="", source_guid="s", target_guid="t"),
         "object_class"),
        (dict(object_class="X", source_guid="", target_guid="t"),
         "source_guid"),
        (dict(object_class="X", source_guid="s", target_guid="t",
              candidate_count=-1), "candidate_count"),
    ])
    def test_invalid_states_rejected(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            MatchBasisRecord(basis=MatchBasis.IDENTITY, **kwargs)


# ---------------------------------------------------------------------------
# ClosureEdge / IncompletenessRecord
# ---------------------------------------------------------------------------

class TestClosureEdge:
    def test_verified_edge_must_name_its_evidence(self):
        """FR-018: asserting 'verified' without naming what verified it is
        exactly the unaudited claim the gate exists to reject."""
        with pytest.raises(ValueError, match="verified_by"):
            ClosureEdge(dependent=SRC, dependency=DEP,
                        kind=DependencyKind.AFFIX_TO_POS,
                        verified=True, origin="pulled_in")

    def test_verified_edge_with_evidence_is_accepted(self):
        edge = ClosureEdge(dependent=SRC, dependency=DEP,
                           kind=DependencyKind.AFFIX_TO_POS, verified=True,
                           origin="pulled_in", verified_by="T013")
        assert edge.verified_by == "T013"

    def test_unverified_edge_needs_no_evidence(self):
        edge = ClosureEdge(dependent=SRC, dependency=DEP,
                           kind=DependencyKind.AFFIX_TO_POS, verified=False,
                           origin="chosen")
        assert edge.verified is False

    @pytest.mark.parametrize("origin", ["", "maybe", "seed"])
    def test_origin_is_constrained(self, origin):
        with pytest.raises(ValueError, match="origin"):
            ClosureEdge(dependent=SRC, dependency=DEP,
                        kind=DependencyKind.AFFIX_TO_POS, verified=False,
                        origin=origin)

    def test_refs_must_be_pairs_with_a_guid(self):
        with pytest.raises(ValueError, match="dependent"):
            ClosureEdge(dependent=(GrammarCategory.AFFIXES,), dependency=DEP,
                        kind=DependencyKind.AFFIX_TO_POS, verified=False,
                        origin="chosen")
        with pytest.raises(ValueError, match="non-empty guid"):
            ClosureEdge(dependent=(GrammarCategory.AFFIXES, ""),
                        dependency=DEP,
                        kind=DependencyKind.AFFIX_TO_POS, verified=False,
                        origin="chosen")


class TestIncompletenessRecord:
    def test_cause_is_constrained(self):
        with pytest.raises(ValueError, match="cause"):
            IncompletenessRecord(SRC, "affix", DEP, "pos", "invented", "x")

    def test_consequence_is_required(self):
        """A record the user cannot act on is not a report (SC-010)."""
        with pytest.raises(ValueError, match="consequence"):
            IncompletenessRecord(SRC, "affix", DEP, "pos", "deselected", "")

    @pytest.mark.parametrize("cause", ["deselected", "unsatisfiable", "cycle"])
    def test_valid_causes_accepted(self, cause):
        rec = IncompletenessRecord(SRC, "affix", DEP, "pos", cause, "loses X")
        assert rec.cause == cause


# ---------------------------------------------------------------------------
# Enrichment -- add-only by construction
# ---------------------------------------------------------------------------

class TestEnrichment:
    def _enr(self, **kw):
        base = dict(object_class="PartOfSpeech", source_guid="s",
                    target_guid="t", label="Noun")
        base.update(kw)
        return EnrichmentRecord(**base)

    def test_was_created_must_be_false(self):
        with pytest.raises(ValueError, match="was_created"):
            self._enr(was_created=True)

    def test_is_empty_detects_a_no_op_enrichment(self):
        assert self._enr().is_empty is True
        assert self._enr(
            collections=(EnrichedCollection("AffixSlotsOC", added=0),)
        ).is_empty is True
        assert self._enr(
            collections=(EnrichedCollection("AffixSlotsOC", added=1),)
        ).is_empty is False
        assert self._enr(fields_updated=("Name",)).is_empty is False

    def test_enrichment_forces_merge_write_mode(self):
        """FR-021: enrichment is add-only. An enrichment carried on an
        overwrite-mode write could blank destination content the user still
        has, so it must not be constructible."""
        with pytest.raises(ValueError, match="write_mode='merge'|write_mode"):
            PlannedOverwrite(category=GrammarCategory.GRAM_CATEGORIES,
                             source_guid="s", target_guid="t", summary="x",
                             enrichment=self._enr())
        ok = PlannedOverwrite(category=GrammarCategory.GRAM_CATEGORIES,
                              source_guid="s", target_guid="t", summary="x",
                              write_mode="merge", enrichment=self._enr())
        assert ok.enrichment is not None

    def test_negative_collection_counts_rejected(self):
        with pytest.raises(ValueError):
            EnrichedCollection("AffixSlotsOC", added=-1)


# ---------------------------------------------------------------------------
# Process rules -- never silently downgraded
# ---------------------------------------------------------------------------

class TestProcessRuleTransferRecord:
    def test_non_reproduction_must_be_explained(self):
        with pytest.raises(ValueError, match="not_reproducible_reason"):
            ProcessRuleTransferRecord(source_guid="s", reproduced=False)

    def test_reproduction_must_name_its_target(self):
        with pytest.raises(ValueError, match="target_guid"):
            ProcessRuleTransferRecord(source_guid="s", reproduced=True)

    def test_explained_non_reproduction_is_accepted(self):
        rec = ProcessRuleTransferRecord(
            source_guid="s", reproduced=False,
            not_reproducible_reason="no reproducible form")
        assert rec.not_reproducible_reason


# ---------------------------------------------------------------------------
# RunReport accounting -- counters cannot drift from their records
# ---------------------------------------------------------------------------

class TestRunReportAccounting:
    def _report(self, per_cat, skips=(), enrichments=()):
        return RunReport(context=_ctx(), mode=RunMode.PREVIEW,
                         per_category=per_cat, skips=skips,
                         enrichments=enrichments)

    def test_enriched_counter_must_match_enrichment_records(self):
        with pytest.raises(ValueError, match="enriched"):
            self._report({GrammarCategory.GRAM_CATEGORIES:
                          CategoryReport(enriched=1)})

    def test_enriched_counter_reconciles(self):
        enr = EnrichmentRecord(object_class="PartOfSpeech", source_guid="s",
                               target_guid="t", label="Noun")
        rep = self._report(
            {GrammarCategory.GRAM_CATEGORIES: CategoryReport(enriched=1)},
            enrichments=(enr,))
        assert len(rep.enrichments) == 1

    def test_not_reproducible_counter_must_match_skip_records(self):
        skip = Skip(category=GrammarCategory.PHONOLOGICAL_RULES,
                    source_guid="s", reason=SkipReason.NOT_REPRODUCIBLE,
                    detail="no form")
        with pytest.raises(ValueError, match="not_reproducible"):
            self._report({GrammarCategory.PHONOLOGICAL_RULES:
                          CategoryReport(skipped=1, not_reproducible=0)},
                         skips=(skip,))

    def test_derived_properties(self):
        rep = self._report({GrammarCategory.GRAM_CATEGORIES:
                            CategoryReport(identity_substitution=3)})
        assert rep.identity_substituted == 3
        assert rep.has_incomplete_items is False
        assert rep.rules_not_reproduced == ()

    def test_new_buckets_default_empty_so_old_snapshots_stay_valid(self):
        rep = self._report({})
        assert rep.closure_edges == ()
        assert rep.incompleteness == ()
        assert rep.enrichments == ()
        assert rep.process_rules == ()
        assert rep.census is None


# ---------------------------------------------------------------------------
# The roster accessor (R1) -- degrade for absent, RAISE for off-roster
# ---------------------------------------------------------------------------

class TestNaturalKeyRoster:
    def teardown_method(self):
        matcher_mod.reset_natural_key_roster_cache(None)

    def test_absent_class_has_no_natural_key_basis(self):
        """A class the roster does not admit is NOT an error -- the engine
        degrades to GUID-only matching for it."""
        assert matcher_mod.natural_key_roster_entry_for(
            "NoSuchLcmClass") is None

    def test_off_roster_class_reaching_the_matching_step_raises(self):
        with pytest.raises(matcher_mod.NaturalKeyRosterHarnessError) as exc:
            matcher_mod.require_natural_key_roster_entry("NoSuchLcmClass")
        assert "NoSuchLcmClass" in str(exc.value)

    def test_real_roster_file_loads_without_raising(self):
        matcher_mod.natural_key_roster_entry_for("PhPhoneme")

    def test_missing_roster_file_degrades_to_empty(self, tmp_path):
        matcher_mod.reset_natural_key_roster_cache(
            str(tmp_path / "absent.json"))
        assert matcher_mod.natural_key_roster_entry_for("PhPhoneme") is None

    def test_malformed_roster_degrades_to_empty(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        matcher_mod.reset_natural_key_roster_cache(str(bad))
        assert matcher_mod.natural_key_roster_entry_for("PhPhoneme") is None

    def test_a_complete_row_projects_and_is_admitted(self, tmp_path):
        roster = tmp_path / "roster.json"
        roster.write_text(json.dumps({
            "schema_version": 1,
            "entries": [{
                "class": "PhPhoneme",
                "natural_key": "Name (default vernacular WS)",
                "key_unique_by_construction": True,
                "on_ambiguous_key": "harness_error",
                "reason": "live-confirmed",
                "key_fn_id": "phoneme_name_key",
                "scope_fn_id": "project_phoneme_scope",
            }],
        }), encoding="utf-8")
        matcher_mod.reset_natural_key_roster_cache(str(roster))
        entry = matcher_mod.natural_key_roster_entry_for("PhPhoneme")
        assert isinstance(entry, NaturalKeyRosterEntry)
        assert entry.key_fn_id == "phoneme_name_key"
        assert matcher_mod.require_natural_key_roster_entry("PhPhoneme")

    def test_row_without_key_fn_id_is_not_executable(self, tmp_path):
        """key_fn_id is what makes a roster row executable. Without it the
        row cannot drive matching, so the class has no natural-key basis --
        this is the state 035's three live entries are in today."""
        roster = tmp_path / "roster.json"
        roster.write_text(json.dumps({
            "schema_version": 1,
            "entries": [{
                "class": "PhPhoneme",
                "natural_key": "Name",
                "key_unique_by_construction": True,
                "on_ambiguous_key": "harness_error",
                "reason": "live-confirmed",
            }],
        }), encoding="utf-8")
        matcher_mod.reset_natural_key_roster_cache(str(roster))
        assert matcher_mod.natural_key_roster_entry_for("PhPhoneme") is None


class TestNaturalKeyRosterEntryType:
    @pytest.mark.parametrize("missing", [
        "object_class", "natural_key", "on_ambiguous_key", "reason",
        "key_fn_id",
    ])
    def test_required_fields_rejected_when_empty(self, missing):
        kwargs = dict(object_class="PhPhoneme", natural_key="Name",
                      key_unique_by_construction=True,
                      on_ambiguous_key="harness_error", reason="r",
                      key_fn_id="k")
        kwargs[missing] = ""
        with pytest.raises(ValueError, match=missing):
            NaturalKeyRosterEntry(**kwargs)


# ---------------------------------------------------------------------------
# The closure registry ships empty and is inert (R3, FR-018)
# ---------------------------------------------------------------------------

class TestClosureRegistryShipsEmpty:
    def test_registry_is_empty_at_rest(self):
        """Emptiness IS the safety property: nothing registered means no
        producer's unaudited edge set can reach a plan."""
        assert categories_mod.CLOSURE_EDGES_VERIFIED == {}

    def test_callable_returns_nothing_for_every_category(self):
        dep_fn = categories_mod.closure_dependencies_for(_ctx())
        for cat in GrammarCategory:
            assert dep_fn(cat, "any-guid") == ()

    def test_registry_rejects_an_entry_without_evidence(self):
        bad = {
            DependencyKind.AFFIX_TO_POS: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": None,
                "verified_by": "",
            }
        }
        with pytest.raises(ValueError):
            categories_mod.closure_dependencies_for(_ctx(), registry=bad)


class TestBuildRunPlanClosureGate:
    """FR-018: `build_run_plan` must RAISE on an unverified edge rather than
    plan from it."""

    def test_empty_registry_materialises_no_edges(self):
        assert preview_mod._materialise_closure_edges(
            visit_order=(SRC,), pulled_in_by={SRC: ()}, registry={}) == ()

    def test_unverified_edge_raises(self):
        registry = {
            DependencyKind.AFFIX_TO_POS: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": GrammarCategory.GRAM_CATEGORIES,
                "verified_by": "some-probe",
                "verified": False,
            }
        }
        with pytest.raises(ValueError, match="UNVERIFIED"):
            preview_mod._materialise_closure_edges(
                visit_order=(SRC, DEP),
                pulled_in_by={SRC: (), DEP: (SRC,)},
                registry=registry)

    def test_verified_edge_materialises(self):
        registry = {
            DependencyKind.AFFIX_TO_POS: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": GrammarCategory.GRAM_CATEGORIES,
                "verified_by": "tests/unit/test_038_foundational.py",
            }
        }
        edges = preview_mod._materialise_closure_edges(
            visit_order=(SRC, DEP),
            pulled_in_by={SRC: (), DEP: (SRC,)},
            registry=registry)
        assert len(edges) == 1
        assert edges[0].kind is DependencyKind.AFFIX_TO_POS
        assert edges[0].origin == "pulled_in"
        assert edges[0].verified_by.endswith("test_038_foundational.py")

    def test_seed_is_never_reported_as_pulled_in(self):
        """closure.walk's seed semantics: an item the user picked directly
        is 'chosen', never 'pulled_in by' something else."""
        registry = {
            DependencyKind.AFFIX_TO_POS: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": GrammarCategory.GRAM_CATEGORIES,
                "verified_by": "probe",
            }
        }
        edges = preview_mod._materialise_closure_edges(
            visit_order=(SRC, DEP),
            pulled_in_by={SRC: (), DEP: (SRC,)},
            registry=registry)
        assert [e.origin for e in edges] == ["pulled_in"]

    def test_ambiguous_registry_raises(self):
        """Two kinds claiming one category pair means an edge's kind cannot
        be determined; guessing would file it under another relationship's
        verified_by."""
        registry = {
            DependencyKind.AFFIX_TO_POS: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": GrammarCategory.GRAM_CATEGORIES,
                "verified_by": "a",
            },
            DependencyKind.AFFIX_TO_SLOT: {
                "category": GrammarCategory.AFFIXES,
                "producer": lambda piece: (),
                "dependency_category": GrammarCategory.GRAM_CATEGORIES,
                "verified_by": "b",
            },
        }
        with pytest.raises(ValueError, match="ambiguous"):
            preview_mod._materialise_closure_edges(
                visit_order=(SRC, DEP),
                pulled_in_by={SRC: (), DEP: (SRC,)},
                registry=registry)


class TestEmptyRegistryChangesNoPlan:
    def test_plan_carries_no_closure_edges_by_default(self):
        """The whole Phase 2 safety claim in one assertion: with the shipped
        registry, a plan's closure contribution is empty."""
        plan = RunPlan(context=_ctx(), selection=None, ws_mapping=None)
        assert plan.closure_edges == ()

    def test_walk_helper_short_circuits_on_empty_registry(self):
        action = PlannedAction(category=GrammarCategory.AFFIXES,
                               source_guid="g", intended_target_guid="t",
                               summary="x")
        assert preview_mod._walk_verified_closure(
            _ctx(), None, [action], []) == ()
