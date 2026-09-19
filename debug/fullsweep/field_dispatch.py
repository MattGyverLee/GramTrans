"""Feature 035 -- Group E, plane 2: THE LIVE field_source(cls, guid) READER
(T045d of specs/035-fullsweep-fidelity/tasks.md).

``census.census_fields`` (``debug/fullsweep/census.py:274-326``) is injected
with a ``field_source(cls, guid) -> (model_fields, syncable_props)`` callable.
Until this module, NOTHING implemented that callable against live LCM -- every
caller in the repo was a unit-test lambda. This module is the real one.

THE TWO HALVES, AND WHY THEY DO NOT SHARE A ROUTE
--------------------------------------------------
``model_fields`` is the class's full declared field surface -- what COULD be
measured. It comes from the GENERIC metadata-cache route:
``FLExProject.GetFieldID`` / the private ``mdc.GetFields(classID, True,
CellarPropertyTypeFilter.All)`` walk that ``debug/probe_field_census_api.py``
(``_read_field``, ``_census``) already proved out live. This route is the same
for every class; it does not care what the class DOES.

``syncable_props`` is what the transfer engine's own ``GetSyncableProperties``
claims to carry -- and that is NOT dispatchable by LCM class name.
``BaseOperations.GetSyncableProperties`` raises ``NotImplementedError`` unless
a subclass overrides it (flexicon ``BaseOperations.py:1373``, verified live
against installed pyflexicon 4.8.0), and the overrides are reached only
through named, per-domain ``FLExProject`` accessors -- ``proj.POS``,
``proj.Senses``, ``proj.Allomorphs``, ``proj.PhonFeatures``, and the rest of
``CLASS_TO_ACCESSOR`` below. Collapsing the two halves into one route would
destroy the very thing this feature measures: ``engine_omitted = model_fields
- syncable_fields`` is only meaningful if the two sides were read two
different ways.

THE MANDATORY COVERAGE HOLE
----------------------------
``MoAdhocProhibGr``, ``MoAlloAdhocProhib`` and ``MoMorphAdhocProhib`` (the
ad hoc morphosyntactic co-occurrence prohibitions) are handled ONLY by
flexicon's ``Grammar/adhoc_prohibition.py:AdhocProhibition``, an
``LCMObjectWrapper`` -- not a ``BaseOperations`` subclass, and not reachable
through any named ``FLExProject`` accessor. They have no dispatchable
``GetSyncableProperties`` at all. ``field_source`` refuses them up front via
``UnreachableClassError`` (never an empty dict, never a bare crash); callers
building a ``census_fields`` corpus MUST partition classes with
``partition_dispatchable`` first and record these as their own NOT-EVALUATED
bucket (mirroring ``coverage.py``'s ``never_attempted``), exactly the way
FR-109/FR-136 already require elsewhere in this feature.

A NAMING TRAP IN THE SOURCE, RESOLVED BY READING flexicon's OWN FIX
--------------------------------------------------------------------
``MorphRuleOperations.py:469`` and ``Grammar/adhoc_prohibition.py`` both
branch on ``class_name in ("MoAdhocProhibGr", "MoAdhocProhibMorph",
"MoAdhocProhibAllomorph")``. Those last two spellings are NOT LCM class
names -- ``lcm_casting.py:158-175`` documents, in flexicon's own words, that
"Earlier versions of this module spelled the latter two as
IMoAdhocProhibMorph / IMoAdhocProhibAllomorph -- which never existed in LCM"
and that the real names are ``MoMorphAdhocProhib`` (class 102) and
``MoAlloAdhocProhib`` (class 101) -- exactly ``coverage-floor.json``'s
spelling. ``lcm_casting.py`` was fixed to import the real names; the two
``elif class_name in (...)`` sites above were NOT, so their
``MoAdhocProhibMorph``/``MoAdhocProhibAllomorph`` branches can never fire at
runtime (``.ClassName`` never returns those strings) -- a live, pre-existing
flexicon defect this module does not attempt to fix, only avoid inheriting.

OTHER LIVE DEFECTS DISCOVERED WHILE BUILDING THE DISPATCH TABLE
------------------------------------------------------------------
Verified 2026-09-19 against ``Ejagham Mini`` (read-only, pyflexicon 4.8.0):

1. ``self.project.GetMultiStringDict`` is called by SEVEN
   ``GetSyncableProperties`` overrides (``TextOperations`` x3,
   ``SegmentOperations`` x2, ``MediaOperations``, ``WfiGlossOperations``,
   ``WfiMorphBundleOperations``, ``WordformOperations``,
   ``DiscourseOperations``) but is defined NOWHERE on ``FLExProject`` in the
   installed flexicon. Calling ``GetSyncableProperties`` on a ``Text``
   (Title/Description/Source are always-truthy .NET wrapper objects, so this
   fires unconditionally) raises ``AttributeError`` live. Same for ``CmFile``
   (Media), ``Segment``, ``WfiGloss``, ``WfiMorphBundle``, ``WfiWordform``.
2. ``SemanticDomainOperations.GetSyncableProperties`` reads ``item.OcmCodes``
   as if it were a multi-string (``.get_String(...)``); live, ``OcmCodes`` is
   a plain ``str`` on ``CmSemanticDomain``, so this also raises
   ``AttributeError`` unconditionally.
3. ``LexSenseOperations.GetSyncableProperties`` unconditionally emits a
   ``DoNotShowMainEntryInRC`` key (both the ``hasattr`` branch and its
   ``else`` set it) even though live ``hasattr(sense,
   "DoNotShowMainEntryInRC")`` is ``False`` and no such MDC field exists
   under that name for ``LexSense`` -- a phantom key with no backing field.
4. ``ReversalIndexOperations`` and ``ReversalIndexEntryOperations`` do not
   override ``GetSyncableProperties`` at all (absent from the file list that
   greps for the override; confirmed live for ``ReversalIndexOperations``,
   which raises the ``BaseOperations`` stub's own ``NotImplementedError``).
   ``TextTag`` has no ``GetSyncableProperties`` reference anywhere in
   flexicon. All four join the mandatory three in
   ``DISCOVERED_UNREACHABLE_CLASSES``.

None of (1)-(3) are "no dispatch entry" the way the mandatory hole is -- an
accessor genuinely exists and is registered in ``CLASS_TO_ACCESSOR``. They
are attempted and FAIL at the call itself. ``field_source`` therefore wraps
every ``GetSyncableProperties`` call and re-raises any exception as a
``CensusContractError`` naming the class, guid and accessor -- loud and
attributable, never a silently-empty dict, and never a bare traceback from
three frames inside someone else's library.

A THIRD DEFECT PATTERN, AND THE FIX APPLIED HERE (not upstream)
-------------------------------------------------------------------
``FLExProject.Object(guid)`` returns an object statically typed as the base
``ICmObject`` (verified live: ``hasattr(proj.Object(pos_guid), "Name")`` is
``False`` even though the concrete runtime object is a ``PartOfSpeech`` with
a real ``Name``). Some ``GetSyncableProperties`` overrides internally re-cast
their argument (``POSOperations``, ``MSAOperations``, ``PhonFeatureOperations``,
``PossibilityItemOperations``: verified live -- passing the raw ``ICmObject``
gives IDENTICAL output to passing an already-cast object). Others do not
(``MorphRuleOperations.__ResolveObject`` returns a non-int argument
unchanged) -- for those, an uncast ``ICmObject`` would make every
``hasattr(rule, "Name")`` check silently False, exactly the class of bug
CLAUDE.md's flexicon-floor section documents for ``FeaturesOA``. Rather than
audit all 40+ overrides for which ones self-cast, ``field_source`` ALWAYS
explicitly casts via ``getattr(SIL.LCModel, "I" + obj.ClassName)(obj)``
before dispatch (verified live: this turns the ``False`` above into
``True``, and is a no-op for overrides that already self-cast).
"""
from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence

