"""Feature 038, Phase 10 Wave 1 (T114-T118) -- the OWNER-ATTRIBUTION probe.

WHY ONE DRIVER FOR FIVE TASKS, AND WHY THAT IS NOT A SHORTCUT.

T114 (`Fs*`), T115 (`CmPossibility`), T116 (the phonological-context family)
and T118 (the six stragglers) are four separate tasks, but they ask ONE
question in four costumes: *for class X, who owns the instances?* A class does
not transfer or fail to transfer on its own -- it rides on an owner, and the
owner decides the route. Attributing per class and then guessing the owner is
how T107 came to build a create path on the affix-process route for a class
whose loss was on the phonological-rule route; the class stayed red on two
pairs and the work was correct-but-aimed-wrong.

So this probe answers the shared question once per project, exactly, and lets
each task read its own rows out of the same measurement. That also makes the
four attributions MUTUALLY CONSISTENT by construction: `PhSimpleContextNC`'s
owner counts and `MoAffixProcess`'s own count come from the same pass, so a
claim like "the contexts are lost because their owner is lost" is arithmetic
here rather than inference.

WHAT IT MEASURES.

For every class in RESIDUE it takes `I<Class>Repository.AllInstances()` (via
`project.ObjectsIn`), filters to the EXACT `ClassName`, and groups the
survivors by `(owning class, owning field, flid)`. The exact-class filter is
not tidying: `AllInstances()` returns the whole inheritance subtree, which is
precisely the defect T023b fixed after `ICmPossibilityRepository` once read
3014 against 302 own objects. The `subtree_total` is reported ALONGSIDE
`exact_class` so the polymorphic gap stays visible instead of being silently
corrected away -- that gap IS T115's first question.

Three enrichments, each earning its place:

* `possibility_lists` -- for `CmPossibility` / `LexEntryType` /
  `LexEntryInflType`, walk up to the owning `ICmPossibilityList` and name it by
  its owning field AND its `Name`. T115's task text is explicit that the first
  question is "what are they", not "why are they lost": a fix authored against
  `CmPossibility` as though it were a thing would be a fix against a bucket.
* `feature_structure` -- for the classes that OWN an `IFsFeatStruc`, count how
  many actually carry one. Run against source and destination, this is what
  turns "the structures do not transfer" into "these owners arrive hollow".
* `flid` -- the raw field id next to the resolved name, because a resolved
  field NAME is a metadata lookup that can mislead, and the flid is the thing
  LCM actually keyed on.

READ-ONLY. It opens the project, enumerates, and writes ONE json file. It never
touches the database, which is what makes it safe to point at a sanctioned
read-only pair rather than a throwaway.

Usage (via FlexTools / the MCP runner, once per project):

    import os
    os.environ["GT038_PROBE_OUT"] = r"<a directory>"
    g = {}
    exec(open(r"debug/run038_phase10_owner_probe.py").read(), g)
    g["Main"](project, report, modifyAllowed)

Writes `<GT038_PROBE_OUT>/owner-probe-<project>.json`.
"""
import json
import os

import SIL.LCModel as lcm
from SIL.LCModel import ICmObject

#: The 16-class P5 residue re-measured 2026-08-26, plus the CONTEXT classes a
#: reader needs to interpret it: the `Fs*` definitions that DO transfer
#: (`FsSymFeatVal`, `FsClosedFeature`, `FsFeatStrucType`), the owners the
#: contexts hang off (`PhRegularRule`, `PhMetathesisRule`, `MoAffixProcess`),
#: and the feature-structure owners (`MoStemMsa`, `MoInflAffMsa`,
#: `PartOfSpeech`, `PhPhoneme`, `PhNCFeatures`). Context classes are here so
#: the attribution can be CHECKED, not padded: `PhSimpleContextNC` owned by
#: `MoAffixProcess.Input` is only an explanation of the loss if
#: `MoAffixProcess` is itself lost, and that number has to be in the same file.
RESIDUE = [
    "FsFeatStruc", "FsClosedValue", "FsSymFeatVal", "FsClosedFeature",
    "FsFeatStrucType", "CmPossibility",
    "PhSequenceContext", "PhSimpleContextNC", "PhSimpleContextSeg",
    "PhSimpleContextBdry", "PhSegRuleRHS", "PhFeatureConstraint",
    "PhCode", "PhPhoneme", "PhNCFeatures", "PhRegularRule", "PhMetathesisRule",
    "MoStemMsa", "MoInflAffMsa", "LexEntryType", "LexEntryInflType",
    "LexReference", "MoAffixProcess", "CmFile", "CmFolder", "PartOfSpeech",
]

#: Classes whose owned feature structure is the thing Phase 10 is chasing.
_FEATURE_OWNERS = ("MoStemMsa", "MoInflAffMsa", "PartOfSpeech", "PhPhoneme",
                   "PhNCFeatures")

