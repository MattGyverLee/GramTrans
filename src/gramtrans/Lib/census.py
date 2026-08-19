"""Feature 038 -- the per-object-class fidelity census (FR-009..FR-013).

THE CONTRACT THIS IMPLEMENTS
---------------------------
- `specs/038-transfer-fidelity-gaps/contracts/fidelity-census.md` -- the human
  contract, including every rule the schema cannot express.
- `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json` --
  the sole authority for anything EMITTED. Every object in it is
  `additionalProperties: false`, so an extra key is a hard validation failure
  rather than a harmless addition.
- `tests/integration/test_object_census.py` -- the executable specification of
  the symbol surface below.

TWO NAMING LAYERS, ON PURPOSE (see `Lib/models.py`'s feature-038 block). The
in-memory dataclasses keep `data-model.md`'s field names; the artifact uses the
schema's. The reconciliation is `models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS` and
its two siblings, and the emitters here are driven BY those tables -- there is
deliberately no third, hand-written set of names.

THE VOCABULARIES ARE RE-EXPORTS, NEVER RE-DECLARATIONS. `REASON_TOKENS` and
friends are bound to the `CENSUS_*` constants in `models.py`. The dependency
direction is census -> models and never the reverse (models has to reject an
out-of-vocabulary token at construction, and cannot import from here), so one
literal list carries two names and cannot drift.

NO LIVE-FLEx IMPORT AT MODULE SCOPE. Every `flexicon` / `SIL.LCModel` /
`FLExInit` import in this module is function-level. That is load-bearing, not
style: `tests/integration/test_object_census.py` imports this module and must
stay runnable with no FieldWorks host and no project (it currently collects in
under a second), and `tests/integration/test_034_standalone_preview_live.py`
demonstrates what an unconditional `FLExInitialize()` at import time does to a
test session on this machine (`Windows fatal exception: access violation`).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import (
    CENSUS_NOT_EVALUATED_REASONS,
    CENSUS_REASON_TOKENS,
    CENSUS_REASONS_NOT_REQUIRING_REPORT_REF,
    CENSUS_ROW_VERDICT_CLASSES,
    CENSUS_SCHEMA_VERSION as _MODELS_CENSUS_SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# Re-exported vocabularies (T020 assigns the rest; these three are needed from
# T016 onward because the class-list loader stamps NOT_EVALUATED reasons).
#
# RE-EXPORT, NOT RE-DECLARATION. `models.py` owns the literals.
# ---------------------------------------------------------------------------

#: `census-artifact.schema.json` top-level `schema_version`.
CENSUS_SCHEMA_VERSION: int = _MODELS_CENSUS_SCHEMA_VERSION

#: FR-013's closed 16-token reason vocabulary, in schema enum order.
REASON_TOKENS: tuple = CENSUS_REASON_TOKENS

#: The four tokens exempt from `accountedLine.report_ref` (R-1).
REASONS_NOT_REQUIRING_REPORT_REF: frozenset = (
    CENSUS_REASONS_NOT_REQUIRING_REPORT_REF
)

#: The three reasons that make a row NOT_EVALUATED rather than measured.
NOT_EVALUATED_REASONS: frozenset = CENSUS_NOT_EVALUATED_REASONS

#: `$defs.classRow.verdict_class.enum`.
ROW_VERDICT_CLASSES: tuple = CENSUS_ROW_VERDICT_CLASSES


# ---------------------------------------------------------------------------
# Failure types
#
# Each carries the VERDICT it maps to, so a caller never has to re-derive the
# verdict from an exception class name, and every message names the offending
# class (CP-1..CP-4 all fail "by class name").
# ---------------------------------------------------------------------------


class CensusFailure(Exception):
    """Base for a census failure that has a verdict token."""

    #: Overridden per subclass; one of the nine `verdictToken` members.
    verdict: str = "CENSUS_ERROR"

    def __init__(self, message: str, classes: tuple = ()) -> None:
        super().__init__(message)
        #: The classes this failure names. Never empty for CP-1/CP-4.
        self.classes: tuple = tuple(classes)


class CoverageIncomplete(CensusFailure):
    """CP-1 derivation mismatch, a missing `classes` row, or a class present in
    BOTH the 035 coverage floor and this feature's additions ledger (CP-4).

    Verdict `COVERAGE_INCOMPLETE`, exit 6. FR-012 coverage is PROVEN, not
    asserted: the derivation runs on every census invocation rather than being
    pinned to a stored digest, so drift in the truth source cannot pass
    unnoticed.
    """

    verdict = "COVERAGE_INCOMPLETE"


class CensusError(CensusFailure):
    """An R-1/R-2 accounting violation, a Section 8 tally mismatch, an
    `fwdata_sha256` that changed under the census, a mis-declared baseline
    kind, an unclassifiable reason, or an unhandled exception.

    Verdict `CENSUS_ERROR`, exit 7.
    """

    verdict = "CENSUS_ERROR"


# ---------------------------------------------------------------------------
# Truth-source locations (fidelity-census.md 3.1)
#
# 038 READS these. 038 does not fork them: the floor and the natural-key
# roster are owned by feature 035, and edits to either are coordinated with
# that live session.
# ---------------------------------------------------------------------------

INVENTORY_DOCUMENT = "specs/035-fullsweep-fidelity/object-inventory.md"
COVERAGE_FLOOR_DOCUMENT = (
    "specs/035-fullsweep-fidelity/contracts/coverage-floor.json"
)
NATURAL_KEY_ROSTER_DOCUMENT = (
    "specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json"
)

#: The tables of `object-inventory.md` the class list is derived from. TABLE 3
#: (ride-along owned children) and TABLE 4 (writing-system / configuration
#: artifacts) are deliberately NOT derivation inputs -- see `CENSUS_ADDITIONS`,
#: where `PhCode` is carried explicitly precisely because it lives in TABLE 3.
DERIVATION_TABLES: tuple = ("TABLE 1", "TABLE 2")

#: `$defs.classRow.inventory_tables` tokens, keyed by the heading above.
_INVENTORY_TABLE_TOKENS = {
    "TABLE 1": "TABLE_1",
    "TABLE 2": "TABLE_2",
    "TABLE 3": "TABLE_3",
    "TABLE 4": "TABLE_4",
}

#: An LCM class name as the inventory writes it: an initial capital, then
#: letters and digits only. Deliberately strict, so prose cells ("Writing
#: system", "(no object created)", "(reference CREATE arm)") cannot be mistaken
#: for classes -- the derivation is an equality proof and a false positive in it
#: is a failed census run, not a warning.
_CLASS_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")


# ---------------------------------------------------------------------------
# CP-3 / CP-4 ledgers
# ---------------------------------------------------------------------------

#: CP-4 -- the three classes measured in `census-evidence.md` section 0 that are
#: absent from the 035 floor. Each is `owed_to_035: true`: the addition must be
#: dropped in the same change that adds it to the floor, so the ledger cannot
#: rot into a second truth source (a class in BOTH is `COVERAGE_INCOMPLETE`).
CENSUS_ADDITIONS: tuple = (
    {
        "class": "MoAffixProcess",
        "rationale": (
            "Absent from object-inventory.md entirely, because the engine has "
            "no create path for it -- the class the transfer silently "
            "downgraded. A truth-source gap, not a corpus gap."
        ),
        "measured_evidence": "Ejagham 13 -> 0, Ngoreme 1 -> 0",
        "owed_to_035": True,
    },
    {
        "class": "PhCode",
        "rationale": (
            "object-inventory.md TABLE 3 (ride-along): flexicon's phoneme "
            "GetSyncableProperties explicitly does not include CodesOS, so "
            "nothing carries it and nothing reports the drop."
        ),
        "measured_evidence": "43 -> 25, 89 -> 25",
        "owed_to_035": True,
    },
    {
        "class": "CmTranslation",
        "rationale": (
            "Reached through the texts path; never projected into the floor."
        ),
        "measured_evidence": "Ngoreme 7925 -> 2",
        "owed_to_035": True,
    },
)

#: CP-3 -- the classes `object-inventory.md` TABLE 2 records as NEVER created
#: by any path. They are `gate_scope: "advisory"` and cannot by themselves fail
#: the gate; SC-005's scope is exactly the `required` set.
NEVER_CREATED_CLASSES: frozenset = frozenset({
    "LexRefType", "LexAppendix", "PhBdryMarker",
})

#: Classes that get a NOT_EVALUATED row with a stated reason rather than a
#: measurement. `MoForm` / `MoMorphSynAnalysis` are abstract LCM bases with no
#: factory (035's `excluded_not_measurable`); `CmAnthroItem` is in the floor but
#: out of THIS feature's scope, so its measured 859 -> 0 on Ejagham stays
#: visible and is explicitly not counted against the gate.
NOT_EVALUATED_CLASS_REASONS: dict = {
    "MoForm": "ABSENT_BY_CONSTRUCTION",
    "MoMorphSynAnalysis": "ABSENT_BY_CONSTRUCTION",
    "CmAnthroItem": "OUT_OF_SCOPE_CLASS",
}

#: CP-1's arithmetic: `in_scope_classes` (69) + `census_additions` (3). Held as
#: a constant so a change in either truth source has to be a deliberate edit
#: here as well as there.
#:
#: NOTE ON THE TWO COUNTS. This is the REQUIRED class count of
#: fidelity-census.md 3.2 ("therefore 72"). It is NOT necessarily
#: `len(classes)`: the same section also requires a NOT_EVALUATED row for each
#: `excluded_not_measurable` class, and `$defs.classRow.in_class_list_via` has
#: an `"excluded_not_measurable"` member precisely so those rows can say how
#: they got in. The artifact's `required_class_count` is therefore emitted as
#: the ROW count (invariant 1 is `len(classes) == required_class_count` and is
#: what the validator enforces); `REQUIRED_CLASS_COUNT` stays the CP-1 figure.
REQUIRED_CLASS_COUNT: int = 72


# ---------------------------------------------------------------------------
# Locating the truth sources
# ---------------------------------------------------------------------------


def repo_root(start: Optional[Path] = None) -> Path:
    """The repository root, found by walking UP for the 035 contracts.

    Walked rather than hard-coded so the census runs from a worktree, a
    checkout, or an editable install without a path constant to keep in sync.
    """
    base = Path(__file__).resolve() if start is None else Path(start).resolve()
    for parent in (base, *base.parents):
        if (parent / COVERAGE_FLOOR_DOCUMENT).is_file():
            return parent
    raise CensusError(
        "could not locate the repository root: no ancestor of "
        + str(base) + " holds " + COVERAGE_FLOOR_DOCUMENT
        + " -- the census re-derives its class list from that document at run "
        "time (CP-1) and cannot make a coverage claim without it"
    )


def sha256_of(path: Path) -> str:
    """The lowercase hex SHA-256 of a file, as the artifact records it.

    Used for both the truth-source digests (provenance for the reader) and the
    `fwdata_sha256_before`/`_after` pair that proves the census wrote nothing.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Parsing `object-inventory.md` TABLE 1 + TABLE 2 -- at RUN TIME (CP-1)
