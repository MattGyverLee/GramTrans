"""Feature 035 -- Group E, plane 2: THE GENERIC PER-OBJECT FIELD CENSUS
(T037 of specs/035-fullsweep-fidelity/tasks.md Phase 5 / US2).

This is the *field*-level accounting plane. Plane 1 (object presence/absence,
``compare.py``) answers "is this source object in the target at all". Plane 2
answers "and is every field on it faithful". FR-093 keeps the two planes
separate; nothing here reports object presence.

The governing constraint is FR-051: the census ranges over **every field
obtainable from an in-scope object's own class**, never a hand-listed set of
fields chosen per class. A hand-list cannot grow when the model grows, so it
silently stops measuring; an enumeration can, and MUST report the growth.

Two field sets, and the difference between them is the whole point:

  * ``model_fields``    -- every field the class exposes (the LCM metadata
                          enumeration). What COULD be measured.
  * ``syncable_fields`` -- what the transfer engine's own
                          ``GetSyncableProperties`` surface returns for that
                          class. What the engine claims to carry.

``engine_omitted = model_fields - syncable_fields`` is therefore the set of
fields the engine deliberately does not carry. FR-052 and FR-066 require that
set to be **enumerated per class on every artifact**, and any growth of it
between runs to be reported as reduced coverage -- never silently absorbed.
That is ``omitted_growth`` below, and it is why this module records the omitted
set rather than merely subtracting it.

EFFECTIVE exclusion for a class (FR-066) is exactly:

    roster entries for that class   (contracts/expected-divergent.json, T038)
  U engine_omitted for that class   (measured, not assumed)

and so the compared set is ``syncable_fields - roster_excluded``.

LCM ACCESS IS INJECTED. ``census_fields`` takes a ``field_source`` callable, the
same pattern ``moves.run_double_move`` uses for ``census``: the live
implementation reaches the database, and a test supplies a fake. Nothing in this
module imports LCM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ROSTER_PATH = (
    _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts" / "expected-divergent.json"
)

#: FR-063 -- the tool appends this line to a Carrier-B ``Description`` on every
#: run. The prose around it is still compared; the tag segment itself is never
#: reported as a mismatch.
DEFAULT_TAG_LINE_MARKER = "[GT-Tag]: "


class CensusContractError(RuntimeError):
    """The census could not be constructed as specified -- a malformed roster,
    or a field source that cannot enumerate a class's fields at all. Distinct
    from an ordinary fidelity failure: this means the MEASUREMENT is broken, so
    it must reach the caller as a harness error rather than a clean pass
    (FR-051: an unenumerable class is not an empty one)."""


# ===========================================================================
# THE EXPECTED_DIVERGENT ROSTER (T038's artifact, loaded here)
# ===========================================================================

@dataclass(frozen=True)
class ExpectedDivergentRoster:
    """contracts/expected-divergent.json, parsed. FR-052/FR-053/FR-066."""

    schema_version: int
    excluded: Mapping[str, frozenset]
    compared_not_excluded: Mapping[str, frozenset]
    tag_line_marker: str
    carrier_a_fields: frozenset
    carrier_b_fields: frozenset
    source_path: str

    def excluded_for(self, cls: str) -> frozenset:
        """The roster's OWN entries for a class. NOT the effective exclusion --
        that additionally includes the engine's omitted set (FR-066), which is
        measured per run and so lives on ``ClassFieldCoverage``."""
        return self.excluded.get(cls, frozenset())

    def is_roster_excluded(self, cls: str, field: str) -> bool:
        return field in self.excluded_for(cls)


def load_expected_divergent(path: Optional[Path] = None) -> ExpectedDivergentRoster:
    """Load and validate the roster. Raises rather than degrading: a comparator
    running without its exclusion roster would report every excluded field as
    loss, which is worse than not running (FR-052 permits no other exclusion
    mechanism, so an absent roster is not "no exclusions")."""
    p = Path(path) if path is not None else DEFAULT_ROSTER_PATH
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CensusContractError(
            "[FR-052] the EXPECTED_DIVERGENT roster is REQUIRED and was not "
            "found at %r; refusing to run a field census with no exclusion "
            "roster (every excluded field would be reported as loss)" % (str(p),)
        ) from exc
    except (ValueError, OSError) as exc:
        raise CensusContractError(
            "[FR-052] the EXPECTED_DIVERGENT roster at %r is unreadable: %s"
            % (str(p), exc)
        ) from exc

    if not isinstance(raw, dict):
        raise CensusContractError("[FR-052] roster root must be an object")
    if raw.get("schema_version") != 1:
        raise CensusContractError(
            "[FR-052] roster schema_version must be 1, got %r"
            % (raw.get("schema_version"),)
        )

    excluded: dict = {}
    for i, e in enumerate(raw.get("entries") or []):
        if not isinstance(e, dict):
            raise CensusContractError("[FR-052] roster entry %d is not an object" % i)
        for key in ("class", "field", "rationale"):
            if not e.get(key):
                raise CensusContractError(
                    "[FR-052] roster entry %d is missing a non-empty %r; every "
                    "exclusion MUST carry its rationale, because promoting a "
                    "field onto this roster is a recorded, reviewable act "
                    "(FR-056)" % (i, key)
                )
        excluded.setdefault(e["class"], set()).add(e["field"])

    compared: dict = {}
    for e in raw.get("compared_not_excluded") or []:
        if isinstance(e, dict) and e.get("class") and e.get("field"):
            compared.setdefault(e["class"], set()).add(e["field"])

    # A field cannot be both excluded and explicitly compared -- that would make
    # the roster self-contradictory and the verdict depend on lookup order.
    for cls, fields in compared.items():
        clash = fields & excluded.get(cls, set())
        if clash:
            raise CensusContractError(
                "[FR-052] roster is self-contradictory for class %r: %s appear "
                "in BOTH entries (excluded) and compared_not_excluded"
                % (cls, ", ".join(sorted(clash)))
            )

    strip = raw.get("tag_stripping") or {}
    marker = ((strip.get("carrier_b") or {}).get("line_marker")
              or DEFAULT_TAG_LINE_MARKER)
    return ExpectedDivergentRoster(
        schema_version=1,
        excluded={k: frozenset(v) for k, v in excluded.items()},
        compared_not_excluded={k: frozenset(v) for k, v in compared.items()},
        tag_line_marker=marker,
        carrier_a_fields=frozenset((strip.get("carrier_a") or {}).get("fields") or ()),
        carrier_b_fields=frozenset((strip.get("carrier_b") or {}).get("fields") or ()),
        source_path=str(p),
    )


def strip_provenance_tag(value, roster: ExpectedDivergentRoster):
    """FR-063: remove the tool's own appended tag segment so the SURROUNDING
    prose can be compared, and so the tag itself is never reported as a
    mismatch. Only whole marker-led lines are removed; a line that merely
    mentions the marker mid-sentence is prose and is kept.

    Non-strings pass through untouched -- this is a text rule, not a coercion.
    """
    if not isinstance(value, str):
        return value
    marker = roster.tag_line_marker
    lines = value.splitlines()
    kept = [ln for ln in lines if not ln.lstrip().startswith(marker)]
    if len(kept) == len(lines):
        return value
    return "\n".join(kept).strip()


# ===========================================================================
# PER-CLASS COVERAGE: what could be measured vs what the engine carries
# ===========================================================================

@dataclass(frozen=True)
class ClassFieldCoverage:
    """One class's field accounting, as it appears on every artifact (FR-052)."""

    cls: str
    model_fields: tuple
    syncable_fields: tuple
    engine_omitted: tuple
    roster_excluded: tuple
    compared: tuple

    def as_dict(self) -> dict:
        return {
            "model_field_count": len(self.model_fields),
            "syncable_fields": list(self.syncable_fields),
            "engine_omitted": list(self.engine_omitted),
            "roster_excluded": list(self.roster_excluded),
            "compared": list(self.compared),
        }