from .census import CensusContractError

__all__ = [
    "UnreachableClassError",
    "MANDATORY_UNREACHABLE_CLASSES",
    "DISCOVERED_UNREACHABLE_CLASSES",
    "UNREACHABLE_CLASSES",
    "CLASS_TO_ACCESSOR",
    "POSSIBILITY_GENERIC_CLASSES",
    "is_dispatchable",
    "partition_dispatchable",
    "model_fields_for_class",
    "build_field_source",
]


class UnreachableClassError(CensusContractError):
    """Raised when ``field_source`` is asked to measure a class with NO
    dispatch entry at all (never an accessor that exists but failed -- that
    case is a plain ``CensusContractError`` from ``build_field_source``'s own
    try/except).

    This is a caller-contract backstop, not a measurement finding: a caller
    that consulted ``partition_dispatchable`` first would never reach here.
    The intended, documented usage is that ``objects_by_class`` fed to
    ``census.census_fields`` NEVER contains one of ``UNREACHABLE_CLASSES`` --
    the caller records those separately as NOT-EVALUATED (mirroring
    ``coverage.py``'s ``never_attempted`` bucket) before it ever calls
    ``census_fields``.
    """

    def __init__(self, cls: str, reason: str):
        super().__init__(
            "[T045d] class %r has no field-census dispatch entry: %s "
            "-- callers MUST exclude this class from census_fields' "
            "objects_by_class and record it as its own NOT-EVALUATED "
            "bucket instead (partition_dispatchable does this split)."
            % (cls, reason)
        )
        self.cls = cls
        self.reason = reason


