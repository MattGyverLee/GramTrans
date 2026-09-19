"""Feature 038 Phase 7 (US3) live driver -- T074, FR-019 / SC-003.

WHAT FR-019 ASKS, AND WHY A DRIVER IS NEEDED TO ANSWER IT. "Each transferred
affix MUST be linked to the template column it occupied in the source, or the
failure to link MUST be reported." Both halves are counts over a LIVE pair and
neither is visible in the run report today: `report.py` carries no MSA->slot
link tally at all, so the only prior evidence for SC-003 is its own recorded
baseline (0 of 110 linked, 0 reported). This driver replaces the deduction with
a measurement, and measures the REPORT as well as the arrival -- a link that
happened and a link that was reported are two different claims.

THE THREE MEASUREMENTS, all against a THROWAWAY target restored from a known
backup first (CLAUDE.md's restore-before-write), source read-only throughout:

  A. FULL COPY. The SC-003 claim as a linguist would ask it: transfer
     everything, then count target `MoInflAffMsa` with a non-empty `SlotsRC`
     against the source's own count. Also counts the 17.1 sub-pass's
     `DEPENDENCY_UNRESOLVED` skips, because "linked OR reported" is only
     satisfied if the residue is reported.

  B. NARROW (AFFIX_TEMPLATES-only). The same run report under a selection that
     transfers NO affixes. `preview._populate_msa_slot_bindings` walks the
     WHOLE SOURCE LEXICON regardless of selection, so every binding is
     unresolvable here by construction. Whatever this column reports is
     reported about affixes the run never claimed to transfer -- the
     over-report direction, which CLAUDE.md records as unshippable in the
     flexicon 4.5.1 case (a guard that "reports a loss that did not happen").
     Each skip is classified against the source MSA->entry map so the count
     separates "not selected" from "transferred but not linked".

  C. AFFIXES-ONLY, no templates and no slots. The one selection where a REAL
     failure to link is expected: the affixes arrive, the slots they reference
     do not, so every binding has a resolvable MSA and an unresolvable slot.
     This is the column that proves a scoped report still reports -- without
     it, "scope the skips to the run" is indistinguishable from "emit fewer
     skips".

Usage (writes to a THROWAWAY target, restored before each measurement):

    python debug/run038_msa_slot_link_census.py

`GT038_LINK_SOURCE` / `GT038_LINK_TARGET` override the projects. ASCII-only
output (Windows-terminal safe).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

SOURCE = os.environ.get("GT038_LINK_SOURCE", "Mbugwe LizzieHC practice")
TARGET = os.environ.get("GT038_LINK_TARGET", "GT038 Closure Target")
BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
_SNAPS = _REPO / "tests" / "integration" / "_snapshots"
_OUT = _SNAPS / "msa-slot-link-038-t074.json"


def _only(*category_names):
    """Exclude every category but the named ones."""
    from gramtrans.Lib.models import GrammarCategory
    keep = {getattr(GrammarCategory, n) for n in category_names}
    return frozenset(c for c in GrammarCategory if c not in keep)


# --------------------------------------------------------------------------
# source truth
# --------------------------------------------------------------------------

def source_link_truth(project_name):
    """READ-ONLY. What the source actually says about affix template columns.

    Returns `(inventory, msa_to_entry)`: the SC-003 denominator plus the map
    that lets a skip be classified as "the run never transferred this affix"
    rather than "the run lost it".
    """
    from harness import full_run

    from gramtrans.Lib import categories
    from gramtrans.Lib.preview import _classname_of

    handle = full_run._open_source_readonly(project_name)
    try:
        cast = categories._cast_lcm
        total = wired = slot_refs = 0
        wired_msas = set()
        msa_to_entry = {}
        slot_guids = set()
        for raw_entry in categories._iter_lex_entries(handle):
            entry = cast(raw_entry, "ILexEntry")
            entry_guid = categories._guid_str_from(raw_entry)
            for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
                if _classname_of(msa) != "MoInflAffMsa":
                    continue
                total += 1
                msa_guid = categories._guid_str_from(msa)
                msa_to_entry[msa_guid] = entry_guid
                slots = list(getattr(
                    cast(msa, "IMoInflAffMsa"), "SlotsRC", None) or [])
                if slots:
                    wired += 1
                    slot_refs += len(slots)
                    wired_msas.add(msa_guid)
                    for sl in slots:
                        slot_guids.add(categories._guid_str_from(sl))
        return (
            {
                "total_MoInflAffMsa": total,
                "with_SlotsRC": wired,
                "slot_refs": slot_refs,
                "distinct_slots_referenced": len(slot_guids),
                "wired_msa_guids": sorted(wired_msas),
            },
            msa_to_entry,
        )
    finally:
        try:
            handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def target_link_state(project_name):
    """READ-ONLY. Target `MoInflAffMsa` with a non-empty SlotsRC."""
    from harness import full_run

    from gramtrans.Lib import categories
    from gramtrans.Lib.preview import _classname_of

    handle = full_run._open_source_readonly(project_name)
    try:
        cast = categories._cast_lcm
        total = wired = slot_refs = 0
        wired_msas = set()
        for raw_entry in categories._iter_lex_entries(handle):
            entry = cast(raw_entry, "ILexEntry")
            for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
                if _classname_of(msa) != "MoInflAffMsa":
                    continue
                total += 1
                slots = list(getattr(
                    cast(msa, "IMoInflAffMsa"), "SlotsRC", None) or [])
                if slots:
                    wired += 1
                    slot_refs += len(slots)
                    wired_msas.add(categories._guid_str_from(msa))
        return {
            "total_MoInflAffMsa": total,
            "with_SlotsRC": wired,
            "slot_refs": slot_refs,
            "wired_msa_guids": sorted(wired_msas),
        }
    finally:
        try:
            handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------
# report side
# --------------------------------------------------------------------------

def _link_skips(report):
    """The 17.1 sub-pass's own skips, identified by their detail text.

    Deliberately matched the way a READER of the report would have to match
    them -- there is no structured field naming this sub-pass, which is itself
    part of what T074 measures.
    """
    rows = []
    for skip in getattr(report, "skips", ()) or ():
        detail = getattr(skip, "detail", "") or ""
        if "msa_guid=" in detail:
            kind = "msa_unresolved"
        elif "slot_guid=" in detail:
            kind = "slot_unresolved"
        else:
            continue
        rows.append({
            "kind": kind,
            "category": getattr(getattr(skip, "category", None), "value", None),
            "reason": getattr(getattr(skip, "reason", None), "name", None),
            "source_guid": str(getattr(skip, "source_guid", "")).lower(),
            "detail": detail,
        })
    return rows


def _transferred_entry_guids(plan):
    """Every source LexEntry GUID this run planned to write."""
    guids = set()
    for item in (list(getattr(plan, "actions", ()) or ())
                 + list(getattr(plan, "overwrites", ()) or ())):
        cat = getattr(getattr(item, "category", None), "value", None)
        if cat in ("affixes", "stems"):
            guids.add(str(item.source_guid).lower())
    return guids


def _classify(skips, msa_to_entry, transferred_entries):
    """Split the reported failures into the two claims they conflate.

    A skip whose MSA belongs to an entry this run never transferred is an
    OVER-REPORT: nothing was lost, because nothing was promised. A skip whose
    MSA belongs to a transferred entry is a REAL unlinked affix -- exactly what
    FR-019's second half exists to surface.
    """
    over = real = unknown = 0
    for row in skips:
        if row["kind"] == "slot_unresolved":
            # keyed by the SLOT guid, so the MSA is not recoverable from the
            # skip alone -- itself a finding about the report's granularity.
            unknown += 1
            continue
        entry = msa_to_entry.get(row["source_guid"])
        if entry is None:
            unknown += 1
        elif entry in transferred_entries:
            real += 1
        else:
            over += 1
    return {
        "total": len(skips),
        "msa_unresolved_for_an_affix_this_run_transferred": real,
        "msa_unresolved_for_an_affix_this_run_never_transferred": over,
        "not_attributable_from_the_skip_alone": unknown,
    }


def _link_tally(report):
    """The FR-019 tally the run report now carries (T074), or None.

    Read off the report OBJECT, so a run whose records never reached the report
    cannot pass by way of a log line.
    """
    links = getattr(report, "affix_slot_links", ()) or ()
    if not links:
        return None
    from gramtrans.Lib import report as _rm
    return _rm._affix_slot_link_block(links)


def _report_has_a_link_tally(report):
    """Does the run report state a link count anywhere? (FR-019's audit trail.)

    Checked by NAME against the report object rather than by reading prose, so
    the answer cannot be produced by a log line that no consumer can count.
    """
    names = ("msa_slot_links", "affix_slot_links", "slot_links_wired",
             "template_columns_linked", "link_failures")
    found = {}
    for name in names:
        if hasattr(report, name):
            # COUNT, never the records themselves: this key answers "does the
            # report carry a tally at all", and the tally's own content is
            # recorded by `_link_tally` below in its serialisable shape.
            value = getattr(report, name)
            found[name] = (len(value) if isinstance(value, (tuple, list))
                           else value)
    per_cat_fields = set()
    for rpt in (getattr(report, "per_category", {}) or {}).values():
        per_cat_fields |= {
            f for f in dir(rpt)
            if "link" in f.lower() or "slot" in f.lower()
        }
        break
    return {
        "runreport_fields_present": found,
        "categoryreport_link_or_slot_fields": sorted(per_cat_fields),
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    from harness import full_run
    from harness.restore import restore_target

    target_path = str(PROJECTS_ROOT / TARGET / (TARGET + ".fwdata"))
    reports_dir = _REPO / "_run_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("== SOURCE truth (%s), read-only" % SOURCE)
    truth, msa_to_entry = source_link_truth(SOURCE)
    for key in ("total_MoInflAffMsa", "with_SlotsRC", "slot_refs",
                "distinct_slots_referenced"):
        print("   %-28s %s" % (key, truth[key]))

    results = {
        "source_project": SOURCE,
        "target_project": TARGET,
        "backup": BACKUP.name,
        "source_truth": {k: v for k, v in truth.items()
                         if k != "wired_msa_guids"},
        "measurements": {},
    }

    def _measure(label, exclude, note):
        print("\n== %s -- restoring %r from %s" % (label, TARGET, BACKUP.name))
        restore_target(TARGET, BACKUP)
        before = target_link_state(TARGET)
        print("   [BEFORE] MoInflAffMsa=%d with-SlotsRC=%d slot-refs=%d"
              % (before["total_MoInflAffMsa"], before["with_SlotsRC"],
                 before["slot_refs"]))
        report_path = str(reports_dir / ("038-t074-%s-report.json" % label))
        plan, report = full_run.run_full_transfer(
            SOURCE, TARGET, target_path,
            exclude=exclude, ws_mapping_mode="full", report_path=report_path,
        )
        after = target_link_state(TARGET)
        skips = _link_skips(report)
        transferred = _transferred_entry_guids(plan)
        arrived = (set(after["wired_msa_guids"])
                   - set(before["wired_msa_guids"]))
        linked_of_source = len(
            set(truth["wired_msa_guids"]) & set(after["wired_msa_guids"]))
        print("   [AFTER]  MoInflAffMsa=%d with-SlotsRC=%d slot-refs=%d"
              % (after["total_MoInflAffMsa"], after["with_SlotsRC"],
                 after["slot_refs"]))
        print("   [LINKED] %d of %d source-wired MSAs occupy a column in target"
              % (linked_of_source, truth["with_SlotsRC"]))
        print("   [REPORT] %d 17.1 skip(s)" % len(skips))
        row = {
            "note": note,
            "excluded_categories": sorted(
                getattr(c, "value", str(c)) for c in exclude),
            "target_before": {k: v for k, v in before.items()
                              if k != "wired_msa_guids"},
            "target_after": {k: v for k, v in after.items()
                             if k != "wired_msa_guids"},
            "newly_wired_in_target": len(arrived),
            "source_wired_msas_linked_in_target": linked_of_source,
            "source_wired_msas_total": truth["with_SlotsRC"],
            "affix_or_stem_entries_transferred": len(transferred),
            "link_skips": _classify(skips, msa_to_entry, transferred),
            "link_skip_examples": skips[:5],
            "report_link_tally": _report_has_a_link_tally(report),
            "affix_slot_link_block": _link_tally(report),
        }
        results["measurements"][label] = row
        return row

    _measure("A-full-copy", frozenset(),
             "SC-003's own claim: transfer everything, count the columns")
    _measure("B-templates-only", _only("AFFIX_TEMPLATES"),
             "no affixes transferred; every reported failure is an over-report")
    _measure("C-affixes-only", _only("AFFIXES"),
             "affixes arrive, slots do not: the real failure-to-link case")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print("\n[INFO] wrote %s" % _OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
