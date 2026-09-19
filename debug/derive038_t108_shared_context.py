"""Feature 038 T108 -- attribute the shared `PhPhonData.ContextsOS` co-create
route from a run report, read-only.

WHY THIS EXISTS AT ALL. T076 added `ProcessContextSpec.co_created_shared` so
that a write into a shared, project-level collection made while transferring a
lexical entry would not be a silent write (SC-010), and asserted it on the
IN-MEMORY record only. `report._process_rule_json` dropped it, so from T076
until T107 the claim was true of the object and FALSE of the artifact anybody
reads. T107 fixed the serializer -- and its own committed run predates the fix,
so its evidence covers the DIRECT boundary-context route (8 rules, 8 reported
input members) and the shared route's refusals and resolution, but not the
shared route's live CO-CREATION.

WHAT THE FIELD SETTLES. `co_created_shared` names the shared members THIS run
created. `categories._resolve_process_graph` reaches the co-create leg only
when the member is not already resolvable in the destination (`member_targets`
is consulted first), so a non-empty field is a positive attribution: this run,
this leg, this object. An empty field over every rule would have been an
answer too -- something else populated `PhPhonData.ContextsOS` first, and on
this pair the only other writer is the phonological-rule path
(`_copy_context_cell`). Either way the output is an attribution. Neither is
"not determinable", which is the string this script exists to replace.

WHY IT ALSO READS THE SOURCE `.fwdata`. The run report names co-created
members by GUID and nothing else, and "13 shared members were created" does
not answer the question T108 was filed for, which is about ONE object: the
single `PhPhonData`-owned `PhSimpleContextBdry`. Resolving each GUID's class
and owner -- and, for a boundary context, every `MoAffixProcess` rule that
reaches it -- is a read-only walk of the source project file, and putting the
result IN the artifact is what keeps the test from asserting against a
hand-typed table that can drift away from the measurement it explains.

Usage:

    python debug/derive038_t108_shared_context.py _run_reports/<report>.json
        [--source-fwdata <path>]

Writes `tests/integration/_snapshots/process-rules-038-t108-ejagham.json`.
Opens no FieldWorks project: the report is JSON and the source is read as text.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SNAPS = _REPO / "tests" / "integration" / "_snapshots"
_OUT = _SNAPS / "process-rules-038-t108-ejagham.json"
_PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")

#: The destination T107's committed censuses are asserted to hash to. A T108
#: derivation that named it would mean the re-run landed on top of T107's
#: evidence, which is the one thing the task forbids.
_T107_DESTINATION = "GT038 Ejagham After"

_RT = re.compile(r"<rt\b.*?</rt>|<rt\b[^>]*/>", re.S)


def _attr(element: str, name: str) -> str:
    m = re.search(r'\b%s="([^"]*)"' % name, element[:400])
    return m.group(1) if m else ""


def _load_source_graph(path: Path) -> dict:
    """`{guid: (class, owner_guid, element)}` for every `rt` in the file.

    Read as text on purpose. A census-grade LCM open would be a heavier
    dependency for a question that is answered by ownership and reference,
    both of which the serialized form carries verbatim.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    graph = {}
    for element in _RT.findall(text):
        guid = _attr(element, "guid").lower()
        if guid:
            graph[guid] = (_attr(element, "class"),
                           _attr(element, "ownerguid").lower(), element)
    return graph


def _owning_rule(graph: dict, guid: str) -> str:
    """The `MoAffixProcess` this object hangs under, or ``""``."""
    seen = set()
    while guid and guid in graph and guid not in seen:
        seen.add(guid)
        cls, owner, _ = graph[guid]
        if cls == "MoAffixProcess":
            return guid
        guid = owner
    return ""


def _rules_reaching(graph: dict, member_guid: str) -> list:
    """Every `MoAffixProcess` with a `PhSequenceContext` naming this member.

    This is the route T076 built and T107 measured at five rules: a rule-owned
    sequence context whose `MembersRS` points into the shared pool.
    """
    rules = set()
    needle = member_guid.lower()
    for guid, (cls, _owner, element) in graph.items():
        if cls != "PhSequenceContext" or needle not in element.lower():
            continue
        rule = _owning_rule(graph, guid)
        if rule:
            rules.add(rule)
    return sorted(rules)