# ---------------------------------------------------------------------------


def _iter_table_rows(text: str, heading: str):
    """Yield the cell lists of one `## <heading> ...` markdown table.

    The inventory's tables are separated by `##` headings, so a heading switch
    ends the table. The header row and its `---` separator are skipped.
    """
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## " + heading)
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if cells[0] in ("Object (class)",) or set(cells[0]) <= {"-", ":"}:
            continue
        yield cells


def _classes_in_cell(cell: str) -> tuple:
    """The LCM class names one first-column cell names.

    The inventory writes a first column three ways, all of which appear:
    `PartOfSpeech`; `CmPossibility (\\`LexDbOA.SenseTypesOA\\`)` -- the class
    plus the owning field, which is NOT part of the class name; and
    `PhNCSegments / PhNCFeatures` -- two classes sharing one row. Prose cells
    (`Writing system`, `(no object created)`) name no class and yield nothing.
    """
    without_parens = re.sub(r"\([^)]*\)", " ", cell)
    found = []
    for part in without_parens.split("/"):
        name = part.strip().strip("`").strip()
        if name and _CLASS_NAME_RE.match(name) and name not in found:
            found.append(name)
    return tuple(found)


def parse_inventory_tables(
    text: str, tables: tuple = DERIVATION_TABLES,
) -> dict:
    """Parse `object-inventory.md` and return `{class_name: (table tokens,)}`.

    This is CP-1's derivation, run on EVERY census invocation. It is not
    checked against a stored digest, because a stored digest proves only that
    the document has not changed -- not that the floor still agrees with it.
    """
    seen: dict = {}
    for heading in tables:
        token = _INVENTORY_TABLE_TOKENS[heading]
        rows = list(_iter_table_rows(text, heading))
        if not rows:
            raise CoverageIncomplete(
                "object-inventory.md has no parseable " + heading
                + " -- the census derives its class list from "
                + ", ".join(tables) + " at run time (CP-1) and a truth source "
                "it cannot read is a coverage failure, not an empty result"
            )
        for cells in rows:
            for name in _classes_in_cell(cells[0]):
                tokens = seen.setdefault(name, [])
                if token not in tokens:
                    tokens.append(token)
    return {name: tuple(tokens) for name, tokens in seen.items()}