# ===========================================================================
# THE MANDATORY AND DISCOVERED UNREACHABLE-CLASS HOLES
# ===========================================================================

#: The spec-mandated hole (T045d task text): ad hoc morphosyntactic
#: co-occurrence prohibitions, owned by ``MoMorphData.AdhocCoProhibitionsOC``,
#: handled only by flexicon's non-``BaseOperations`` ``AdhocProhibition``
#: wrapper (``Grammar/adhoc_prohibition.py``). No ``FLExProject`` accessor
#: reaches them; no dispatch entry is possible without inventing one.
MANDATORY_UNREACHABLE_CLASSES: Mapping[str, str] = {
    "MoAdhocProhibGr": (
        "grammatical-feature ad hoc prohibition; owned by "
        "MoMorphData.AdhocCoProhibitionsOC; handled only by flexicon's "
        "Grammar/adhoc_prohibition.py:AdhocProhibition (an LCMObjectWrapper, "
        "not a BaseOperations subclass) -- no GetSyncableProperties exists."
    ),
    "MoAlloAdhocProhib": (
        "allomorph co-occurrence ad hoc prohibition (LCM class 101; "
        "flexicon historically misspelled this MoAdhocProhibAllomorph, a "
        "name that never existed in LCM -- see lcm_casting.py:158-175). "
        "Same AdhocProhibition-only handling as MoAdhocProhibGr; no "
        "GetSyncableProperties exists."
    ),
    "MoMorphAdhocProhib": (
        "morpheme co-occurrence ad hoc prohibition (LCM class 102; "
        "flexicon historically misspelled this MoAdhocProhibMorph, a name "
        "that never existed in LCM -- see lcm_casting.py:158-175). Same "
        "AdhocProhibition-only handling as MoAdhocProhibGr; no "
        "GetSyncableProperties exists."
    ),
}

#: Discovered while building the dispatch table -- NOT mandated by the task
#: text, but the same shape of hole, so it gets the same honest treatment
#: rather than a wrong guess or a silent skip.
DISCOVERED_UNREACHABLE_CLASSES: Mapping[str, str] = {
    "ReversalIndex": (
        "ReversalIndexOperations does not override GetSyncableProperties; "
        "calling it raises BaseOperations' own NotImplementedError stub "
        "(verified live against Ejagham Mini, pyflexicon 4.8.0)."
    ),
    "ReversalIndexEntry": (
        "ReversalIndexEntryOperations does not override "
        "GetSyncableProperties either (absent from the file list that greps "
        "for the override across the whole flexicon package); same "
        "NotImplementedError stub as ReversalIndex, inferred by the same "
        "absence rather than separately live-triggered."
    ),
    "TextTag": (
        "no reference to ITextTag exists anywhere in the installed "
        "flexicon package -- not in any Operations class, not in any "
        "GetSyncableProperties override. There is no accessor to even "
        "attempt."
    ),
}

UNREACHABLE_CLASSES: Mapping[str, str] = {
    **MANDATORY_UNREACHABLE_CLASSES,
    **DISCOVERED_UNREACHABLE_CLASSES,
}


# ===========================================================================
# THE CLASS -> ACCESSOR DISPATCH TABLE
# ===========================================================================