def _attribution(created, boundary, rules_total, refused) -> str:
    if not created:
        return (
            "MEASURED AND EMPTY, which is an answer rather than a gap. Not "
            "one of this run's %d MoAffixProcess rules co-created a shared "
            "PhPhonData.ContextsOS member: every "
            "input_contexts[*].co_created_shared is []. "
            "categories._resolve_process_graph consults member_targets -- "
            "what is already resolvable in the destination -- BEFORE the "
            "co-create leg, so an empty field over every rule means the "
            "shared contexts were already there when the affix process path "
            "reached them, and on this pair the only other writer of that "
            "collection is the phonological-rule path "
            "(Lib/categories._copy_context_cell). The shared route's "
            "RESOLUTION is exercised; its CO-CREATION is not, because "
            "nothing was left for it to create." % rules_total
        )
    by_class = Counter(c["source_class"] for c in created)
    breakdown = ", ".join("%d %s" % (n, k) for k, n in sorted(by_class.items()))
    rules = sorted({c["rule"] for c in created})
    head = (
        "MEASURED AND ATTRIBUTED. The affix-process co-create leg "
        "(categories._create_shared_process_context) created %d shared "
        "members of PhPhonData.ContextsOS in this run -- %s -- reported on "
        "%d of the pair's %d MoAffixProcess rules (%s). Every one is owned "
        "by PhPhonData in the source, which is the shared, project-level "
        "collection SC-010 is about. The count is the number of members "
        "CREATED, not the number of rules that use them: "
        "_resolve_process_graph consults member_targets first, so the "
        "second rule to reach a member finds what the first one made."
        % (len(created), breakdown, len(rules), rules_total, ", ".join(rules))
    )
    if not boundary:
        return head + (
            " NO BOUNDARY CONTEXT IS AMONG THEM, so T108's own question -- "
            "which writer produced the one PhPhonData-owned "
            "PhSimpleContextBdry -- is answered the other way: the "
            "phonological-rule path put it there."
        )
    parts = [head]
    for b in boundary:
        found_it = [r for r in b["rules_reaching_it"]
                    if r != b["created_by_rule"]]
        still_refused = [r for r in found_it if r in refused]
        parts.append(
            " THE BOUNDARY CONTEXT IS AMONG THEM, which is exactly what T107 "
            "could not say: %s, owned by PhPhonData in the source, was "
            "created by rule %s. So the destination's one PhPhonData-owned "
            "PhSimpleContextBdry came from the affix-process co-create leg "
            "and NOT from the phonological-rule path "
            "(Lib/categories._copy_context_cell), even though both write "
            "that collection -- the ambiguity T107 recorded is resolved by "
            "measurement rather than by argument. %d rules reach that "
            "context through a rule-owned PhSequenceContext, reproducing "
            "T107's read-only count of five; the other %d report no "
            "co-creation because they found it already present, and %d of "
            "those never got that far (refused: %s)."
            % (b["guid"], b["created_by_rule"], len(b["rules_reaching_it"]),
               len(found_it), len(still_refused),
               ", ".join(still_refused) or "none")
        )
    return "".join(parts)


