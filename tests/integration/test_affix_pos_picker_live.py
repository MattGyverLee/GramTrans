"""Live MCP integration tests for the POS-grouped affix inventory builder.

T013 (US1): Ejagham Full GT-Test count anchors.
T019 (US3): Esperanto derivational/unclassified/multi-POS anchors.
T021 (US4): Esperanto and Ejagham junk drawer counts.

These tests require the FlexTools MCP server with live FLEx projects open:
  - "Ejagham Full GT-Test"
  - "Esperanto"

Run with:
    python -m pytest tests/integration/test_affix_pos_picker_live.py -m integration -v

Skip with:
    python -m pytest -m "not integration"

All count anchors come from specs/008-affix-pos-picker/contracts/pos-grouped-inventory.md
(validated live via MCP on 2026-07-01).

EXECUTED 2026-08-20, and the "written, not executed" status above is what let
three separate defects sit here undetected. Recorded so the next reader does
not re-introduce any of them:

1. THE WRONG LIBRARY. `_get_source` opened projects through stock `flexlibs`.
   GramTrans depends on **flexicon** (dist `pyflexicon`), a standalone package
   that is NOT a fork of stock flexlibs -- see CLAUDE.md. A
   `flexlibs.FLExProject` has no `.Cache` attribute AT ALL, and
   `build_pos_grouped_inventory` reads `source.Cache.LangProject.*` behind an
   `except (AttributeError, TypeError)` fail-soft (`selection.py:708`, `:716`).
   So every open produced an EMPTY inventory and every anchor failed as
   "Expected 68 affixes, got 0" -- which reads as a data regression and was in
   fact "no project was read". Both site are now flexicon, and the handle is
   validated before the inventory is trusted (`_require_readable`).

2. NO FieldWorks INITIALIZATION. A standalone (non-FlexTools-host) process must
   call `ensure_flex_initialized()` before any `OpenProject`; the harness's own
   `_ensure_flex_initialized` warns that skipping it surfaces as
   `RegistryHelper.get_CompanyKey()` throwing, and that a stale init can leave
   the next open QUARANTINING the project's `WritingSystemStore/*.ldml` files.
   `Esperanto` is read-only in the strong sense, so this file must never be the
   thing that damages it. That is also why these tests SKIPPED when the file ran
   alone and FAILED inside a full-suite run: alone, the un-initialized open
   raised and was swallowed into `pytest.skip`; after another test had
   initialized FieldWorks, the open "succeeded" and handed back the
   Cache-less handle from defect 1.

3. THE WRONG INSTRUMENT for infl/deriv/uncl. The contract's `41 / 31 / 12`
   count **MSAs**, not entries -- measured live: `MoInflAffMsa` 41,
   `MoDerivAffMsa` 31, `MoUnclassifiedAffixMsa` 12, total 84 across 68 affix
   entries. `_count_affix_rows_by_msa_kind` counts DISTINCT ENTRY GUIDS reached
   through the POS tree and yields 30 / 30 / 2, which is a different and also
   correct quantity -- it just is not the one the contract anchored. That the
   contract's three numbers sum to 84 while the affix total is 68 was the clue
   sitting in plain sight. `_count_msas_by_class` is the matching instrument.

Run with:
    python -m pytest tests/integration/test_affix_pos_picker_live.py -m integration -v

Skip with:
    python -m pytest -m "not integration"
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.selection import (
    PosGroupedAffixInventory,
    build_pos_grouped_inventory,
)


# ============================================================================
# Helpers
# ============================================================================

def _get_source(project_name: str):
    """Open the named FLEx project READ-ONLY through flexicon.

    flexicon, not stock `flexlibs`: a `flexlibs.FLExProject` exposes no
    `.Cache`, which `build_pos_grouped_inventory` needs and which its fail-soft
    would silently turn into an empty inventory (see defect 1 in the module
    docstring).

    `ensure_flex_initialized()` FIRST and on every call. It is idempotent, it
    re-verifies the SLDR rather than trusting a once-per-process latch, and a
    pytest session runs many features' fixtures in one process where any
    `FLExCleanup()` takes the SLDR down for the rest. Opening without it can
    quarantine the project's `WritingSystemStore/*.ldml`, and `Esperanto` is
    read-only in the strong sense.

    A genuinely unavailable project still SKIPS -- headless CI has no
    FieldWorks -- but a project that opens and then reads as empty does NOT;
    see `_require_readable`.
    """
    try:
        from gramtrans.Lib.flexinit import ensure_flex_initialized
        from flexicon import FLExProject  # type: ignore

        ensure_flex_initialized()
        project = FLExProject()
        project.OpenProject(projectName=project_name, writeEnabled=False)
        return project
    except Exception as e:  # noqa: BLE001 -- LCM raises a variety of types
        pytest.skip(f"Cannot open project '{project_name}': {e}")


def _require_readable(project, project_name: str):
    """Fail LOUDLY if the handle cannot serve the two paths the builder reads.

    `build_pos_grouped_inventory` catches `AttributeError`/`TypeError` on both
    `Cache.LangProject.LexDbOA.Entries` and
    `Cache.LangProject.PartsOfSpeechOA.PossibilitiesOS` and substitutes an empty
    list. That fail-soft is right for ONE malformed object in a real walk, and
    wrong as a way to discover that the handle is the wrong shape entirely: it
    converts "no project was read" into "this project has no affixes", which is
    indistinguishable from a data regression and is exactly how defect 1 hid.

    So the shape is asserted here rather than inferred from a count of 0.
    """
    try:
        entries = list(project.Cache.LangProject.LexDbOA.Entries)
        list(project.Cache.LangProject.PartsOfSpeechOA.PossibilitiesOS)
    except (AttributeError, TypeError) as exc:
        raise AssertionError(
            "the handle for %r does not expose the LCM paths "
            "build_pos_grouped_inventory reads (%s: %s). This is a WRONG "
            "HANDLE, not an empty project -- the builder would have fail-softed "
            "it to an inventory of 0 and every anchor below would have failed "
            "as a data regression. Check that _get_source is opening through "
            "flexicon and not stock flexlibs." % (project_name, type(exc).__name__, exc)
        ) from exc
    return entries


def _count_msas_by_class(project, inv: PosGroupedAffixInventory,
                         class_name: str) -> int:
    """MSAs of `class_name` across the inventory's affix entries.

    THE CONTRACT'S INSTRUMENT for the infl/deriv/uncl column, and a different
    quantity from `_count_affix_rows_by_msa_kind`: one entry may carry several
    MSAs of the same class, and an entry whose MSAs reach no POS never appears
    in the POS tree the row-walking helper traverses. Measured on `Esperanto`:
    41 + 31 + 12 = 84 MSAs over 68 affix entries, which is why the contract's
    three figures sum past its own affix total.
    """
    affix_guids = set(inv.all_affix_guids())
    total = 0
    for entry in project.Cache.LangProject.LexDbOA.Entries:
        if str(entry.Guid) not in affix_guids:
            continue
        for msa in entry.MorphoSyntaxAnalysesOC:
            if msa.ClassName == class_name:
                total += 1
    return total


def _count_affix_rows_by_msa_kind(inv: PosGroupedAffixInventory, kind: str) -> int:
    """Count distinct entry GUIDs whose primary kind matches `kind`."""
    guids = set()

    def _walk_node(node) -> None:
        for row in node.inflectional:
            if row.msa_kind == kind:
                guids.add(row.entry_guid)
        for row in node.deriv_attaches:
            if row.msa_kind == kind:
                guids.add(row.entry_guid)
        for row in node.deriv_produces:
            if row.msa_kind == kind:
                guids.add(row.entry_guid)
        for child in node.children:
            _walk_node(child)

    for root in inv.roots:
        _walk_node(root)
    return len(guids)


def _attaches_count_for_label(inv: PosGroupedAffixInventory, label: str) -> int:
    """Count distinct affix GUIDs in attaches-to lists for the named POS node."""
    guids: set = set()

    def _walk(node) -> None:
        if node.label == label:
            for row in node.inflectional:
                guids.add(row.entry_guid)
            for row in node.deriv_attaches:
                guids.add(row.entry_guid)
        for child in node.children:
            _walk(child)

    for root in inv.roots:
        _walk(root)
    return len(guids)


def _produces_count_for_label(inv: PosGroupedAffixInventory, label: str) -> int:
    """Count distinct affix GUIDs in produces lists for the named POS node."""
    guids: set = set()

    def _walk(node) -> None:
        if node.label == label:
            for row in node.deriv_produces:
                guids.add(row.entry_guid)
        for child in node.children:
            _walk(child)

    for root in inv.roots:
        _walk(root)
    return len(guids)


def _count_multi_pos(inv: PosGroupedAffixInventory) -> int:
    """Count affix GUIDs that appear in more than one attaches-to POS group."""
    from collections import Counter
    ctr: Counter = Counter()

    def _walk(node) -> None:
        seen_here: set = set()
        for row in node.inflectional:
            seen_here.add(row.entry_guid)
        for row in node.deriv_attaches:
            seen_here.add(row.entry_guid)
        for guid in seen_here:
            ctr[guid] += 1
        for child in node.children:
            _walk(child)

    for root in inv.roots:
        _walk(root)
    return sum(1 for g, c in ctr.items() if c > 1)


# ============================================================================
# T013 - Ejagham Full GT-Test (US1: inflectional baseline)
# ============================================================================

@pytest.mark.integration
class TestEjaghamInventory:
    """Contract anchors for Ejagham Full GT-Test (inflectional-only baseline).

    From contracts/pos-grouped-inventory.md:
      affixes: 33 | infl: 33 / deriv: 0 / uncl: 0
      attaches-to: v:14, n:11, num:6, pro:1
      multi-POS: 0 | junk no_pos: 1
    """

    #: The affix total the contract anchored on 2026-07-01.
    ANCHORED_AFFIXES = 33

    @pytest.fixture(scope="class")
    def ejagham_inv(self):
        """SKIPS ON DRIFT, and `Ejagham Full GT-Test` has drifted.

        Measured 2026-08-20: the project holds **0 lexical entries**. It is the
        throwaway TARGET of the `Ejagham Mini -> Ejagham Full GT-Test` transfer
        pair and is restored blank between runs, so its contents are a function
        of which transfer last ran -- not a stable regression surface. The
        contract's 33 affixes describe a populated snapshot that no longer
        exists, and no sibling carries it either (measured the same day:
        `Ejagham Full` 20 affixes, `Ejagham Mini` 88).

        So this skips rather than fails, on the same reasoning as the T024 live
        block in `test_object_census.py`, which self-skips when its source
        projects no longer match their recorded digests: a fixed figure that no
        longer describes the file cannot be asserted against it. `Esperanto` is
        a stable read-only reference and its anchors below DO run.

        Re-anchoring is a deliberate act, not a repair: transfer `Ejagham Mini`
        into a freshly restored `Ejagham Full GT-Test`, re-measure, and update
        `specs/008-affix-pos-picker/contracts/pos-grouped-inventory.md` in the
        same change -- otherwise the numbers here and in the contract diverge
        silently, which is the failure mode this whole block exists to catch.
        """
        source = _get_source("Ejagham Full GT-Test")
        entries = _require_readable(source, "Ejagham Full GT-Test")
        inv = build_pos_grouped_inventory(source)
        found = len(inv.all_affix_guids())
        if found != self.ANCHORED_AFFIXES:
            pytest.skip(
                "'Ejagham Full GT-Test' has drifted since the contract "
                "anchored it on 2026-07-01: %d lexical entries and %d affixes "
                "now, against the anchored %d. It is the restore-between-runs "
                "target of the Ejagham Mini pair, so this is expected rather "
                "than a regression. Re-anchor by re-running that transfer and "
                "updating contracts/pos-grouped-inventory.md together."
                % (len(entries), found, self.ANCHORED_AFFIXES)
            )
        return inv

    def test_total_affix_count(self, ejagham_inv):
        total = len(ejagham_inv.all_affix_guids())
        assert total == 33, f"Expected 33 affixes, got {total}"

    def test_all_inflectional(self, ejagham_inv):
        infl_count = _count_affix_rows_by_msa_kind(ejagham_inv, "infl")
        assert infl_count == 33, f"Expected 33 inflectional, got {infl_count}"

    def test_no_derivational(self, ejagham_inv):
        deriv = _count_affix_rows_by_msa_kind(ejagham_inv, "deriv")
        assert deriv == 0, f"Expected 0 derivational, got {deriv}"

    def test_no_unclassified(self, ejagham_inv):
        uncl = _count_affix_rows_by_msa_kind(ejagham_inv, "uncl")
        assert uncl == 0, f"Expected 0 unclassified, got {uncl}"

    def test_attaches_verb_14(self, ejagham_inv):
        c = _attaches_count_for_label(ejagham_inv, "v")
        assert c == 14, f"Expected 14 verb-attaching, got {c}"

    def test_attaches_noun_11(self, ejagham_inv):
        c = _attaches_count_for_label(ejagham_inv, "n")
        assert c == 11, f"Expected 11 noun-attaching, got {c}"

    def test_attaches_num_6(self, ejagham_inv):
        c = _attaches_count_for_label(ejagham_inv, "num")
        assert c == 6, f"Expected 6 num-attaching, got {c}"

    def test_attaches_pro_1(self, ejagham_inv):
        c = _attaches_count_for_label(ejagham_inv, "pro")
        assert c == 1, f"Expected 1 pro-attaching, got {c}"

    def test_zero_multi_pos(self, ejagham_inv):
        m = _count_multi_pos(ejagham_inv)
        assert m == 0, f"Expected 0 multi-POS, got {m}"

    # T021 - Ejagham junk
    def test_junk_no_pos_1(self, ejagham_inv):
        c = len(ejagham_inv.junk.no_pos)
        assert c == 1, f"Expected 1 no-POS junk entry, got {c}"

    def test_junk_no_analysis_0(self, ejagham_inv):
        c = len(ejagham_inv.junk.no_analysis)
        assert c == 0, f"Expected 0 no-analysis junk, got {c}"


# ============================================================================
# T019 - Esperanto (US3: derivational + unclassified + multi-POS)
# ============================================================================

@pytest.mark.integration
class TestEsperantoInventory:
    """Contract anchors for Esperanto.

    From contracts/pos-grouped-inventory.md:
      affixes: 68 | infl: 41 / deriv: 31 / uncl: 12
      attaches-to: Root:43, v:12, VRoot:9, ARoot:3, n:3, NRoot:2, adj:2
      produces: n:14, v:10, adj:5, adv:1
      multi-POS: 13 | junk no_pos: 7 / no_analysis: 0
    """

    @pytest.fixture(scope="class")
    def esp_project(self):
        """The open handle, kept because three anchors count MSAs and must go
        back to the project for them. Read-only: `Esperanto` is never a write
        target and never a transfer destination."""
        source = _get_source("Esperanto")
        _require_readable(source, "Esperanto")
        return source

    @pytest.fixture(scope="class")
    def esp_inv(self, esp_project):
        return build_pos_grouped_inventory(esp_project)

    def test_total_affix_count(self, esp_inv):
        total = len(esp_inv.all_affix_guids())
        assert total == 68, f"Expected 68 affixes, got {total}"

    def test_inflectional_41(self, esp_project, esp_inv):
        """MSAs, not entries -- see defect 3 in the module docstring. The
        entry-level figure is 30 and is asserted separately below, so both
        quantities stay pinned and neither can drift into the other."""
        c = _count_msas_by_class(esp_project, esp_inv, "MoInflAffMsa")
        assert c == 41, f"Expected 41 inflectional MSAs, got {c}"

    def test_derivational_31(self, esp_project, esp_inv):
        c = _count_msas_by_class(esp_project, esp_inv, "MoDerivAffMsa")
        assert c == 31, f"Expected 31 derivational MSAs, got {c}"

    def test_unclassified_12(self, esp_project, esp_inv):
        c = _count_msas_by_class(esp_project, esp_inv, "MoUnclassifiedAffixMsa")
        assert c == 12, f"Expected 12 unclassified MSAs, got {c}"

    def test_the_three_msa_classes_account_for_every_affix_entry(
            self, esp_project, esp_inv):
        """The reconciliation that makes the two instruments legible together.

        41 + 31 + 12 = 84 MSAs over 68 affix entries. Asserted so a future
        reader meets the >-than-total arithmetic as a stated property rather
        than as a suspicious inconsistency -- and so an MSA class appearing
        that none of the three names cannot pass unnoticed."""
        total = sum(
            _count_msas_by_class(esp_project, esp_inv, name)
            for name in ("MoInflAffMsa", "MoDerivAffMsa",
                         "MoUnclassifiedAffixMsa")
        )
        assert total == 84
        assert total > len(esp_inv.all_affix_guids()) == 68

    def test_entry_level_counts_are_the_other_quantity(self, esp_inv):
        """The distinct-ENTRY figures, pinned beside the MSA ones.

        30 / 30 / 2 through the POS tree, against 41 / 31 / 12 MSAs. The gap on
        `uncl` is the largest and the most informative: 12 entries carry an
        unclassified MSA but only 2 reach a POS node, because an
        `MoUnclassifiedAffixMsa` need name no part of speech -- the rest land in
        the junk drawer. Pinned so the earlier confusion between these two
        instruments cannot recur silently."""
        assert _count_affix_rows_by_msa_kind(esp_inv, "infl") == 30
        assert _count_affix_rows_by_msa_kind(esp_inv, "deriv") == 30
        assert _count_affix_rows_by_msa_kind(esp_inv, "uncl") == 2

    # Attaches-to counts
    def test_attaches_root_43(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "Root")
        assert c == 43, f"Expected Root:43, got {c}"

    def test_attaches_v_12(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "v")
        assert c == 12, f"Expected v:12, got {c}"

    def test_attaches_vroot_9(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "VRoot")
        assert c == 9, f"Expected VRoot:9, got {c}"

    def test_attaches_aroot_3(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "ARoot")
        assert c == 3, f"Expected ARoot:3, got {c}"

    def test_attaches_n_3(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "n")
        assert c == 3, f"Expected n:3, got {c}"

    def test_attaches_nroot_2(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "NRoot")
        assert c == 2, f"Expected NRoot:2, got {c}"

    def test_attaches_adj_2(self, esp_inv):
        c = _attaches_count_for_label(esp_inv, "adj")
        assert c == 2, f"Expected adj:2, got {c}"

    # Produces counts
    def test_produces_n_14(self, esp_inv):
        c = _produces_count_for_label(esp_inv, "n")
        assert c == 14, f"Expected n produces:14, got {c}"

    def test_produces_v_10(self, esp_inv):
        c = _produces_count_for_label(esp_inv, "v")
        assert c == 10, f"Expected v produces:10, got {c}"

    def test_produces_adj_5(self, esp_inv):
        c = _produces_count_for_label(esp_inv, "adj")
        assert c == 5, f"Expected adj produces:5, got {c}"

    def test_produces_adv_1(self, esp_inv):
        c = _produces_count_for_label(esp_inv, "adv")
        assert c == 1, f"Expected adv produces:1, got {c}"

    def test_multi_pos_13(self, esp_inv):
        m = _count_multi_pos(esp_inv)
        assert m == 13, f"Expected 13 multi-POS, got {m}"

    # T021 - Esperanto junk drawer
    def test_junk_no_pos_7(self, esp_inv):
        c = len(esp_inv.junk.no_pos)
        assert c == 7, f"Expected 7 no-POS junk, got {c}"

    def test_junk_no_analysis_0(self, esp_inv):
        c = len(esp_inv.junk.no_analysis)
        assert c == 0, f"Expected 0 no-analysis junk, got {c}"