def class_field_coverage(
    cls: str,
    model_fields: Iterable[str],
    syncable_fields: Iterable[str],
    roster: ExpectedDivergentRoster,
) -> ClassFieldCoverage:
    """FR-051/FR-052/FR-066. ``compared`` is ``syncable - roster_excluded``: the
    engine's own surface bounds what CAN be compared, and the roster removes
    from that what is legitimately expected to differ.

    An empty ``model_fields`` is a measurement defect, not an empty class: it
    means the field source could not enumerate the class, and proceeding would
    report full coverage over nothing.
    """
    model = frozenset(model_fields)
    if not model:
        raise CensusContractError(
            "[FR-051] no model fields could be enumerated for class %r; the "
            "census refuses to report coverage it did not measure" % (cls,)
        )
    syncable = frozenset(syncable_fields)
    unknown = syncable - model
    if unknown:
        raise CensusContractError(
            "[FR-051] the engine's syncable surface for class %r returned "
            "field(s) absent from the class's own model enumeration: %s -- the "
            "two surfaces disagree, so neither the omitted set nor the compared "
            "set is trustworthy" % (cls, ", ".join(sorted(unknown)))
        )
    excluded = roster.excluded_for(cls)
    return ClassFieldCoverage(
        cls=cls,
        model_fields=tuple(sorted(model)),
        syncable_fields=tuple(sorted(syncable)),
        engine_omitted=tuple(sorted(model - syncable)),
        roster_excluded=tuple(sorted(excluded)),
        compared=tuple(sorted(syncable - excluded)),
    )


