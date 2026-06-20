"""Affix-category transfer surface (T049, FR-005).

Affixes carry the heaviest closure in Phase 0: each affix pulls its
allomorphs, APRs, referenced inflection features + inflection classes +
stem names + exception features. Plus they may reference phonological
environments (Layer 3 territory).

Per contracts/category-transfer.md, this module implements the five
functions of the CategoryTransfer protocol. Bodies are NotImplementedError
until T049 lands; the registry below makes them callable from the engine.
"""
from __future__ import annotations

from typing import Iterable, Tuple

if __package__:
    from .models import GrammarCategory, WSKind
    from .residue import ImportResidueTag
else:
    from models import GrammarCategory, WSKind  # type: ignore
    from residue import ImportResidueTag  # type: ignore


CATEGORY = GrammarCategory.AFFIXES


def enumerate_source(context, selection):
    """Walk source affixes honoring `selection.affix_picks` (Q4). Empty
    affix_picks + categories[AFFIXES]=True means 'all affixes'."""
    raise NotImplementedError("T049: walk source.LexEntry.GetAll() filtered to affixes")


def dependencies(piece) -> Iterable[Tuple[GrammarCategory, str]]:
    """FR-005 closure: allomorphs, APRs, inflection features, inflection
    classes, stem names, exception features. Plus environments referenced
    by allomorphs."""
    raise NotImplementedError(
        "T049: yield refs to allomorphs / APRs / inflection features / "
        "inflection classes / stem names / exception features / environments"
    )


def required_writing_systems(piece) -> Iterable[Tuple[str, WSKind]]:
    raise NotImplementedError("T049: lexeme form / citation form / gloss WSs")


def plan_action(piece, context, ws_mapping):
    raise NotImplementedError("T049: PlannedAction or Skip(DEPENDENCY_UNRESOLVED)")


def execute_action(action, context, ws_mapping, tag: ImportResidueTag):
    """Create the LexEntry + LexSense + MSA + Allomorph chain per STATUS.md
    Layer 3 outline. Residue carrier: Carrier A (LiftResidue) on ILexEntry,
    ILexSense, IMoForm, IMoMorphSynAnalysis."""
    raise NotImplementedError("T049 + T051b: ILexEntryFactory.Create(Guid, ILexDb), etc.")


BUNDLE = {
    "enumerate_source": enumerate_source,
    "dependencies": dependencies,
    "required_writing_systems": required_writing_systems,
    "plan_action": plan_action,
    "execute_action": execute_action,
}
