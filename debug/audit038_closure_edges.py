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

HOW IT ANSWERS. For each producer, the same attribute is read twice per piece:
once exactly as the producer reads it (uncast), and once after an explicit cast
to the concrete interface named by `ClassName`. If the uncast count is 0 while
the cast count is positive, the edge is DEAD -- registering it would switch on
a relationship that contributes nothing. Equal counts mean the producer reads
correctly on live data and the edge is eligible for registration.

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
#: evidence that a DEAD verdict is a property of the producer rather than of
#: one project's data, so a second run must not overwrite the first.
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


def _verdict(uncast: int, cast: int, population: int) -> str:
    """DEAD / OK / PARTIAL / NO_DATA for one measured pair.

    NO_DATA is distinguished from OK deliberately: a producer that found
    nothing because the corpus holds nothing has NOT been audited, and
    reporting that as a pass is how an unverified edge acquires a
    `verified_by` it did not earn.
    """
    if population == 0:
        return "NO_DATA"
    if cast == 0 and uncast == 0:
        return "NO_DATA"
    if uncast == 0 and cast > 0:
        return "DEAD"
    if uncast == cast:
        return "OK"
    return "PARTIAL"


def main() -> int:
    from harness import full_run

    # `SIL.LCModel` only becomes importable once FLExInit has run, which
    # `_open_source_readonly` does -- so the project is opened FIRST and the
    # LCM interfaces are imported after it, not at module scope.
    print("[INFO] Opening %r read-only" % SOURCE)
    proj = full_run._open_source_readonly(SOURCE)

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
        "AFFIX_TO_SLOT": {
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

    artifact = {
        "audit": "038-phase7-closure-edges",
        "source_project": SOURCE,
        "read_only": True,
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
    print("[INFO] Wrote %s" % SNAPSHOT)
    if dead:
        print("[FAIL] %d edge(s) are DEAD on live data and MUST NOT be "
              "registered: %s" % (len(dead), ", ".join(dead)))
        print("       The producer reads a subclass-only property off a "
              "base-typed proxy, so it returns nothing on a real project "
              "while every duck-typed unit test passes.")
        return 1
    print("[OK]   No dead edge among those measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