def load_coverage_floor(path: Path) -> dict:
    """035's `coverage-floor.json`, as a dict. Read, never forked."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("in_scope_classes", "excluded_not_measurable"):
        if key not in data:
            raise CoverageIncomplete(
                "coverage-floor.json is missing " + repr(key)
                + " -- the census cannot prove FR-012 coverage against a "
                "floor that does not declare its own scope"
            )
    return data


# ---------------------------------------------------------------------------
# The class list
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassListEntry:
    """One class's PLACE in the census, decided before anything is counted.

    Separate from `models.ClassCensusRow` on purpose. The row is the
    measurement; this is the provenance the measurement is reported under, and
    it answers three of the four REQUIRED `classRow` keys that are not
    functions of the row itself (`CLASS_CENSUS_ROW_ARTIFACT_FIELDS`'s
    docstring names them): `gate_scope`, `in_class_list_via` and
    `inventory_tables`. Carrying them here rather than passing them to the
    emitter keeps CP-3's advisory marking and CP-4's floor-vs-additions
    provenance in ONE place -- the loader that actually knows them -- instead
    of being re-decided per emission.
    """

    object_class: str                        # -> artifact `class`
    in_class_list_via: str                   # -> artifact `in_class_list_via`
    gate_scope: str                          # -> artifact `gate_scope`
    engine_can_create: bool                  # -> artifact `engine_can_create`
    inventory_tables: tuple = ()             # -> artifact `inventory_tables`
    not_evaluated_reason: Optional[str] = None   # -> `not_evaluated_reason`
    #: A1 (T018): the owning feature system for a class reachable from both,
    #: e.g. `FsFeatStrucType`. `None` for every ordinary class.
    owning_feature_system: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.object_class:
            raise CensusError("ClassListEntry.object_class must be non-empty")
        if self.in_class_list_via not in (
                "coverage_floor", "census_additions", "excluded_not_measurable"):
            raise CensusError(
                "ClassListEntry.in_class_list_via for "
                + repr(self.object_class) + " is "
                + repr(self.in_class_list_via)
                + ", outside the schema's in_class_list_via enum"
            )
        if self.gate_scope not in ("required", "advisory"):
            raise CensusError(
                "ClassListEntry.gate_scope for " + repr(self.object_class)
                + " is " + repr(self.gate_scope) + ", not 'required' or "
                "'advisory'"
            )
        if (self.not_evaluated_reason is not None
                and self.not_evaluated_reason not in NOT_EVALUATED_REASONS):
            raise CensusError(
                "ClassListEntry.not_evaluated_reason for "
                + repr(self.object_class) + " is "
                + repr(self.not_evaluated_reason) + ", not one of "
                + repr(tuple(sorted(NOT_EVALUATED_REASONS)))
            )

    @property
    def is_not_evaluated(self) -> bool:
        """True when the class is reported without being measured."""
        return self.not_evaluated_reason is not None

    @property
    def row_key(self) -> str:
        """The identity this entry's row is emitted under.

        Equal to `object_class` for every ordinary class. For an A1-split class
        it carries the owning feature system as well, because a single summed
        row would let a shortfall in one system be masked by a surplus in the
        other -- see `split_class_label` (T018).
        """
        if self.owning_feature_system is None:
            return self.object_class
        return split_class_label(self.object_class, self.owning_feature_system)


@dataclass(frozen=True)
class ClassList:
    """The full census roster plus the evidence that it is complete.

    `entries` is one entry per emitted row, in a stable order: the required
    classes (floor, then additions) alphabetically, then the
    `excluded_not_measurable` rows. `derivation_check` and `provenance` are
    emitted verbatim into `class_list_provenance`.
    """

    entries: tuple
    derivation_check: dict
    provenance: dict

    def __post_init__(self) -> None:
        seen = set()
        for entry in self.entries:
            if entry.row_key in seen:
                raise CoverageIncomplete(
                    "the class list carries two rows for " + repr(entry.row_key)
                    + " -- exactly one row per class (CP-2)",
                    (entry.object_class,),
                )
            seen.add(entry.row_key)

    # ---- derived views -------------------------------------------------

    @property
    def classes(self) -> tuple:
        """Every emitted row key, in emission order."""
        return tuple(e.row_key for e in self.entries)

    @property
    def required_classes(self) -> tuple:
        """The CP-1 class set: coverage floor union census additions."""
        return tuple(
            e.object_class for e in self.entries
            if e.in_class_list_via in ("coverage_floor", "census_additions")
        )

    @property
    def required_class_count(self) -> int:
        """-> artifact `required_class_count`.

        The ROW count, because invariant 1 is `len(classes) ==
        required_class_count` and a validator recomputes it. See the note on
        `REQUIRED_CLASS_COUNT` for why the two numbers differ by the
        `excluded_not_measurable` rows.
        """
        return len(self.entries)

    def entry_for(self, class_or_row_key: str) -> Optional[ClassListEntry]:
        """The entry for one class or row key, or None when absent -- which is
        itself a coverage defect (FR-012 requires a row per class)."""
        for entry in self.entries:
            if class_or_row_key in (entry.object_class, entry.row_key):
                return entry
        return None

    def entries_for(self, object_class: str) -> tuple:
        """Every entry for one class. More than one only for an A1 split."""
        return tuple(e for e in self.entries if e.object_class == object_class)


def _gate_scope_for(object_class: str, engine_can_create: bool) -> str:
    """CP-3: `gate_scope` is explicit per row, and advisory is not a judgement.

    Rows the engine can create are `required`; the classes no path creates are
    `advisory` and cannot by themselves fail the gate.
    """
    return "required" if engine_can_create else "advisory"


def derive_class_list(
    root: Optional[Path] = None,
    *,
    additions: tuple = CENSUS_ADDITIONS,
) -> ClassList:
    """Derive the census class list from the truth sources, and PROVE it.

    Four executable checks, each failing by class name:

    - **CP-1** the class set parsed out of `object-inventory.md` TABLE 1 +
      TABLE 2 must equal `in_scope_classes` union `excluded_not_measurable`.
      A class added to the inventory and not to the floor, or the reverse,
      fails the run and names the class.
    - **CP-2** exactly one row per class; a class with no instances anywhere is
      NOT_EVALUATED, never omitted (enforced by `ClassList.__post_init__` and
      by invariant 1 downstream).
    - **CP-3** `LexRefType` / `LexAppendix` / `PhBdryMarker` are advisory.
    - **CP-4** a class in both the floor and the additions ledger is
      `COVERAGE_INCOMPLETE`.

    Raises `CoverageIncomplete` (verdict `COVERAGE_INCOMPLETE`, exit 6) on any
    of them.
    """
    base = repo_root() if root is None else Path(root)
    inventory_path = base / INVENTORY_DOCUMENT
    floor_path = base / COVERAGE_FLOOR_DOCUMENT
    roster_path = base / NATURAL_KEY_ROSTER_DOCUMENT

    if not inventory_path.is_file():
        raise CoverageIncomplete(
            "the class-list truth source is missing: " + str(inventory_path)
            + " -- CP-1 re-derives the class set from it on every invocation"
        )

    derived = parse_inventory_tables(
        inventory_path.read_text(encoding="utf-8"))
    floor = load_coverage_floor(floor_path)

    in_scope = tuple(floor["in_scope_classes"])
    excluded = tuple(
        (e["class"], e.get("reason", "")) for e in floor["excluded_not_measurable"]
    )
    excluded_names = tuple(name for name, _ in excluded)
    addition_names = tuple(a["class"] for a in additions)

    # -- CP-4, checked BEFORE CP-1 so a double-listed class is reported as the
    # ledger error it is rather than as a derivation surplus.
    both = tuple(sorted(set(in_scope) & set(addition_names)))
    if both:
        raise CoverageIncomplete(
            "these classes are in BOTH coverage-floor.json in_scope_classes "
            "and the census additions ledger: " + ", ".join(both)
            + " -- an addition must be dropped in the same change that adds it "
            "to the floor, so the ledger cannot rot into a second truth source "
            "(CP-4)",
            both,
        )

    # -- CP-1, the derivation proof.
    expected = set(in_scope) | set(excluded_names)
    in_inventory_not_in_floor = tuple(sorted(set(derived) - expected))
    in_floor_not_in_inventory = tuple(sorted(expected - set(derived)))
    matched = not in_inventory_not_in_floor and not in_floor_not_in_inventory

    derivation_check = {
        "performed": True,
        "result": "match" if matched else "mismatch",
        "derived_class_count": len(derived),
        "in_inventory_not_in_floor": list(in_inventory_not_in_floor),
        "in_floor_not_in_inventory": list(in_floor_not_in_inventory),
    }

    if not matched:
        raise CoverageIncomplete(
            "CP-1 derivation mismatch between " + INVENTORY_DOCUMENT + " and "
            + COVERAGE_FLOOR_DOCUMENT + ": in the inventory and not the floor: "
            + (", ".join(in_inventory_not_in_floor) or "(none)")
            + "; in the floor and not the inventory: "
            + (", ".join(in_floor_not_in_inventory) or "(none)"),
            in_inventory_not_in_floor + in_floor_not_in_inventory,
        )

    entries = []
    for name in sorted(in_scope):
        engine_can_create = name not in NEVER_CREATED_CLASSES
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="coverage_floor",
            gate_scope=_gate_scope_for(name, engine_can_create),
            engine_can_create=engine_can_create,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(name),
        ))
    for addition in additions:
        name = addition["class"]
        # An addition is carried BECAUSE the engine has no path for it
        # (MoAffixProcess) or because nothing carries it (PhCode); it is still
        # gate-required, because that is the point of measuring it. Only the
        # three never-created classes are advisory (CP-3).
        engine_can_create = name not in NEVER_CREATED_CLASSES
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="census_additions",
            gate_scope=_gate_scope_for(name, engine_can_create),
            engine_can_create=engine_can_create,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(name),
        ))
    for name, _reason in excluded:
        # Abstract LCM bases with no factory. Reported, never measured, and
        # never omitted: an absent row is indistinguishable from a class the
        # census forgot.
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="excluded_not_measurable",
            gate_scope="advisory",
            engine_can_create=False,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(
                name, "ABSENT_BY_CONSTRUCTION"),
        ))

    required_count = sum(
        1 for e in entries
        if e.in_class_list_via in ("coverage_floor", "census_additions")
    )
    if required_count != REQUIRED_CLASS_COUNT:
        raise CoverageIncomplete(
            "the derived required class count is " + str(required_count)
            + ", not the " + str(REQUIRED_CLASS_COUNT) + " of "
            "fidelity-census.md 3.2 (" + str(len(in_scope)) + " floor + "
            + str(len(addition_names)) + " additions) -- a change in either "
            "truth source must be a deliberate edit to REQUIRED_CLASS_COUNT "
            "as well, so coverage cannot drift silently",
            tuple(sorted(set(in_scope) | set(addition_names))),
        )

    provenance = {
        "inventory_document": INVENTORY_DOCUMENT,
        "inventory_sha256": sha256_of(inventory_path),
        "coverage_floor_document": COVERAGE_FLOOR_DOCUMENT,
        "coverage_floor_sha256": sha256_of(floor_path),
        "census_additions": [dict(a) for a in additions],
        "excluded_not_measurable": [
            {"class": name, "reason": reason} for name, reason in excluded
        ],
        "in_scope_class_count": len(in_scope),
    }
    if roster_path.is_file():
        provenance["natural_key_roster_document"] = NATURAL_KEY_ROSTER_DOCUMENT
        provenance["natural_key_roster_sha256"] = sha256_of(roster_path)

    return ClassList(
        entries=tuple(entries),
        derivation_check=derivation_check,
        provenance=provenance,
    )


def class_list_provenance_artifact(class_list: ClassList) -> dict:
    """-> artifact `class_list_provenance`.

    `required_class_count` is the ROW count so invariant 1 (`len(classes) ==
    required_class_count`) holds by construction.
    """
    block = dict(class_list.provenance)
    block["derivation_check"] = dict(class_list.derivation_check)
    block["required_class_count"] = class_list.required_class_count
    return block


# ---------------------------------------------------------------------------
# T018 places the A1 seam here; declared now so `ClassListEntry.row_key` can
# reference it without a forward-declaration dance.
# ---------------------------------------------------------------------------


def split_class_label(object_class: str, owner: str) -> str:
    """PROVISIONAL (A1): the row label for a class split by owning collection.

    Replaced or kept by T018; see that task's seam for the two encodings under
    consideration.
    """
    return object_class + "(" + owner + ")"