#: Classes for which the owning possibility LIST is the identifying fact.
_LIST_MEMBERS = ("CmPossibility", "LexEntryType", "LexEntryInflType")

#: The four spellings LCM uses for "the feature structure this object owns".
_FEATURE_FIELDS = ("FeaturesOA", "MsFeaturesOA", "InflFeatsOA",
                   "DefaultFeaturesOA")


def _best(multi):
    """`BestAnalysisAlternative.Text`, or None when the field will not say."""
    try:
        return multi.BestAnalysisAlternative.Text
    except Exception:
        return None


def _field_label(obj_as_cmobject, mdc):
    """`OwningClass.Field (flid=N)`, plus the RUNTIME owner when it differs.

    The runtime owner matters and is not cosmetic: `PhCode` resolves its owning
    field to `PhTerminalUnit.Codes`, but the runtime owner is what separates
    the phoneme codes from the BOUNDARY-MARKER codes, and a fix scoped to
    phonemes would silently leave the latter behind.
    """
    flid = obj_as_cmobject.OwningFlid
    owner = obj_as_cmobject.Owner
    runtime = getattr(owner, "ClassName", None) if owner is not None else None
    if not flid:
        return "(unowned) [runtime=%s]" % runtime
    own_cls = mdc.GetOwnClsName(flid)
    label = "%s.%s (flid=%s)" % (own_cls, mdc.GetFieldName(flid), flid)
    if runtime and own_cls and runtime != own_cls:
        label += " [runtime=%s]" % runtime
    return label


def _list_identity(obj, mdc):
    """Name the `ICmPossibilityList` this item ultimately lives in.

    Walks owners upward -- items nest via `SubPossibilities`, so the list is
    not necessarily the direct owner. Bounded at 40 hops so an unexpected
    ownership chain cannot hang the probe.
    """
    current = obj
    for _ in range(40):
        if current is None:
            return None
        if getattr(current, "ClassName", None) == "CmPossibilityList":
            try:
                where = _field_label(ICmObject(current), mdc)
            except Exception:
                where = "(?)"
            return "%s | name=%r" % (where, _best(getattr(current, "Name", None)))
        try:
            current = ICmObject(current).Owner
        except Exception:
            return None
    return None


def _feature_structure_of(obj):
    """Which feature-structure field this object actually carries, if any."""
    for field in _FEATURE_FIELDS:
        try:
            value = getattr(obj, field, None)
        except Exception:
            continue
        if value is not None:
            return field
    return None


def _project_name(project):
    """The project's name as a STRING.

    `FLExProject.ProjectName` is a bound METHOD, not a property, so the
    obvious `getattr(project, "ProjectName", None)` yields a repr like
    `<bound method ...>` and silently names the output file after a memory
    address. Call it when it is callable, and fall back rather than raise.
    """
    value = getattr(project, "ProjectName", None)
    if callable(value):
        try:
            value = value()
        except Exception:
            value = None
    return str(value) if value else "unknown"


def Main(project, report, modifyAllowed):
    mdc = project.Cache.MetaDataCacheAccessor
    out_dir = os.environ.get("GT038_PROBE_OUT") or "."
    name = _project_name(project)
    result = {"project": name, "classes": {}}

    for cls in RESIDUE:
        iface = getattr(lcm, "I" + cls + "Repository", None)
        if iface is None:
            result["classes"][cls] = {
                "error": "SIL.LCModel exposes no I%sRepository" % cls}
            continue
        try:
            subtree = list(project.ObjectsIn(iface))
        except Exception as exc:
            result["classes"][cls] = {"error": "ObjectsIn raised: %r" % (exc,)}
            continue

        exact = [o for o in subtree if getattr(o, "ClassName", None) == cls]
        owners, lists, feats = {}, {}, {}
        for obj in exact:
            try:
                label = _field_label(ICmObject(obj), mdc)
            except Exception as exc:
                label = "ERROR:%r" % (exc,)
            owners[label] = owners.get(label, 0) + 1

            if cls in _LIST_MEMBERS:
                key = _list_identity(obj, mdc) or "(no owning list)"
                lists[key] = lists.get(key, 0) + 1
            if cls in _FEATURE_OWNERS:
                key = _feature_structure_of(obj) or "(none)"
                feats[key] = feats.get(key, 0) + 1

        record = {
            "subtree_total": len(subtree),
            "exact_class": len(exact),
            "owners": dict(sorted(owners.items(), key=lambda kv: -kv[1])),
        }
        if lists:
            record["possibility_lists"] = dict(
                sorted(lists.items(), key=lambda kv: -kv[1]))
        if feats:
            record["feature_structure"] = dict(
                sorted(feats.items(), key=lambda kv: -kv[1]))
        result["classes"][cls] = record

    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(name))
    path = os.path.join(out_dir, "owner-probe-%s.json" % safe)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    report.Info("WROTE %s" % path)
    report.Info("classes measured: %d" % len(result["classes"]))
