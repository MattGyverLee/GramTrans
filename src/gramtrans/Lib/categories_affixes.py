"""Affix-category transfer surface -- INTENTIONALLY UNIMPLEMENTED placeholder.

DO NOT mistake this for a pending backlog item. Phase-0 affix transfer is
LIVE and MCP-verified via the closure/plan path, NOT through this module:

    Lib/preview.py._plan_layer3_verb_affixes   (planning)
    Lib/transfer.py._execute_layer3            (LexEntry/Sense/MSA/Allomorph)
    Lib/categories.py._create_msa_for_closure  (MSA wiring)

Per-item picks (`selection.affix_picks` / `selection.stem_picks`) are honoured
by the live path (issue #117, decided: honour them): `Selection.
leaf_picks_for` falls back to them, `categories.affixes_enumerate_source` /
`stems_enumerate_source` filter on it, and Preview states whether picks are
set (`preview.lexicon_pick_notes`). This module stays an unused placeholder;
its bodies deliberately raise NotImplementedError. The former `categories_templates.py` /
`categories_msas.py` sibling stubs were the same abandoned "generic-walker
refactor" and were deleted once the closure/plan path proved sufficient.
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
