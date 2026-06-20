"""MSA + allomorph + environment transfer surface (T051b, STATUS.md Layer 3).

MSA wiring is the densest part of Phase 0 — for each affix LexEntry we
create:
- ILexEntry  (LexDb-owned)
- ILexSense (entry-owned)
- IMoInflAffMsa / IMoDerivAffMsa / IMoStemMsa / IMoUnclassifiedAffixMsa
  (entry.MorphoSyntaxAnalysesOC; sense.MorphoSyntaxAnalysisRA points at it)
- IMoAffixAllomorph (entry.LexemeFormOA or entry.AlternateFormsOS)
- IPhEnvironment (LangProject.PhonologicalDataOA.EnvironmentsOS) referenced
  from allomorph.PhoneEnvRC

Cross-references resolved by GUID lookup (STATUS.md Layer 3 outline):
- MSA.PartOfSpeechRA → target Verb POS (created in Layer 1)
- MSA.SlotsRC → target slots (created in Layer 2)
- Allomorph.MorphTypeRA → FW standard morph type (same GUID across projects)
- Allomorph.PhoneEnvRC → target environments

Residue carriers: Carrier A (`LiftResidue`) on ILexEntry, ILexSense,
IMoForm subclasses, IMoMorphSynAnalysis; Carrier B (Description-append)
on IPhEnvironment.

Bodies are NotImplementedError pending T-Spike step 3 + T051b.
"""
from __future__ import annotations

from typing import Iterable, Tuple

if __package__:
    from .models import GrammarCategory, WSKind
    from .residue import ImportResidueTag
else:
    from models import GrammarCategory, WSKind  # type: ignore
    from residue import ImportResidueTag  # type: ignore


def msa_dependencies(piece) -> Iterable[Tuple[GrammarCategory, str]]:
    """An MSA references: parent LexEntry, parent LexSense, target POS,
    target slots (for IMoInflAffMsa), inflection features."""
    raise NotImplementedError("T051b: yield refs across POS/slots/features")


def msa_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T051b")


def msa_execute_action(action, context, ws_mapping, tag: ImportResidueTag):
    """IMoInflAffMsaFactory.Create(Guid) → entry.MorphoSyntaxAnalysesOC.Add(msa) →
    sense.MorphoSyntaxAnalysisRA = msa → wire SlotsRC + PartOfSpeechRA →
    apply Carrier-A LiftResidue."""
    raise NotImplementedError("T051b: MSA factory + wiring")


def allomorph_dependencies(piece) -> Iterable[Tuple[GrammarCategory, str]]:
    """Allomorphs reference environments (PhoneEnvRC) and a morph type."""
    raise NotImplementedError("T051b: yield (PH_ENVIRONMENT, guid) refs")


def allomorph_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T051b")


def allomorph_execute_action(action, context, ws_mapping, tag: ImportResidueTag):
    """IMoAffixAllomorphFactory.Create(Guid) → owner attach
    (entry.LexemeFormOA = allo OR entry.AlternateFormsOS.Add(allo)) → wire
    MorphTypeRA + Form multistring + PhoneEnvRC → Carrier-A LiftResidue."""
    raise NotImplementedError("T051b: allomorph factory + wiring")


def environment_dependencies(piece) -> Iterable[Tuple[GrammarCategory, str]]:
    return ()  # environments are leaves


def environment_plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T051b")


def environment_execute_action(action, context, ws_mapping, tag: ImportResidueTag):
    """IPhEnvironmentFactory.Create(Guid) → cache.LangProject.PhonologicalDataOA
    .EnvironmentsOS.Add(env) → Carrier-B Description-append."""
    raise NotImplementedError("T051b: environment factory")


MSA_BUNDLE = {
    "dependencies": msa_dependencies,
    "plan_action": msa_plan_action,
    "execute_action": msa_execute_action,
}

ALLOMORPH_BUNDLE = {
    "dependencies": allomorph_dependencies,
    "plan_action": allomorph_plan_action,
    "execute_action": allomorph_execute_action,
}

ENVIRONMENT_BUNDLE = {
    "dependencies": environment_dependencies,
    "plan_action": environment_plan_action,
    "execute_action": environment_execute_action,
}