# ===========================================================================
# THE CENSUS ITSELF
# ===========================================================================

@dataclass
class FieldCensus:
    """Per-class, per-object field values plus the per-class coverage block that
    FR-052 requires on every artifact."""

    values: dict           # class -> guid -> {field: value}
    coverage: dict         # class -> ClassFieldCoverage

    def omitted_by_class(self) -> dict:
        """The artifact's enumerated omitted set (FR-052/FR-066)."""
        return {c: list(cov.engine_omitted) for c, cov in sorted(self.coverage.items())}

    def as_dict(self) -> dict:
        return {
            "classes_measured": sorted(self.coverage),
            "object_count": sum(len(v) for v in self.values.values()),
            "coverage": {c: cov.as_dict() for c, cov in sorted(self.coverage.items())},
            "engine_omitted_by_class": self.omitted_by_class(),
        }


def census_fields(
    objects_by_class: Mapping[str, Iterable[str]],
    *,
    field_source: Callable[[str, str], tuple],
    roster: ExpectedDivergentRoster,
) -> FieldCensus:
    """Walk every in-scope object and record every COMPARED field's value.

    ``field_source(cls, guid)`` returns ``(model_fields, syncable_props)`` where
    ``syncable_props`` is the ``GetSyncableProperties`` dict for that object.
    Its keys establish the class's syncable surface; its values are the payload.

    Per-class coverage is computed from the FIRST object of that class and then
    held fixed: the syncable surface is a property of the class, so an object
    whose surface disagrees with its siblings is a defect worth raising rather
    than averaging away.

    FR-063 tag-stripping is applied to Carrier-B fields as values are recorded,
    so downstream comparison never sees the tool's own tag.
    """
    values: dict = {}
    coverage: dict = {}
    for cls in sorted(objects_by_class):
        guids = list(objects_by_class[cls] or ())
        per_object: dict = {}
        for guid in guids:
            model_fields, props = field_source(cls, guid)
            if not isinstance(props, Mapping):
                raise CensusContractError(
                    "[FR-051] field source for %s/%s returned a non-mapping "
                    "syncable-properties value (%r)"
                    % (cls, guid, type(props).__name__)
                )
            cov = class_field_coverage(cls, model_fields, props.keys(), roster)
            if cls not in coverage:
                coverage[cls] = cov
            elif cov.syncable_fields != coverage[cls].syncable_fields:
                raise CensusContractError(
                    "[FR-051] class %r exposed two different syncable surfaces "
                    "within one run (object %s): %s vs %s -- the omitted set is "
                    "not well defined for this class"
                    % (cls, guid, list(coverage[cls].syncable_fields),
                       list(cov.syncable_fields))
                )
            compared = coverage[cls].compared
            per_object[guid] = {
                f: (strip_provenance_tag(props[f], roster)
                    if f in roster.carrier_b_fields else props[f])
                for f in compared if f in props
            }
        if guids:
            values[cls] = per_object
    return FieldCensus(values=values, coverage=coverage)


# ===========================================================================
# COVERAGE REGRESSION: growth of the omitted set (FR-052 / FR-066)
# ===========================================================================

def omitted_growth(previous: Mapping[str, Iterable[str]],
                   current: Mapping[str, Iterable[str]]) -> dict:
    """FR-052/FR-066: any GROWTH of the engine-omitted set between runs is
    reduced coverage and MUST be reported, never silently absorbed.

    Shrinkage is not a failure -- the engine started carrying something it used
    to skip -- but it is recorded, because a reader comparing two artifacts
    should not have to diff them by hand.

    A class present now and absent before is NOT growth: it was never measured,
    so there is no baseline to have regressed against. It is reported under
    ``classes_new`` so the distinction stays visible.
    """
    prev = {c: frozenset(f or ()) for c, f in (previous or {}).items()}
    cur = {c: frozenset(f or ()) for c, f in (current or {}).items()}
    grew: dict = {}
    shrank: dict = {}
    for cls in sorted(set(prev) & set(cur)):
        added = cur[cls] - prev[cls]
        removed = prev[cls] - cur[cls]
        if added:
            grew[cls] = sorted(added)
        if removed:
            shrank[cls] = sorted(removed)
    return {
        "coverage_reduced": bool(grew),
        "grew": grew,
        "shrank": shrank,
        "classes_new": sorted(set(cur) - set(prev)),
        "classes_absent_now": sorted(set(prev) - set(cur)),
    }