def main(argv) -> int:
    if len(argv) < 2:
        print("[FAIL] usage: python debug/derive038_t108_shared_context.py "
              "<run-report.json> [--source-fwdata <path>]")
        return 2
    report_path = Path(argv[1])
    if not report_path.is_file():
        print("[FAIL] no run report at %s" % report_path)
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))

    ctx = report.get("context") or {}
    destination = ctx.get("target_project_name") or ""
    source_name = ctx.get("source_project_name") or ""
    if destination == _T107_DESTINATION:
        print("[FAIL] this report was taken against %r, which is T107's "
              "committed evidence. T108 must run into its own throwaway "
              "target." % destination)
        return 1

    if "--source-fwdata" in argv:
        source_fwdata = Path(argv[argv.index("--source-fwdata") + 1])
    else:
        source_fwdata = (_PROJECTS_ROOT / source_name
                         / (source_name + ".fwdata"))
    if not source_fwdata.is_file():
        print("[FAIL] no source project file at %s -- pass --source-fwdata"
              % source_fwdata)
        return 1

    rules = report.get("process_rules") or []
    if not rules:
        print("[FAIL] %s carries no process_rules block" % report_path)
        return 1

    raw_created, class_totals, boundary_direct = [], Counter(), []
    missing_field, contexts_total = [], 0
    for rule in rules:
        for spec in rule.get("input_contexts") or ():
            contexts_total += 1
            class_totals[spec["context_class"]] += 1
            if "co_created_shared" not in spec:
                missing_field.append(rule["source_guid"])
            else:
                for guid in spec["co_created_shared"]:
                    raw_created.append({
                        "rule": rule["source_guid"],
                        "index": spec["index"],
                        "context_class": spec["context_class"],
                        "guid": guid,
                    })
            if spec["context_class"] == "PhSimpleContextBdry":
                boundary_direct.append({
                    "rule": rule["source_guid"],
                    "index": spec["index"],
                    "referent_guid": spec["referent_guid"],
                })

    if missing_field:
        # The serializer regressed, or this report predates T107's fix. Either
        # way the run cannot answer T108's question and must not be written up
        # as if it had -- that silence is the whole defect T108 exists to end.
        print("[FAIL] %d input_contexts entries carry no co_created_shared "
              "key; this report predates T107's serializer fix (or it "
              "regressed). Re-run the transfer on the current branch."
              % len(missing_field))
        return 1

    graph = _load_source_graph(source_fwdata)
    created, boundary = [], []
    for row in sorted(raw_created, key=lambda r: (r["rule"], r["index"])):
        cls, owner, _element = graph.get(row["guid"].lower(), ("", "", ""))
        if not cls:
            print("[FAIL] co-created member %s is not in the source graph -- "
                  "the report and %s do not describe the same project"
                  % (row["guid"], source_fwdata))
            return 1
        owner_cls = graph.get(owner, ("", "", ""))[0]
        row = dict(row, source_class=cls, source_owner_class=owner_cls)
        created.append(row)
        if cls == "PhSimpleContextBdry":
            boundary.append({
                "guid": row["guid"],
                "source_owner_class": owner_cls,
                "created_by_rule": row["rule"],
                "created_at_input_index": row["index"],
                "rules_reaching_it": _rules_reaching(graph, row["guid"]),
            })

    refused = {r["source_guid"] for r in rules if not r.get("reproduced")}
    payload = {
        "artifact": _OUT.stem,
        "purpose": (
            "T108's live attribution of the shared PhPhonData.ContextsOS "
            "co-create route, which T107 could not make because the only "
            "field that distinguishes it -- "
            "ProcessContextSpec.co_created_shared -- was never serialized. "
            "Derived read-only from the run report of one restored-target "
            "Ejagham transfer on the FIXED serializer, into a target of its "
            "own so that T107's committed censuses keep hashing to the "
            "project they describe. Class and owner for each co-created "
            "member, and the rules that reach a co-created boundary context, "
            "come from a read-only walk of the source .fwdata. NO CENSUS WAS "
            "TAKEN and none was needed: the question lives entirely in the "
            "run report."
        ),
        "derived_read_only_from": report_path.as_posix(),
        "source_graph_read_from": source_fwdata.as_posix(),
        "source_project": source_name,
        "destination_project": destination,
        "run_id": ctx.get("run_id") or "",
        "rules_total": len(rules),
        "rules_reproduced": sum(1 for r in rules if r.get("reproduced")),
        "rules_not_reproduced": sorted(
            ({"source_guid": r["source_guid"],
              "reason": r.get("not_reproducible_reason") or ""}
             for r in rules if not r.get("reproduced")),
            key=lambda r: r["source_guid"]),
        "input_context_class_totals": dict(sorted(class_totals.items())),
        # Both counts, so "the field reached the artifact" is checkable from
        # the artifact rather than only from this script having exited 0.
        # They are equal by construction -- the derivation refuses a report
        # with a single entry missing the key -- and asserting the equality is
        # what makes a future silent regression of the serializer visible here
        # instead of nowhere.
        "input_contexts_total": contexts_total,
        "input_contexts_carrying_co_created_shared": contexts_total,
        "boundary_context_input_members": sorted(
            boundary_direct, key=lambda d: (d["rule"], d["index"])),
        "co_created_shared_members": created,
        "co_created_shared_total": len(created),
        "co_created_shared_by_class": dict(sorted(
            Counter(c["source_class"] for c in created).items())),
        "co_created_shared_owner_classes": dict(sorted(
            Counter(c["source_owner_class"] for c in created).items())),
        "co_created_shared_boundary_contexts": boundary,
        "shared_context_attribution": _attribution(
            created, boundary, len(rules), refused),
    }
    _OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print("[OK] wrote %s" % _OUT)
    print("     rules %d reproduced / %d total"
          % (payload["rules_reproduced"], payload["rules_total"]))
    print("     direct PhSimpleContextBdry input members: %d"
          % len(boundary_direct))
    print("     co-created shared members: %d on %d rule(s)  %s"
          % (len(created), len({c["rule"] for c in created}),
             payload["co_created_shared_by_class"]))
    print()
    print(payload["shared_context_attribution"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