#: LCM class name -> the FLExProject property name whose Operations instance
#: implements GetSyncableProperties for that class. Built from direct source
#: evidence (each override's own docstring/cast target, e.g. "item: The
#: IPartOfSpeech object", or an explicit ``I<Class>(...)`` cast in the
#: method body) -- not guessed. Several accessors cover more than one
#: concrete class (e.g. MSA's four MoXxxMsa subclasses); several classes
#: share one accessor because that accessor's GetSyncableProperties is
#: generic across its whole family (e.g. every PhonRules context subtype).
#:
#: Some entries route to an accessor with a KNOWN live defect (see the
#: module docstring's "OTHER LIVE DEFECTS" section) -- they are kept here
#: because the dispatch entry genuinely exists; build_field_source's
#: try/except turns the resulting crash into a CensusContractError rather
#: than pretending the class has no entry at all.
CLASS_TO_ACCESSOR: Mapping[str, str] = {
    # --- Grammar -----------------------------------------------------------
    "PartOfSpeech": "POS",
    "MoInflClass": "InflectionFeatures",
    "MoStratum": "Strata",
    "PhPhoneme": "Phonemes",
    "PhNCFeatures": "NaturalClasses",
    "PhNCSegments": "NaturalClasses",
    "PhEnvironment": "Environments",
    "FsClosedFeature": "PhonFeatures",
    "MoEndoCompound": "MorphRules",
    "MoExoCompound": "MorphRules",
    "MoInflAffixTemplate": "MorphRules",
    "PhRegularRule": "PhonRules",
    "PhMetathesisRule": "PhonRules",
    "PhSegmentRule": "PhonRules",
    "PhSegRuleRHS": "PhonRules",
    "PhFeatureConstraint": "PhonRules",
    "PhSequenceContext": "PhonRules",
    "PhSimpleContextBdry": "PhonRules",
    "PhSimpleContextNC": "PhonRules",
    "PhSimpleContextSeg": "PhonRules",
    # --- Lexicon -------------------------------------------------------------
    "LexEntry": "LexEntry",
    "LexSense": "Senses",
    "MoStemAllomorph": "Allomorphs",
    "MoAffixAllomorph": "Allomorphs",
    "MoStemMsa": "MSA",
    "MoInflAffMsa": "MSA",
    "MoDerivAffMsa": "MSA",
    "MoUnclassifiedAffixMsa": "MSA",
    "LexExampleSentence": "Examples",
    "LexReference": "LexReferences",
    "CmSemanticDomain": "SemanticDomains",  # KNOWN LIVE DEFECT, see docstring
    "LexPronunciation": "Pronunciations",
    "LexEntryRef": "Variants",
    "LexEtymology": "Etymology",
    # --- Texts/Words ---------------------------------------------------------
    "Text": "Texts",  # KNOWN LIVE DEFECT (GetMultiStringDict), see docstring
    "StText": "Texts",  # degenerate: TextOperations is hasattr-based, an
                         # StText has none of Title/Description/Source/etc,
                         # so this returns {} without reaching the same bug
    "StTxtPara": "Paragraphs",
    "Segment": "Segments",  # KNOWN LIVE DEFECT (GetMultiStringDict)
    "WfiWordform": "Wordforms",  # KNOWN LIVE DEFECT (GetMultiStringDict)
    "WfiAnalysis": "WfiAnalyses",
    "WfiGloss": "WfiGlosses",  # KNOWN LIVE DEFECT (GetMultiStringDict)
    "WfiMorphBundle": "WfiMorphBundles",  # KNOWN LIVE DEFECT (GetMultiStringDict)
    # --- Shared/System ---------------------------------------------------------
    "CmFile": "Media",  # KNOWN LIVE DEFECT (GetMultiStringDict)
    "CmAnthroItem": "Anthropology",
    "CmAgent": "Agents",
}

#: Classes with no dedicated accessor but that are plain ICmPossibility list
#: items -- reachable through the generic PossibilityItemOperations base
#: (Lists/possibility_item_base.py), which flexicon does not expose as a
#: named FLExProject property but which is a fully public, concrete,
#: non-abstract Operations class (verified live: it works unmodified against
#: a live MoMorphType instance, its only unexpected key being the universal
#: "Guid" every possibility-item emits -- handled generically in
#: model_fields_for_class below).
POSSIBILITY_GENERIC_CLASSES: frozenset = frozenset({
    "CmPossibility",
    "LexEntryType",
    "LexEntryInflType",
    "LexRefType",
    "MoMorphType",
    "MoStemName",
})


def is_dispatchable(cls: str) -> bool:
    """True if ``field_source`` has SOME entry for *cls* (an accessor route
    or the generic-possibility route) -- False if it is in
    ``UNREACHABLE_CLASSES`` or in neither table at all (genuinely unmapped,
    a gap this pass did not close; see the T045d review for the list)."""
    if cls in UNREACHABLE_CLASSES:
        return False
    return cls in CLASS_TO_ACCESSOR or cls in POSSIBILITY_GENERIC_CLASSES


