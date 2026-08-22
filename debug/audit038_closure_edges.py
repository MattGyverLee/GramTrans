"""Feature 038 Phase 7 (US3) closure-edge audit driver -- T067 / T068 / T069.

FR-018 says each dependency relationship must be verified as CORRECT before it
may influence a plan, and `CLOSURE_EDGES_VERIFIED` makes `verified_by` name the
audit that earned it. This is that audit. It is READ-ONLY: it opens one source
project, runs each candidate producer over real pieces, and asks a question no
unit test can answer.

THE QUESTION. Every one of the 23 `*_dependencies(piece)` producers reads its
far endpoints with bare `getattr`. Under pythonnet, attribute lookup resolves
against the object's STATIC type, and LCM's owning collections are polymorphic:
`ILexEntry.MorphoSyntaxAnalysesOC` is typed `IMoMorphSynAnalysis`, on which
`PartOfSpeechRA`, `InflFeatsOA` and `MsFeaturesOA` are NOT declared -- they
live on the concrete MSA subclasses. So `getattr(msa, "PartOfSpeechRA", None)`
can be unconditionally None on live data while every offline test passes,
because the duck-typed fakes expose the attribute directly on the fake.

That is not a hypothetical. It is the shape of the flexicon 4.5.0 defect this
repo's CLAUDE.md documents at length: a `hasattr(nc, "FeaturesOA")` gate that
was always False, dead for 100% of live natural classes while all 1467 flexicon
tests passed, because those tests built factory-fresh CONCRETE-typed objects.
An edge registered on the strength of unit tests alone would carry a
`verified_by` naming an audit that never touched a real database.

HOW IT ANSWERS -- TWO SEPARATE SIGNALS, deliberately not merged.

1. `edges` measures the READ PATTERN: the same attribute read twice per piece,
   once with a bare `getattr` and once after an explicit cast to the interface
   named by `ClassName`. `CAST_REQUIRED` means a cast is mandatory at that
   site. This is a fact about pythonnet and LCM, so it NEVER changes when
   this repo is fixed.

2. `producer_output` measures THIS REPO: it calls the real producers and
   counts the edges they hand back. This is the signal that changes when a
   producer is fixed, and it drives the exit code.

3. `relationships` measures ONE RELATIONSHIP AT A TIME -- the T067 addition.
   Signals 1 and 2 both answer questions about a COMPOSITE producer:
   `affixes_dependencies` returns GRAM_CATEGORIES, FEATURE_STRUCT_TYPES and
   INFLECTION_FEATURES edges from a single call. `CLOSURE_EDGES_VERIFIED` is
   keyed by ONE `DependencyKind` per row and a dict key is unique, so an audit
   that can only report "the composite returns 1063 edges" cannot earn three
   separate `verified_by` values -- it would file two unaudited relationships
   under a third's evidence, which is the substitution FR-018 exists to
   prevent. So this block calls the NARROW producers (T067's
   `affixes_pos_dependencies`, `affixes_feat_struc_type_dependencies`,
   `affixes_infl_feature_dependencies`; T068's `slots_pos_dependencies`;
   T069's `affix_templates_pos_dependencies` and
   `affix_templates_slot_dependencies`) over the pieces the registry will
   actually walk -- each relationship's OWN source-category
   `enumerate_source`, not every LexEntry -- and per relationship measures
   three things:

     * `foreign_edges`   -- edges of a far category the row does NOT claim.
       Non-zero means the producer is not narrow and must not be registered.
     * `unresolved`      -- far GUIDs that the far category's OWN
       `enumerate_source` never yields. A pulled-in ref that names no
       enumerable piece cannot be planned, marked (T070) or deselected
       (T072); registering it would put an unplannable item into a plan.
     * `resolved`        -- far GUIDs that do resolve. This is the "the edge
       is correct against a live pair" half of T067's own wording.

   A relationship is CONFIRMED only with `foreign_edges == 0`,
   `unresolved == 0` and `edges > 0`, on BOTH corpora.

Keeping them apart is a lesson from the first version of this driver, which
had only signal 1 and was therefore useless for verifying T088's fix -- it
reported the same DEAD verdict before and after, because it never called a
producer at all. A `population` of 0 reports NO_DATA rather than a pass or a
failure: Ejagham Mini holds no adhoc rules, so 0 edges is the correct answer
there and must not be mistaken for a silent producer.

WHY A DRIVER AND NOT A TEST. Same reason as `run038_phase6_live.py`: this needs
a real project and pythonnet. The measurement is run once here and COMMITTED to
`tests/integration/_snapshots/`, and the integration test asserts against the
recorded numbers.

Usage (read-only; never writes, so no restore is needed):

    python debug/audit038_closure_edges.py

Set `GT038_AUDIT_SOURCE` to audit a different project.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

SOURCE = os.environ.get("GT038_AUDIT_SOURCE", "Mbugwe LizzieHC practice")

#: One snapshot PER SOURCE, not one shared file. Two corpora agreeing is the
#: evidence that a verdict is a property of the producer rather than of one
#: project's data, so a second run must not overwrite the first.
SNAPSHOT = (_REPO / "tests" / "integration" / "_snapshots"
            / ("closure-edge-audit-038-%s.json"
               % SOURCE.lower().replace(" ", "-")))

#: The MSA subclasses `MorphoSyntaxAnalysesOC` can actually hold. Keyed by
#: `ClassName` because that is the only discriminator available on a
#: base-typed proxy.
_MSA_CLASSES = (
    "MoStemMsa", "MoInflAffMsa", "MoDerivAffMsa",
    "MoDerivStepMsa", "MoUnclassifiedAffixMsa",
)

#: The POS references `_entry_pos_deps` probes, verbatim.
_POS_ATTRS = ("PartOfSpeechRA", "FromPartOfSpeechRA", "ToPartOfSpeechRA")

#: The feature-structure slots `_entry_feat_struc_deps` probes
#: (`categories._MSA_FEAT_STRUC_ATTRS`), verbatim.
_FEAT_ATTRS = ("InflFeatsOA", "MsFeaturesOA", "FromMsFeaturesOA",
               "ToMsFeaturesOA")

#: The five slot reference sequences `affix_templates_dependencies` walks
#: (`categories._TEMPLATE_SLOT_SEQS`), verbatim.
_TPL_SEQS = ("PrefixSlotsRS", "SuffixSlotsRS", "EncliticSlotsRS",
             "ProcliticSlotsRS", "SlotsRS")

#: Which task owns each candidate relationship in the `relationships` block.
#: Recorded in the snapshot so a reader can tell which audit a row belongs to
#: without consulting tasks.md -- the `relationships` block started as T067's
#: and now spans three tasks.
_CANDIDATE_TASK = {
    "AFFIX_TO_POS": "T067",
    "MSA_TO_FEAT_STRUC_TYPE": "T067",
    "MSA_TO_INFL_FEATURE": "T067",
    "SLOT_TO_POS": "T068",
    "TEMPLATE_TO_POS": "T069",
    "TEMPLATE_TO_SLOT": "T069",
}


def _verdict(uncast: int, cast: int, population: int) -> str:
    """What the READ PATTERN requires, for one measured attribute group.

    This describes pythonnet and LCM, not this repo's code, so it does not
    change when a producer is fixed -- `CAST_REQUIRED` stays `CAST_REQUIRED`
    forever, because a bare `getattr` on a base-typed proxy will never see a
    subclass-only property. Read it as "a cast is mandatory here", not as
    "the producer is broken".

    Whether the producer is broken is a different question with a different
    answer, and conflating the two is what made the first version of this
    driver useless for verifying T088's fix: it reported DEAD both before and
    after, because it was never measuring the producer at all. The
    `producer_output` block answers that one.

    NO_DATA is distinguished from NO_CAST_NEEDED deliberately: an attribute
    group that found nothing because the corpus holds nothing has NOT been
    audited, and reporting that as a pass is how an unverified edge acquires
    a `verified_by` it did not earn.
    """
    if population == 0:
        return "NO_DATA"
    if cast == 0 and uncast == 0:
        return "NO_DATA"
    if uncast == 0 and cast > 0:
        return "CAST_REQUIRED"
    if uncast == cast:
        return "NO_CAST_NEEDED"
    return "PARTIAL"


def main() -> int:
    from harness import full_run

    # `SIL.LCModel` only becomes importable once FLExInit has run, which
    # `source_readonly` does -- so the project is opened FIRST and the LCM
    # interfaces are imported after it, not at module scope.
    #
    # T090: this used to call `full_run._open_source_readonly` and return
    # without ever closing. flexicon takes the Palaso file lock on ANY open,
    # read-only included ("the project must be closed with `CloseProject()`
    # to save any changes, AND RELEASE THE LOCK"), so every run of this driver
    # left a `<project>.fwdata.lock` behind naming a PID that had exited --
    # and the next `tests/integration` run read that file as "locked by
    # FieldWorks" and turned four live assertions into skips. The audit body
    # lives in `_audit` so the pairing is by construction, not by remembering
    # to close on every return path.
    print("[INFO] Opening %r read-only" % SOURCE)
    with full_run.source_readonly(SOURCE) as proj:
        return _audit(proj)


def _audit(proj) -> int:
    from SIL.LCModel import (
        ILangProject,
        IMoDerivAffMsa,
        IMoDerivStepMsa,
        IMoInflAffMsa,
        IMoInflAffixTemplate,
        IMoStemMsa,
        IMoUnclassifiedAffixMsa,
        IPartOfSpeech,
    )

    concrete = {
        "MoStemMsa": IMoStemMsa,
        "MoInflAffMsa": IMoInflAffMsa,
        "MoDerivAffMsa": IMoDerivAffMsa,
        "MoDerivStepMsa": IMoDerivStepMsa,
        "MoUnclassifiedAffixMsa": IMoUnclassifiedAffixMsa,
    }

    langproj = ILangProject(proj.project.LangProject)

    # ---- T067: the two halves of affixes_dependencies / stems_dependencies
    entries = list(langproj.LexDbOA.Entries)
    msa_by_class: dict = {}
    pos_uncast = pos_cast = 0
    feat_uncast = feat_cast = 0
    n_msa = 0

    for entry in entries:
        for msa in (entry.MorphoSyntaxAnalysesOC or []):
            n_msa += 1
            cname = str(msa.ClassName)
            msa_by_class[cname] = msa_by_class.get(cname, 0) + 1
            for attr in _POS_ATTRS:
                if getattr(msa, attr, None) is not None:
                    pos_uncast += 1
            for attr in _FEAT_ATTRS:
                if getattr(msa, attr, None) is not None:
                    feat_uncast += 1
            iface = concrete.get(cname)
            if iface is None:
                continue
            cast_msa = iface(msa)
            for attr in _POS_ATTRS:
                if getattr(cast_msa, attr, None) is not None:
                    pos_cast += 1
            for attr in _FEAT_ATTRS:
                if getattr(cast_msa, attr, None) is not None:
                    feat_cast += 1

    # ---- T068 / T069: slot and template owners, plus the slot ref sequences
    stats = dict(pos=0, slots=0, templates=0, slot_owner=0, tpl_owner=0,
                 seq_uncast=0, seq_cast=0)

    def walk(pos_list) -> None:
        for raw in pos_list:
            pos = IPartOfSpeech(raw)
            stats["pos"] += 1
            for slot in (pos.AffixSlotsOC or []):
                stats["slots"] += 1
                if getattr(slot, "Owner", None) is not None:
                    stats["slot_owner"] += 1
            for tpl in (pos.AffixTemplatesOS or []):
                stats["templates"] += 1
                if getattr(tpl, "Owner", None) is not None:
                    stats["tpl_owner"] += 1
                for seq in _TPL_SEQS:
                    got = getattr(tpl, seq, None)
                    if got is not None:
                        stats["seq_uncast"] += len(list(got))
                cast_tpl = IMoInflAffixTemplate(tpl)
                for seq in _TPL_SEQS:
                    got = getattr(cast_tpl, seq, None)
                    if got is not None:
                        stats["seq_cast"] += len(list(got))
            walk(pos.SubPossibilitiesOS or [])

    walk(list(langproj.PartsOfSpeechOA.PossibilitiesOS))

    edges = {
        "AFFIX_TO_POS": {
            "task": "T067",
            "producer": "categories._entry_pos_deps (affixes/stems_dependencies)",
            "reads": list(_POS_ATTRS),
            "population": n_msa,
            "uncast": pos_uncast,
            "cast": pos_cast,
            "verdict": _verdict(pos_uncast, pos_cast, n_msa),
        },
        "MSA_TO_FEAT_STRUC_TYPE": {
            "task": "T067 (edges landed by T034)",
            "producer": "categories._entry_feat_struc_deps",
            "reads": list(_FEAT_ATTRS),
            "population": n_msa,
            "uncast": feat_uncast,
            "cast": feat_cast,
            "verdict": _verdict(feat_uncast, feat_cast, n_msa),
        },
        "SLOT_TO_POS": {
            "task": "T068",
            "producer": "categories.slots_dependencies",
            "reads": ["Owner"],
            "population": stats["slots"],
            "uncast": stats["slot_owner"],
            "cast": stats["slots"],
            "verdict": _verdict(stats["slot_owner"], stats["slots"],
                                stats["slots"]),
        },
        "TEMPLATE_TO_POS": {
            "task": "T069",
            "producer": "categories.affix_templates_dependencies (owner half)",
            "reads": ["Owner"],
            "population": stats["templates"],
            "uncast": stats["tpl_owner"],
            "cast": stats["templates"],
            "verdict": _verdict(stats["tpl_owner"], stats["templates"],
                                stats["templates"]),
        },
        # RENAMED by T069 from `AFFIX_TO_SLOT`. This block has always
        # measured `IMoInflAffixTemplate`'s five `*SlotsRS` sequences -- a
        # TEMPLATE->slot reference. `AFFIX_TO_SLOT` is `IMoInflAffMsa.SlotsRC`,
        # a different arrow off a different owner, and is carried as
        # `RunPlan.msa_slot_bindings` rather than as a dependency edge.
        "TEMPLATE_TO_SLOT": {
            "task": "T069",
            "producer": "categories.affix_templates_dependencies (slot seqs)",
            "reads": list(_TPL_SEQS),
            "population": stats["templates"],
            "uncast": stats["seq_uncast"],
            "cast": stats["seq_cast"],
            "verdict": _verdict(stats["seq_uncast"], stats["seq_cast"],
                                stats["templates"]),
        },
    }

    # ---- What the PRODUCERS actually return
    #
    # The `edges` block above measures the LCM read pattern -- bare `getattr`
    # versus a cast -- which is a fact about pythonnet and is DEAD by
    # construction no matter what this repo does. It is the right measurement
    # for deciding whether a cast is NEEDED, and the wrong one for checking
    # whether a producer has been FIXED. So call the real producers too and
    # count the edges they hand back, bucketed by far category.
    from gramtrans.Lib import categories as _cats
    from gramtrans.Lib.models import GrammarCategory as _GC

    producer_out: dict = {}
    for label, fn in (("affixes_dependencies", _cats.affixes_dependencies),
                      ("stems_dependencies", _cats.stems_dependencies)):
        by_far: dict = {}
        total = 0
        for entry in entries:
            for ref in fn(entry) or ():
                if not (isinstance(ref, tuple) and len(ref) == 2):
                    continue
                far = getattr(ref[0], "value", str(ref[0]))
                by_far[far] = by_far.get(far, 0) + 1
                total += 1
        producer_out[label] = {"population": len(entries),
                               "total_edges": total,
                               "by_far_category": by_far}

    adhoc_rules = list(_cats._rules_enumerate_all(proj) or ())
    adhoc_total = 0
    for rule in adhoc_rules:
        adhoc_total += len(_cats.adhoc_compound_rules_dependencies(rule) or ())
    producer_out["adhoc_compound_rules_dependencies"] = {
        # `population` is the RULE count here, not the entry count: Ejagham
        # Mini holds 0 adhoc rules, so 0 edges is the correct answer there and
        # must not be reported as a silent producer.
        "population": len(adhoc_rules),
        "total_edges": adhoc_total,
        "by_far_category": {},
    }

    # ---- T067: ONE RELATIONSHIP AT A TIME
    #
    # `producer_output` above is a composite measurement and cannot earn three
    # separate `verified_by` values. This block calls the NARROW producers over
    # the pieces `closure_dependencies_for` will actually hand them -- the
    # AFFIXES category's own `enumerate_source`, not every LexEntry -- and
    # resolves each far GUID against the far category's own enumerator, which
    # is the same lookup `_pieces_for` performs during the walk.

    class _AuditContext:
        """The one attribute `*_enumerate_source` reads off a RunContext.

        A real `RunContext` needs a bound TARGET, and this audit is read-only
        with no target at all. Every enumerator used here touches
        `context.source_handle` and nothing else.
        """

        def __init__(self, handle):
            self.source_handle = handle

    audit_ctx = _AuditContext(proj)

    _pieces_cache: dict = {}

    def _source_pieces(category):
        """The pieces the registry will actually hand a producer for
        `category` -- its own `enumerate_source`, not a hand-rolled LCM walk.

        Cached because several candidate relationships share one source
        category (AFFIXES has three, AFFIX_TEMPLATES has two) and re-walking
        the project per relationship would make the numbers depend on the
        order the candidates happen to be listed in.
        """
        if category not in _pieces_cache:
            bundle = _cats.LEAF_CATEGORIES[category]
            _pieces_cache[category] = list(
                bundle["enumerate_source"](audit_ctx, None) or ())
        return _pieces_cache[category]

    def _piece_guids(category):
        """Lower-cased GUIDs of every piece `category`'s enumerator yields.

        Deliberately the REAL enumerator rather than a hand-rolled LCM walk:
        the question is whether a pulled-in ref names something this repo can
        enumerate, plan and deselect, and `enumerate_source` is what decides
        that.
        """
        bundle = _cats.LEAF_CATEGORIES[category]
        out = set()
        for piece in bundle["enumerate_source"](audit_ctx, None) or ():
            g = _cats._guid_str_from(piece)
            if g:
                out.add(g.lower())
        return out

    def _owned_symbolic_value_guids():
        """GUIDs of the `IFsSymFeatVal`s owned by the enumerated features.

        `inflection_features_enumerate_source` yields feature DEFNS only, and
        `inflection_features_dependencies` records that the values are
        "co-created in execute_action, not separately planned". So a value GUID
        is neither unresolvable-in-the-source nor an enumerable piece: it is a
        third state, and collapsing it into either would misreport the finding.
        """
        out = set()
        enumerate_source = _cats.LEAF_CATEGORIES[
            _GC.INFLECTION_FEATURES]["enumerate_source"]
        for defn in enumerate_source(audit_ctx, None) or ():
            closed = _cats._cast_lcm(_cats._unwrap_lcm(defn), "IFsClosedFeature")
            for val in getattr(closed, "ValuesOC", None) or ():
                g = _cats._guid_str_from(val)
                if g:
                    out.add(g.lower())
        return out

    _far_index = {
        _GC.GRAM_CATEGORIES: (_piece_guids(_GC.GRAM_CATEGORIES), set()),
        _GC.SLOTS: (_piece_guids(_GC.SLOTS), set()),
        _GC.FEATURE_STRUCT_TYPES: (_piece_guids(_GC.FEATURE_STRUCT_TYPES), set()),
        _GC.INFLECTION_FEATURES: (_piece_guids(_GC.INFLECTION_FEATURES),
                                  _owned_symbolic_value_guids()),
    }

    #: `(DependencyKind name, producer name, producer, SOURCE category, FAR
    #: category)`. The SOURCE category is not decoration: it decides which
    #: `enumerate_source` supplies the pieces, and measuring a producer over
    #: the wrong pieces is how T067's composite measurement came to be worth
    #: nothing (it counted `affixes_dependencies` over every LexEntry, not
    #: over the AFFIXES category's own output).
    _CANDIDATES = (
        ("AFFIX_TO_POS", "affixes_pos_dependencies",
         _cats.affixes_pos_dependencies, _GC.AFFIXES, _GC.GRAM_CATEGORIES),
        ("MSA_TO_FEAT_STRUC_TYPE", "affixes_feat_struc_type_dependencies",
         _cats.affixes_feat_struc_type_dependencies, _GC.AFFIXES,
         _GC.FEATURE_STRUCT_TYPES),
        ("MSA_TO_INFL_FEATURE", "affixes_infl_feature_dependencies",
         _cats.affixes_infl_feature_dependencies, _GC.AFFIXES,
         _GC.INFLECTION_FEATURES),
        # T068. The relationship the plan called `SLOT_TO_TEMPLATE` and the
        # first audit called `SLOT_TO_POS` without a member existing for it.
        ("SLOT_TO_POS", "slots_pos_dependencies",
         _cats.slots_pos_dependencies, _GC.SLOTS, _GC.GRAM_CATEGORIES),
        # T069. Both halves of `affix_templates_dependencies`, split the way
        # T067 split `affixes_dependencies`. TEMPLATE_TO_SLOT is the member
        # this relationship needed: the first audit labelled it
        # `AFFIX_TO_SLOT`, which is a different arrow off a different owner.
        ("TEMPLATE_TO_POS", "affix_templates_pos_dependencies",
         _cats.affix_templates_pos_dependencies, _GC.AFFIX_TEMPLATES,
         _GC.GRAM_CATEGORIES),
        ("TEMPLATE_TO_SLOT", "affix_templates_slot_dependencies",
         _cats.affix_templates_slot_dependencies, _GC.AFFIX_TEMPLATES,
         _GC.SLOTS),
    )

    relationships: dict = {}
    for kind_name, producer_name, producer, src_cat, far_cat in _CANDIDATES:
        pieces_ok, owned_values = _far_index[far_cat]
        src_pieces = _source_pieces(src_cat)
        edge_count = 0
        foreign = 0
        distinct = set()
        resolved = 0
        owned = 0
        unresolved_guids: list = []
        for piece in src_pieces:
            for ref in producer(piece) or ():
                if not (isinstance(ref, tuple) and len(ref) == 2):
                    foreign += 1
                    continue
                if ref[0] is not far_cat:
                    foreign += 1
                    continue
                edge_count += 1
                distinct.add(ref[1])
        for guid in sorted(distinct):
            if guid in pieces_ok:
                resolved += 1
            elif guid in owned_values:
                owned += 1
            else:
                unresolved_guids.append(guid)
        if not src_pieces or edge_count == 0:
            verdict = "NO_DATA"
        elif foreign:
            verdict = "REFUSED_NOT_NARROW"
        elif unresolved_guids:
            verdict = "REFUSED_UNRESOLVED_FAR_ENDPOINT"
        elif owned:
            verdict = "REFUSED_FAR_ENDPOINT_NOT_ENUMERABLE"
        else:
            verdict = "CONFIRMED"
        relationships[kind_name] = {
            "task": _CANDIDATE_TASK[kind_name],
            "producer": "categories." + producer_name,
            "source_category": src_cat.value,
            "dependency_category": far_cat.value,
            "population": len(src_pieces),
            "edges": edge_count,
            "distinct_far_guids": len(distinct),
            "foreign_edges": foreign,
            "resolved_as_piece": resolved,
            "resolved_as_owned_value": owned,
            "unresolved": len(unresolved_guids),
            "unresolved_sample": unresolved_guids[:5],
            "verdict": verdict,
        }

    _ = _GC  # imported for the category vocabulary these buckets name

    artifact = {
        "audit": "038-phase7-closure-edges",
        "source_project": SOURCE,
        "read_only": True,
        "producer_output": producer_out,
        "relationships": relationships,
        "population": {
            "lex_entries": len(entries),
            "msas": n_msa,
            "msas_by_class": msa_by_class,
            "poses": stats["pos"],
            "slots": stats["slots"],
            "templates": stats["templates"],
        },
        "edges": edges,
    }

    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")

    print()
    print("[INFO] %s: %d entries, %d MSAs, %d POSes, %d slots, %d templates"
          % (SOURCE, len(entries), n_msa, stats["pos"], stats["slots"],
             stats["templates"]))
    for cname in sorted(msa_by_class):
        print("         %-26s %d" % (cname, msa_by_class[cname]))
    print()
    print("       %-24s %-8s %-8s %s" % ("EDGE", "UNCAST", "CAST", "VERDICT"))
    print("       " + "-" * 56)
    dead = []
    for name, row in edges.items():
        print("       %-24s %-8d %-8d %s"
              % (name, row["uncast"], row["cast"], row["verdict"]))
        if row["verdict"] == "DEAD":
            dead.append(name)
    print()
    print("       PRODUCER OUTPUT (what the fixed code actually returns)")
    print("       " + "-" * 56)
    for label in sorted(producer_out):
        row = producer_out[label]
        print("       %-38s %d edge(s)" % (label, row["total_edges"]))
        for far in sorted(row["by_far_category"]):
            print("           -> %-26s %d" % (far, row["by_far_category"][far]))

    print()
    print("       PER-RELATIONSHIP AUDIT (T067/T068/T069 -- what may "
          "be REGISTERED)")
    print("       " + "-" * 68)
    print("       %-24s %-7s %-8s %-6s %-6s %s"
          % ("RELATIONSHIP", "EDGES", "FOREIGN", "RESLV", "OWNED", "VERDICT"))
    for name, row in relationships.items():
        print("       %-24s %-7d %-8d %-6d %-6d %s"
              % (name, row["edges"], row["foreign_edges"],
                 row["resolved_as_piece"], row["resolved_as_owned_value"],
                 row["verdict"]))
        if row["unresolved"]:
            print("           unresolved far GUIDs: %d (e.g. %s)"
                  % (row["unresolved"], ", ".join(row["unresolved_sample"])))

    print()
    print("[INFO] Wrote %s" % SNAPSHOT)
    if dead:
        print("[INFO] %d attribute group(s) REQUIRE a cast (a fact about "
              "pythonnet, not a defect): %s" % (len(dead), ", ".join(dead)))

    # The pass/fail signal is whether the PRODUCERS return anything, because
    # that is the part this repo controls. A producer that must cast and does
    # is correct; one that must cast and does not is T088.
    silent = [label for label, row in producer_out.items()
              if row["total_edges"] == 0 and row["population"] > 0]
    no_data = [label for label, row in producer_out.items()
               if row["population"] == 0]
    for label in sorted(no_data):
        print("[INFO] %s: nothing of its kind in this corpus -- NOT audited "
              "here" % label)
    if silent:
        print("[FAIL] %d producer(s) returned NO edges over a corpus that has "
              "them: %s" % (len(silent), ", ".join(sorted(silent))))
        print("       That is T088: a subclass-only property read off a "
              "base-typed proxy returns nothing on a real project while every "
              "duck-typed unit test passes.")
        return 1
    print("[OK]   Every measured producer returns edges on live data.")

    confirmed = [n for n, r in relationships.items()
                 if r["verdict"] == "CONFIRMED"]
    refused = [n for n, r in relationships.items()
               if r["verdict"].startswith("REFUSED")]
    print("[INFO] Registrable (CONFIRMED): %s"
          % (", ".join(confirmed) or "none"))
    if refused:
        print("[INFO] NOT registrable: %s" % ", ".join(refused))
        print("       A refused relationship is the audit working. Do not "
              "register it and do not give it a verified_by.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