def partition_dispatchable(
    classes: Sequence[str],
) -> "tuple[list[str], dict[str, str]]":
    """Split *classes* into (dispatchable, unreachable). ``unreachable`` maps
    class -> reason, drawn from ``UNREACHABLE_CLASSES`` for a recognized hole
    or a generic "not yet mapped" reason for a class in neither table.

    This is the artifact-facing surfacing FR-109/FR-136 pattern requires:
    a caller building ``census_fields``' ``objects_by_class`` should call
    this FIRST, pass only the dispatchable half into ``census_fields``, and
    record ``unreachable`` as its own NOT-EVALUATED bucket -- never silently
    dropped, never faked as an empty measurement.
    """
    dispatchable: list = []
    unreachable: dict = {}
    for cls in classes:
        if cls in UNREACHABLE_CLASSES:
            unreachable[cls] = UNREACHABLE_CLASSES[cls]
        elif cls in CLASS_TO_ACCESSOR or cls in POSSIBILITY_GENERIC_CLASSES:
            dispatchable.append(cls)
        else:
            unreachable[cls] = (
                "no dispatch entry mapped in field_dispatch.CLASS_TO_ACCESSOR "
                "or POSSIBILITY_GENERIC_CLASSES yet -- not one of the "
                "recognized unreachable holes either; a genuine gap in this "
                "pass's coverage, not a measured absence."
            )
    return dispatchable, unreachable


# ===========================================================================
# THE GENERIC model_fields READER (the MDC route, class-name-agnostic)
# ===========================================================================

#: CellarPropertyType codes for owning/reference atomic|collection|sequence
#: properties, and the C#-accessor-suffix convention flexicon's own
#: ``FLExProject.GetFieldID`` strips before an MDC lookup (FLExProject.py:
#: 4246: ``if fieldName[-2:] in ("OA","OS","OC","RA","RS","RC")``). MDC's
#: ``GetFieldName`` returns the BARE name (e.g. "DefaultFeatures"); several
#: GetSyncableProperties overrides emit the SUFFIXED C# property name instead
#: (e.g. "MorphoSyntaxAnalysisRA" -- verified live against LexSense). Both
#: spellings are legitimate names for the same field, so model_fields must
#: contain both, or class_field_coverage's "the two surfaces disagree" raise
#: fires on a naming-convention difference that is not a real coverage gap.
_SUFFIX_BY_CELLAR_TYPE: Mapping[int, str] = {
    23: "OA",  # owning atomic
    24: "RA",  # reference atomic
    25: "OC",  # owning collection
    26: "RC",  # reference collection
    27: "OS",  # owning sequence
    28: "RS",  # reference sequence
}

#: flid<200 is CmObject's own structural fields (Owner, OwnFlid, etc.) --
#: never content, matching debug/probe_field_census_api.py's convention.
_STRUCTURAL_FLID_CEILING = 200


def model_fields_for_class(mdc, cellar_property_type_filter_all: int,
                            class_name: str) -> frozenset:
    """The generic, class-name-agnostic half of field_source: every
    non-structural, non-virtual field *class_name* declares, read through
    the MDC metadata-cache route (FR-051's "every field obtainable from an
    in-scope object's own class, never a hand-listed set").

    For every owning/reference field, BOTH the bare MDC name and its C#
    accessor-suffixed spelling are included (see
    ``_SUFFIX_BY_CELLAR_TYPE``'s docstring), plus a "<bare>Guid" alias for
    the "emit the owned/referenced object's GUID under a synthesized key"
    convention several overrides use (POS's DefaultFeaturesGuid,
    NaturalClassOperations' FeaturesGuid, and so on). "Guid" itself is
    always included: every CmObject has one, several GetSyncableProperties
    overrides emit it (verified live: PossibilityItemOperations always
    does), and it is not an MDC "field" at all -- it is CmObject identity.

    Raises ``CensusContractError`` if the class name is unknown to the MDC,
    or if it enumerates to zero fields -- FR-051: "an unenumerable class is
    not an empty one."
    """
    try:
        clid = mdc.GetClassId(class_name)
    except Exception as exc:  # noqa: BLE001 -- exact LCM exception varies
        raise CensusContractError(
            "[FR-051] the MDC has no class %r: %s" % (class_name, exc)
        ) from exc
    if not clid:
        raise CensusContractError(
            "[FR-051] MDC.GetClassId(%r) returned a falsy class id -- the "
            "class does not exist in this project's metadata cache"
            % (class_name,)
        )

    names: set = set()
    for flid in mdc.GetFields(clid, True, cellar_property_type_filter_all):
        fi = int(flid)
        if fi < _STRUCTURAL_FLID_CEILING or mdc.get_IsVirtual(fi):
            continue
        bare = mdc.GetFieldName(fi)
        names.add(bare)
        suffix = _SUFFIX_BY_CELLAR_TYPE.get(int(mdc.GetFieldType(fi)) & 0x1F)
        if suffix:
            names.add(bare + suffix)
            names.add(bare + "Guid")
    names.add("Guid")

    if not names - {"Guid"}:
        raise CensusContractError(
            "[FR-051] no model fields could be enumerated for class %r; the "
            "census refuses to report coverage it did not measure"
            % (class_name,)
        )
    return frozenset(names)


# ===========================================================================
# THE LIVE field_source(cls, guid) FACTORY
# ===========================================================================

def build_field_source(proj) -> Callable[[str, str], tuple]:
    """Build the live ``field_source(cls, guid)`` callable
    ``census.census_fields`` requires, bound to an ALREADY-OPEN
    ``flexicon.FLExProject`` instance (``proj``). Opens no project of its
    own -- read-only by construction, since it never calls anything but
    ``GetSyncableProperties`` and the MDC metadata reads.

    Callers MUST run ``partition_dispatchable`` over their class roster
    first and only feed the dispatchable half's guids to
    ``census_fields``; calling the returned ``field_source`` with a class in
    ``UNREACHABLE_CLASSES`` raises ``UnreachableClassError`` rather than
    guessing.
    """
    import SIL.LCModel as lcm  # noqa: PLC0415 -- lazy: no LCM import at module load
    from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged  # noqa: PLC0415
    from SIL.LCModel.Core.Cellar import CellarPropertyTypeFilter  # noqa: PLC0415

    mdc = IFwMetaDataCacheManaged(proj.Cache.MetaDataCacheAccessor)
    cpt_all = int(CellarPropertyTypeFilter.All)

    # Lazily constructed: PossibilityItemOperations is not exposed as a
    # named FLExProject accessor, so classes in POSSIBILITY_GENERIC_CLASSES
    # get their own fresh instance, built once and reused.
    _possibility_ops: list = []

    def _possibility_operations():
        if not _possibility_ops:
            from flexicon.code.Lists.possibility_item_base import (  # noqa: PLC0415
                PossibilityItemOperations,
            )
            _possibility_ops.append(PossibilityItemOperations(proj))
        return _possibility_ops[0]

    def _cast(raw):
        """Explicitly promote *raw* (whatever proj.Object() handed back,
        typically statically-typed as the base ICmObject -- verified live,
        see module docstring) to its concrete SIL.LCModel interface, so
        hasattr-based GetSyncableProperties overrides see the real surface
        rather than ICmObject's near-empty one."""
        iface = getattr(lcm, "I" + raw.ClassName, None)
        if iface is None:
            return raw
        try:
            return iface(raw)
        except Exception:  # noqa: BLE001 -- fall back to the raw object
            return raw

    def field_source(cls: str, guid: str) -> tuple:
        if cls in UNREACHABLE_CLASSES:
            raise UnreachableClassError(cls, UNREACHABLE_CLASSES[cls])

        model = model_fields_for_class(mdc, cpt_all, cls)

        accessor_name = CLASS_TO_ACCESSOR.get(cls)
        if accessor_name is not None:
            ops = getattr(proj, accessor_name)
        elif cls in POSSIBILITY_GENERIC_CLASSES:
            ops = _possibility_operations()
        else:
            raise CensusContractError(
                "[T045d] no dispatch entry for class %r -- callers must "
                "call partition_dispatchable() before building "
                "objects_by_class, so this call should never happen for a "
                "class this pass did not map" % (cls,)
            )

        raw = proj.Object(guid)
        obj = _cast(raw)
        try:
            props = ops.GetSyncableProperties(obj)
        except Exception as exc:  # noqa: BLE001 -- any failure is reported, not eaten
            raise CensusContractError(
                "[T045d] GetSyncableProperties raised for class %r guid %r "
                "via accessor %r: %s: %s -- this is a live flexicon defect "
                "in that accessor (see field_dispatch module docstring's "
                "\"OTHER LIVE DEFECTS\" section for known cases), not a "
                "clean empty measurement"
                % (cls, guid, accessor_name or "PossibilityItemOperations",
                   type(exc).__name__, exc)
            ) from exc

        return model, props

    return field_source
