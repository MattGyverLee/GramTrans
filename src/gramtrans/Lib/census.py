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

# Dual-mode import, matching every other module under `Lib/`. This file used
# to import `.models` unconditionally, which made it importable ONLY as part of
# the `gramtrans.Lib` package. That was invisible for as long as nothing in the
# flat, `site.addsitedir("Lib")` load path reached it -- and it stopped being
# invisible the moment 038 T031 gave `preview.py` a module-level dependency on
# `census`, because the standalone FlexTools entry module loads `preview` flat.
# The failure mode was an `ImportError: attempted relative import with no known
# parent package` raised from this line, surfacing 10 files away in the feature
# 034 standalone-contract tests.
if __package__:
    from .models import (
        CENSUS_FEATURE_SYSTEM_OWNERS,
        CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES,
        CENSUS_NOT_EVALUATED_REASONS,
        CENSUS_REASON_TOKENS,
        CENSUS_REASONS_NOT_REQUIRING_REPORT_REF,
        CENSUS_ROW_VERDICT_CLASSES,
        CENSUS_SCHEMA_VERSION as _MODELS_CENSUS_SCHEMA_VERSION,
    )
else:  # loaded via site.addsitedir("Lib")
    from models import (  # type: ignore[no-redef]
        CENSUS_FEATURE_SYSTEM_OWNERS,
        CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES,
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

#: FR-013's closed 17-token reason vocabulary, in schema enum order.
REASON_TOKENS: tuple = CENSUS_REASON_TOKENS

#: The four tokens exempt from `accountedLine.report_ref` (R-1).
REASONS_NOT_REQUIRING_REPORT_REF: frozenset = (
    CENSUS_REASONS_NOT_REQUIRING_REPORT_REF
)

#: The three reasons that make a row NOT_EVALUATED rather than measured.
NOT_EVALUATED_REASONS: frozenset = CENSUS_NOT_EVALUATED_REASONS

#: `$defs.classRow.verdict_class.enum`.
ROW_VERDICT_CLASSES: tuple = CENSUS_ROW_VERDICT_CLASSES

#: T109 -- `class -> (owner, reason)` for every class the spec Assumptions hand
#: to another feature. Read through `governed_by_other_feature` below, which is
#: THE ONE LOOKUP; the disjointness lock that makes the roster safe lives at
#: module scope beside the phase class sets, because it needs them.
GOVERNED_BY_OTHER_FEATURE_CLASSES: dict = (
    CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES
)


def governed_by_other_feature(object_class: str):
    """`(owner, reason)` if this class is another feature's, else None.

    THE ONE LOOKUP (T079's `report_only_residue_entry` precedent), so there is
    no second place a class could acquire a `GOVERNED_BY_OTHER_FEATURE` line.
    Reads the module global at call time on purpose: that is what lets
    `tests/.../test_038_t109_governed_by_other_feature.py` empty the roster and
    prove the emitter is inert without it.
    """
    return GOVERNED_BY_OTHER_FEATURE_CLASSES.get(object_class)


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

#: T098. Feature 038's own PROPOSAL for the six classes it asked 035 to admit.
#: It is not a roster and never becomes one: it stays populated after landing
#: (it is the proposal record), which is why admission is read from
#: `NATURAL_KEY_ROSTER_DOCUMENT` and provenance is CHECKED against both.
NATURAL_KEY_ROSTER_EXTENSION_DOCUMENT = (
    "specs/038-transfer-fidelity-gaps/contracts/"
    "natural-key-roster-extension.json"
)

#: The two documents a `NaturalKeyDefinition.roster_source` may name, and the
#: whole vocabulary. `ROSTER_SOURCE_035` means the class is ADMITTED and its
#: duplicates can fail the gate; `ROSTER_SOURCE_038_PROPOSAL` means 038 has
#: proposed it and 035 has not taken it yet, so its duplicates are advisory.
ROSTER_SOURCE_035 = "natural_key_identity_roster_035"
ROSTER_SOURCE_038_PROPOSAL = "roster_extension_038"
ROSTER_SOURCES: tuple = (ROSTER_SOURCE_035, ROSTER_SOURCE_038_PROPOSAL)

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
        other. INTERNAL ONLY: the two halves must be distinguishable in memory
        (`ClassList` rejects two rows under one key), but the EMITTED `class` is
        the plain class name on both, with the owner in the row property
        `owning_feature_system` -- see `encode_split_owner`.
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
        """The CP-1 class set: coverage floor union census additions.

        DISTINCT class names, so an A1 split (one class, two rows -- see
        `split_feature_system_entries`) leaves this count untouched, exactly as
        Amendment A1 requires: "it adds no class to the required list and does
        not alter the 72-class count". The row count is `required_class_count`.
        """
        return tuple(dict.fromkeys(
            e.object_class for e in self.entries
            if e.in_class_list_via in ("coverage_floor", "census_additions")
        ))

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


def gate_scope_for(object_class: str, engine_can_create: bool) -> str:
    """CP-3: `gate_scope` is explicit per row, and advisory is not a judgement.

    Rows the engine can create are `required`; the classes no path creates are
    `advisory` and cannot by themselves fail the gate.

    PUBLIC ON PURPOSE. `Lib/report.py` needs this when it emits a `classRow`
    from an in-memory `FidelityCensus`, and the only alternative there is a
    local `"required" if engine_can_create else "advisory"` -- a second copy of
    CP-3's rule, free to drift. One rule, one function, called from both
    surfaces.
    """
    return "required" if engine_can_create else "advisory"


#: Compatibility alias for the pre-promotion private spelling. Retained rather
#: than renamed so an in-flight caller of `census._gate_scope_for` keeps
#: working; both names are the same function object, so they cannot disagree.
_gate_scope_for = gate_scope_for


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
            gate_scope=gate_scope_for(name, engine_can_create),
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
            gate_scope=gate_scope_for(name, engine_can_create),
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
    """The label for a class split by owning collection -- FALLBACK ONLY.

    Not part of the emitted artifact while `A1_OWNER_ENCODING` is
    `"row_property"` (the settled choice, backed by the `classRow` property
    `owning_feature_system`). It survives as the INTERNAL
    `ClassListEntry.row_key`, which needs the two halves of a split to be
    distinguishable in memory even though the emitted `class` is the plain class
    name on both. Kept so the encoding decision is reversible at one constant;
    see the note above `A1_OWNER_ENCODING`.
    """
    return object_class + "(" + owner + ")"


# ===========================================================================
# T017 -- the READ-ONLY counting pass
#
# READ-ONLY, WITHOUT EXCEPTION (fidelity-census.md section 2). Both projects
# are opened `writeEnabled=False`, the `.fwdata` digest is taken before and
# after, and a digest that MOVED is `CENSUS_ERROR` -- not a warning, not a
# note. `Ejagham Mini`, `Esperanto` and `Mbugwe LizzieHC practice` are
# read-only test projects, and the digest pair is the evidence that they stayed
# that way. `$defs.projectRef.opened_read_only` is `const: true`, so a census
# that opened a write handle cannot produce a valid artifact at all.
#
# AN UNRESOLVED ACCESSOR IS A REPORTED OUTCOME, NEVER A SKIP.
# `tests/integration/harness/full_run.py:230` is the precedent to avoid: its
# counting loop does `except Exception: continue`, so a renamed accessor turns
# into a silently absent number and the harness reports success over it. Here a
# class whose repository cannot be resolved lands in `unresolved_accessors`,
# becomes an `errors[]` entry with the class named, and drives the run to
# CENSUS_ERROR. The census may fail to measure a class; it may not fail
# QUIETLY.
# ===========================================================================

#: Where FLEx projects live when no root is supplied. The same literal
#: `Lib/api.py` defaults to, so the census and the transfer cannot disagree
#: about where a project is.
DEFAULT_PROJECTS_ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"

#: `<languageproject version="7000072">` on the second line of every `.fwdata`.
_DATA_MODEL_VERSION_RE = re.compile(rb'<languageproject\s+version="(\d+)"')

#: Process-wide latch for `FLExInitialize()`; see `_ensure_flex_initialized`.
_FLEX_INITIALIZED = False


def _ensure_flex_initialized() -> None:
    """Make FieldWorks AND the SLDR ready for an `OpenProject`.

    A non-FlexTools-host process MUST initialise the FieldWorks libraries
    before any `OpenProject`; skipping it surfaces as
    `RegistryHelper.get_CompanyKey()` throwing `ArgumentNullException` on the
    first open.

    Delegates to `Lib/flexinit.py`, which additionally re-verifies the SLDR on
    EVERY call. This used to be a bare once-per-process boolean latch, and that
    was actively destructive: `flexicon.FLExCleanup()` (called by any
    `HostSession.release()` in the same process) runs `Sldr.Cleanup()`, after
    which the latch suppressed re-initialisation and the next open -- even a
    READ-ONLY one -- renamed every `WritingSystemStore/*.ldml` to `*.ldml.bad`,
    producing the user-visible "Can't add EN writing system". A census opens
    both projects read-only, so it was one of the paths doing the damage. See
    `Lib/flexinit.py` for the measurement.

    The import is function-level on purpose -- see this module's docstring on
    why nothing here may touch FieldWorks at import time. `flexinit` itself is
    FieldWorks-free at import time, but keeping the call site lazy preserves
    that guarantee locally rather than by reference.
    """
    global _FLEX_INITIALIZED
    if __package__:
        from .flexinit import ensure_flex_initialized  # noqa: PLC0415
    else:
        from flexinit import ensure_flex_initialized  # type: ignore # noqa: PLC0415

    ensure_flex_initialized()
    _FLEX_INITIALIZED = True


def fwdata_path_for(
    project_name: str,
    projects_root: Optional[str] = None,
    handle=None,
) -> Path:
    """The `.fwdata` file whose digest proves the census wrote nothing.

    Prefers the OPEN handle's own `ProjectId.Path` (the accessor
    `Lib/config_views.py` and `Lib/api.py` already use), because that is the
    file LCM actually has open rather than a guess from the project name.
    Falls back to `<root>/<name>/<name>.fwdata`, research R5's definition of
    what a FLEx project looks like on disk.
    """
    if handle is not None:
        try:
            candidate = str(handle.project.ProjectId.Path)
        except Exception:  # noqa: BLE001 -- fake handles / API drift
            candidate = ""
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    root = projects_root or DEFAULT_PROJECTS_ROOT
    return Path(root) / project_name / (project_name + ".fwdata")


def read_data_model_version(fwdata: Path) -> Optional[int]:
    """The `.fwdata` header's data-model version, or None when unreadable.

    Read from the file rather than from the cache because it is needed BEFORE
    and AFTER the open, and because baseline staleness is judged against it
    (fidelity-census.md 5.3): a destination whose `data_model_version` exceeds
    the baseline's makes the baseline stale.
    """
    try:
        with open(fwdata, "rb") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    found = _DATA_MODEL_VERSION_RE.search(head)
    return int(found.group(1)) if found else None


# ---------------------------------------------------------------------------
# Per-class counts
#
# T023b -- LCM REPOSITORIES ARE POLYMORPHIC. DO NOT "SIMPLIFY" THIS BACK.
#
# `I<Class>Repository.Count` / `.AllInstances()` (which is what flexicon's
# `ObjectCountFor` / `ObjectsIn` wrap) return the whole INHERITANCE SUBTREE, not
# the objects whose own class is `<Class>`. Measured against a blank FieldWorks
# starter project (the `Ngoreme Target 2026-08-19 0831` backup, digest
# bc91a75b...), read straight out of `.fwdata` for ground truth:
#
#     class            repository reports    own <rt> rows
#     CmPossibility               3014                 302
#     LexEntryType                  14                  11
#
# 3014 = 302 own + 1792 CmSemanticDomain + 859 CmAnthroItem + 19 MoMorphType
# + 14 LexEntryType(subtree) + 15 CmAnnotationDefn + 7 LexRefType
# + 5 PartOfSpeech + 1 CmPerson -- the entire subtree, to the object.
# 14 = 11 own + 3 LexEntryInflType.
#
# That is fatal for a census whose rows are supposed to PARTITION the project:
#
#   - the 74 class rows stop being disjoint (one `PartOfSpeech` object is
#     counted in the `PartOfSpeech` row AND in the `CmPossibility` row),
#   - the emitted object total double-counts,
#   - a per-class `difference` is ambiguous for any class with subclasses, and
#   - the match-basis invariant
#     `identity + natural_key + created_new + unmatched_reported == source_count`
#     runs against a polymorphic `source_count`, so T019's "no cross-class
#     netting, ever" is undermined by the COUNTS rather than by the arithmetic.
#
# So every number this section publishes is the EXACT class. The two words are
# used consistently and are not interchangeable:
#
#   EXACT       objects whose own class is this class. `ClassCounts.counts`,
#               `count_for()`, every row, every difference, every total.
#   CUMULATIVE  the polymorphic subtree, i.e. what LCM hands back raw.
#               `ClassCounts.cumulative_counts` / `cumulative_count_for()`,
#               retained ONLY so the raw reading stays inspectable.
#
# Exact is derived by SUBTRACTING the direct subclasses' cumulative counts from
# the class's own cumulative count, which keeps T017's one-O(1)-read-per-class
# contract (a `Count` read per class plus one per direct subclass -- 0.26s for
# all 74 rows on the starter, versus 0.37s for the enumerate-and-filter walk).
# The subclass names come from LCM's own metadata cache, never from a table
# hand-maintained here. When the metadata cache cannot be reached at all the
# code falls back to enumerating and filtering on `ClassName`, which is O(n) in
# the subtree; that fallback is RECORDED per class in `ClassCounts.count_basis`
# rather than taken silently, because it is a real change in cost.
# ---------------------------------------------------------------------------


#: `count_basis` value: exact = own cumulative count MINUS the cumulative counts
#: of the direct subclasses LCM's metadata cache names. One O(1) `Count` read per
#: class plus one per direct subclass, so T017's contract is intact.
COUNT_BASIS_SUBTRACTION = "repository_subtraction"

#: `count_basis` value: exact = enumerate the subtree ONCE and keep the objects
#: whose `ClassName` is the class. Correct but O(n) in the subtree; only used
#: when the metadata cache cannot be reached, and always recorded when it is.
COUNT_BASIS_ENUMERATION = "enumerated_class_filter"


@dataclass(frozen=True)
class ClassCounts:
    """One project's per-class instance counts, plus what could NOT be counted.

    `counts` is the EXACT class in every case -- objects whose own class is the
    key, never the polymorphic LCM subtree (T023b; see this section's header).
    That is what makes the 74 rows disjoint and a per-class `difference`
    meaningful. The raw subtree reading is kept beside it in
    `cumulative_counts`, under a name that cannot be mistaken for the other.

    `counts` holds only classes that were actually measured. A class the census
    could not measure is in `unmeasurable` and its reason is in
    `unresolved_accessors` -- it is never silently absent from `counts` and
    never defaulted to zero, because zero is a positive claim ("this project
    holds none of these") and an unresolved accessor supports no claim at all.
    """

    project_name: str
    counts: dict
    unmeasurable: tuple = ()
    unresolved_accessors: Optional[dict] = None
    object_count_total: Optional[int] = None
    #: `{class: cumulative count}` -- the POLYMORPHIC subtree total LCM hands
    #: back raw. Diagnostic only: nothing in the accounting reads it, because
    #: subtracting one project's subtree from another's is exactly the
    #: cross-class netting T019 forbids. It equals `counts[class]` for every
    #: class with no subclasses.
    cumulative_counts: Optional[dict] = None
    #: `{class: basis}` -- how the exact count was obtained, one of
    #: `COUNT_BASIS_SUBTRACTION` (O(1) reads) or `COUNT_BASIS_ENUMERATION`
    #: (O(n) walk, the metadata-cache fallback). Emitted nowhere; it exists so
    #: a run that quietly got slow can SAY so instead of being guessed at.
    count_basis: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.unresolved_accessors is None:
            object.__setattr__(self, "unresolved_accessors", {})
        if self.cumulative_counts is None:
            object.__setattr__(self, "cumulative_counts", {})
        if self.count_basis is None:
            object.__setattr__(self, "count_basis", {})
        missing = tuple(
            name for name in self.unmeasurable
            if name not in self.unresolved_accessors
        )
        if missing:
            raise CensusError(
                "these classes are unmeasurable with no recorded reason: "
                + ", ".join(sorted(missing))
                + " -- an unmeasurable class must say WHY, or it is "
                "indistinguishable from a class the census forgot",
                missing,
            )
        both = tuple(sorted(set(self.counts) & set(self.unmeasurable)))
        if both:
            raise CensusError(
                "these classes are both counted and unmeasurable: "
                + ", ".join(both),
                both,
            )

    def count_for(self, object_class: str) -> Optional[int]:
        """The EXACT count for one class, or None when it could not be measured.

        Exact means "own class is this class", not the polymorphic subtree --
        see the section header. None is `unmeasurable`, NOT zero. The caller
        must report it rather than subtract it.
        """
        return self.counts.get(object_class)

    def cumulative_count_for(self, object_class: str) -> Optional[int]:
        """The POLYMORPHIC subtree count for one class -- diagnostics only.

        Never feed this to a difference or a total: subtree counts overlap, so
        summing or subtracting them double-counts. `count_for` is the number
        every row is built from.
        """
        return (self.cumulative_counts or {}).get(object_class)

    def basis_for(self, object_class: str) -> Optional[str]:
        """How this class's exact count was obtained -- see `count_basis`."""
        return (self.count_basis or {}).get(object_class)

    @property
    def enumerated_classes(self) -> tuple:
        """Classes that needed the O(n) fallback walk, sorted.

        Empty on a healthy run. Non-empty means the metadata cache was
        unreachable and the pass paid a walk per class; the caller should say so
        rather than let the cost pass unremarked.
        """
        return tuple(sorted(
            name for name, basis in (self.count_basis or {}).items()
            if basis == COUNT_BASIS_ENUMERATION
        ))

    @property
    def is_complete(self) -> bool:
        """True when every requested class yielded a number."""
        return not self.unmeasurable


def _repository_interface(object_class: str):
    """The `SIL.LCModel.I<Class>Repository` interface, or None when absent.

    LCM generates one repository per class, so this resolves for every class in
    the roster; returning None rather than raising lets the caller record an
    `unresolved_accessors` entry naming the class instead of aborting the whole
    pass on one drifted name.
    """
    import SIL.LCModel as lcm  # noqa: PLC0415 -- see module docstring

    return getattr(lcm, "I" + object_class + "Repository", None)


def metadata_cache(handle):
    """LCM's own metadata cache, or None when it cannot be reached.

    This is where the class HIERARCHY comes from. There is deliberately no
    hand-maintained subclass table in this module: LCM adds and moves classes
    between data-model versions, and a stale local table would silently put the
    subtree back into an "exact" count -- the very defect T023b removed, but
    harder to notice the second time.

    `LcmCache.MetaDataCacheAccessor` is typed `IFwMetaDataCache`, whose
    interface does not carry `GetDirectSubclasses`; the managed subinterface
    `SIL.LCModel.Infrastructure.IFwMetaDataCacheManaged` does. Measured on this
    machine (liblcm 11.0.0) the raw proxy happens to answer it too, but that is
    pythonnet resolving against whatever the concrete object exposes and is
    exactly the kind of coincidence CLAUDE.md's `FeaturesOA` note records going
    the other way -- so the cast is attempted FIRST, and the raw accessor is
    used only when it can be shown to answer.
    """
    cache = getattr(handle, "project", None)
    accessor = getattr(cache, "MetaDataCacheAccessor", None)
    if accessor is None:
        return None
    candidates = []
    try:
        from SIL.LCModel.Infrastructure import (  # noqa: PLC0415
            IFwMetaDataCacheManaged,
        )

        candidates.append(IFwMetaDataCacheManaged(accessor))
    except Exception:  # noqa: BLE001 -- no managed cast available; try raw
        pass
    candidates.append(accessor)
    for candidate in candidates:
        if candidate is None:
            continue
        if all(hasattr(candidate, name) for name in
               ("GetClassId", "GetClassName", "GetDirectSubclasses")):
            return candidate
    return None


def direct_subclass_names(mdc, object_class: str) -> Optional[tuple]:
    """The DIRECT subclasses of one class, or None when metadata cannot say.

    Direct, not all: `exact = cumulative(C) - sum(cumulative(direct subclass))`
    already telescopes over the whole subtree, because each direct subclass's
    cumulative count contains its own descendants. Subtracting ALL subclasses
    would double-subtract every grandchild (`LexEntryInflType` sits under
    `LexEntryType` sits under `CmPossibility`).
    """
    try:
        clid = int(mdc.GetClassId(object_class))
    except Exception:  # noqa: BLE001 -- unknown class name, or drifted API
        return None
    if not clid:
        return None
    try:
        return tuple(
            str(mdc.GetClassName(sub))
            for sub in mdc.GetDirectSubclasses(clid)
        )
    except Exception:  # noqa: BLE001
        return None


def cumulative_count(handle, object_class: str) -> tuple:
    """`(count, reason)` for the POLYMORPHIC subtree total of one class.

    Exactly one `repository.Count` read. Success is `(int, None)`; failure is
    `(None, reason)`, worded ready for `unresolved_accessors` -- a missing
    repository interface, a service locator that returns nothing, a raising
    accessor, and a count that is not an integer are four distinct reasons and
    stay distinguishable.

    THIS NUMBER IS NOT A ROW. It counts the class and every subclass; see the
    section header. `count_classes` turns it into an exact count.
    """
    iface = _repository_interface(object_class)
    if iface is None:
        return None, (
            "SIL.LCModel exposes no I" + object_class + "Repository -- the "
            "class was renamed, removed, or is not a first-class LCM class"
        )
    try:
        value = handle.ObjectCountFor(iface)
    except Exception as exc:  # noqa: BLE001 -- LCM raises many types
        return None, (
            "I" + object_class + "Repository resolved but counting raised "
            + type(exc).__name__ + ": " + str(exc)
        )
    if value is None:
        return None, (
            "the service locator returned no I" + object_class + "Repository"
        )
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, (
            "I" + object_class + "Repository.Count is not an integer: "
            + repr(value)
        )


def count_classes(handle, class_names, *, project_name: str = "") -> ClassCounts:
    """Count each class ONCE against an open, read-only project handle.

    Every returned count is the EXACT class -- objects whose own class is that
    class. LCM's repositories are polymorphic, so the raw reading is not; the
    section header above measures the damage that did, and must be read before
    touching this function.

    THE EFFICIENCY CONTRACT (T017) IS INTACT. Exact counting is arithmetic over
    O(1) `repository.Count` reads, not a walk: one read for the class plus one
    per DIRECT subclass named by LCM's metadata cache, with every read memoised
    across the pass so a class that is several classes' subclass is still read
    once. Measured over all 74 rows of the blank starter: 0.26s, against 0.37s
    for the enumerate-and-filter alternative. No per-object re-query anywhere.

    Only when `metadata_cache` cannot be reached at all does a class fall back
    to enumerating its subtree once and filtering on `ClassName` -- correct, but
    O(n). That is recorded per class in `count_basis` (and summarised by
    `enumerated_classes`) rather than absorbed silently, because it changes the
    cost of the pass.

    Every failure mode is recorded and named: the four `cumulative_count`
    reasons, plus a subclass whose own cumulative count could not be read (the
    subtraction would be wrong, so the class is unmeasurable rather than
    approximate) and a subtraction that comes out negative (LCM contradicted
    itself, and a negative "count" is not a measurement).
    """
    requested = tuple(dict.fromkeys(class_names))
    cumulative: dict = {}
    reasons: dict = {}

    def cumulative_for(name: str):
        """Memoised `cumulative_count` -- one repository read per class, ever."""
        if name not in cumulative:
            value, reason = cumulative_count(handle, name)
            cumulative[name] = value
            if reason is not None:
                reasons[name] = reason
        return cumulative[name]

    mdc = metadata_cache(handle)
    counts: dict = {}
    basis: dict = {}
    unresolved: dict = {}

    for name in requested:
        total = cumulative_for(name)
        if total is None:
            unresolved[name] = reasons[name]
            continue

        subclasses = None if mdc is None else direct_subclass_names(mdc, name)
        if subclasses is None:
            # No hierarchy available: enumerate the subtree ONCE and keep the
            # objects whose own class matches. Correct, and flagged as costly.
            try:
                counts[name] = len(objects_in_class(handle, name))
            except CensusError as exc:
                unresolved[name] = (
                    "LCM's metadata cache could not name the subclasses of "
                    + name + ", and the enumerate-and-filter fallback also "
                    "failed: " + str(exc) + " -- an exact count cannot be "
                    "proved either way, and the polymorphic subtree total ("
                    + str(total) + ") is not a substitute for it"
                )
                continue
            basis[name] = COUNT_BASIS_ENUMERATION
            continue

        own = total
        blocked = None
        for subclass in subclasses:
            sub_total = cumulative_for(subclass)
            if sub_total is None:
                blocked = subclass
                break
            own -= sub_total
        if blocked is not None:
            unresolved[name] = (
                "the exact count for " + name + " needs the subclass count "
                "for " + blocked + ", which could not be read ("
                + reasons[blocked] + ") -- LCM's I" + name + "Repository "
                "reports " + str(total) + " for the whole subtree, and "
                "publishing that as " + name + "'s own count is the "
                "double-counting T023b removed"
            )
            continue
        if own < 0:
            unresolved[name] = (
                "LCM reports " + str(total) + " objects in the " + name
                + " subtree but " + str(total - own) + " in its direct "
                "subclasses (" + ", ".join(subclasses) + "), leaving "
                + str(own) + " for " + name + " itself -- a negative count is "
                "not a measurement"
            )
            continue
        counts[name] = own
        basis[name] = COUNT_BASIS_SUBTRACTION

    total_objects: Optional[int] = None
    try:
        import SIL.LCModel as lcm  # noqa: PLC0415

        repo = handle.ObjectRepository(lcm.ICmObjectRepository)
        total_objects = int(repo.Count) if repo is not None else None
    except Exception:  # noqa: BLE001 -- advisory figure only
        total_objects = None

    return ClassCounts(
        project_name=project_name or str(getattr(handle, "ProjectName", "")),
        counts=counts,
        unmeasurable=tuple(sorted(unresolved)),
        unresolved_accessors=unresolved,
        object_count_total=total_objects,
        cumulative_counts={
            name: value for name, value in cumulative.items()
            if value is not None
        },
        count_basis=basis,
    )


def _exact_class_name(obj) -> Optional[str]:
    """`obj.ClassName`, or None when the object will not say what it is.

    `ClassName` is declared on `ICmObject`, so it is visible on every proxy LCM
    hands back regardless of which repository interface it came through, and it
    reports the RUNTIME class -- a `PartOfSpeech` reached through
    `ICmPossibilityRepository` still answers `"PartOfSpeech"`. That is what
    makes it a usable exact-class discriminator.
    """
    name = getattr(obj, "ClassName", None)
    return None if name is None else str(name)


def objects_in_class(handle, object_class: str) -> list:
    """Every instance of EXACTLY `object_class`, enumerated ONCE.

    Two callers: T018's duplicate grouping (which needs the objects themselves,
    not just their number) and `count_classes`'s metadata-cache fallback.

    The `ClassName` filter is not tidying. `handle.ObjectsIn` is
    `AllInstances()`, which yields the whole inheritance subtree, so an
    unfiltered `CmPossibility` enumeration hands duplicate grouping 3014 objects
    of ten different classes on a blank starter that owns 302 -- and a
    natural-key collision between a `PartOfSpeech` and a `CmSemanticDomain`
    would be reported as a duplicate `CmPossibility`. Each object belongs to
    exactly one row, so each row enumerates exactly its own objects.

    Raises `CensusError` rather than yielding nothing when the class cannot be
    enumerated, so a duplicate count of 0 always means "measured, and none" and
    never "could not look" -- including when an object declines to name its own
    class, because silently keeping an object of unknown class is how the
    subtree gets back in.
    """
    iface = _repository_interface(object_class)
    if iface is None:
        raise CensusError(
            "cannot enumerate " + repr(object_class)
            + ": SIL.LCModel exposes no I" + object_class + "Repository",
            (object_class,),
        )
    try:
        subtree = list(handle.ObjectsIn(iface))
    except Exception as exc:  # noqa: BLE001
        raise CensusError(
            "cannot enumerate " + repr(object_class) + ": "
            + type(exc).__name__ + ": " + str(exc),
            (object_class,),
        ) from exc

    exact = []
    for obj in subtree:
        name = _exact_class_name(obj)
        if name is None:
            raise CensusError(
                "cannot enumerate " + repr(object_class) + " exactly: an "
                "object in the subtree has no ClassName, so it cannot be "
                "assigned to one class row -- and I" + object_class
                + "Repository.AllInstances() returns the whole subtree, so "
                "keeping it anyway would count another class's object here",
                (object_class,),
            )
        if name == object_class:
            exact.append(obj)
    return exact


# ---------------------------------------------------------------------------
# One project's reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectCensusReading:
    """-> artifact `projects.source` / `projects.destination`.

    `opened_read_only` is not stored: it is emitted as the literal `True` the
    schema pins as `const`, and it is true because `read_project` is the only
    way to build one of these and it passes `writeEnabled=False`. A caller who
    counted through a write handle has no way to express that here, which is
    the intended shape.
    """

    name: str
    path: str
    counted_at: str
    fwdata_sha256_before: str
    fwdata_sha256_after: str
    counts: ClassCounts
    data_model_version: Optional[int] = None
    declared_freshly_created: Optional[bool] = None
    #: `{row_key: count}` for the A1-split rows -- see `split_counts`. Empty
    #: unless `read_project` was given the class list.
    split_counts: Optional[dict] = None

    @property
    def digest_unchanged(self) -> bool:
        """Invariant 7's per-project half: the census wrote nothing."""
        return self.fwdata_sha256_before == self.fwdata_sha256_after

    def artifact(self) -> dict:
        """The `$defs.projectRef` block."""
        block = {
            "name": self.name,
            "path": self.path,
            "opened_read_only": True,
            "counted_at": self.counted_at,
            "fwdata_sha256_before": self.fwdata_sha256_before,
            "fwdata_sha256_after": self.fwdata_sha256_after,
        }
        if self.data_model_version is not None:
            block["data_model_version"] = self.data_model_version
        if self.declared_freshly_created is not None:
            block["declared_freshly_created"] = self.declared_freshly_created
        if self.counts.object_count_total is not None:
            block["object_count_total"] = self.counts.object_count_total
        return block


def _now_iso() -> str:
    """`counted_at` / `generated_at`, second resolution, ISO-8601."""
    import datetime  # noqa: PLC0415 -- keeps the import surface uniform

    return datetime.datetime.now().replace(microsecond=0).isoformat()


def read_project(
    project_name: str,
    class_names,
    *,
    projects_root: Optional[str] = None,
    declared_freshly_created: Optional[bool] = None,
    class_list: Optional[ClassList] = None,
    open_project=None,
) -> ProjectCensusReading:
    """Open one project READ-ONLY, count every class once, and prove no write.

    The digest is taken before the open and again after the CLOSE, because a
    write LCM only flushes on `CloseProject()` would not show up in a digest
    taken while the handle is still open. A digest that moved raises
    `CensusError` (verdict `CENSUS_ERROR`, exit 7): the census's whole claim to
    be a safe instrument rests on that comparison, so it is the feature, not a
    formality.

    Pass `class_list` to also collect the A1 per-owner counts (`split_counts`)
    IN THIS SAME OPEN. They deliberately are not a second `read_project` call:
    one open means one digest window, and a second open of the same project to
    finish counting would widen the very window this function exists to close.

    `open_project` is an injection seam -- it must accept `(project_name)` and
    return a handle whose `ObjectCountFor` works. The default opens a real
    flexicon handle with `writeEnabled=False`.
    """
    fwdata = fwdata_path_for(project_name, projects_root)
    if not fwdata.is_file():
        raise CensusError(
            "no .fwdata for project " + repr(project_name) + " at "
            + str(fwdata) + " -- the census cannot prove it wrote nothing to a "
            "file it cannot digest"
        )
    before = sha256_of(fwdata)
    model_version = read_data_model_version(fwdata)
    counted_at = _now_iso()
    resolved = fwdata

    handle = None
    try:
        if open_project is not None:
            handle = open_project(project_name)
        else:
            from flexicon import FLExProject  # noqa: PLC0415

            _ensure_flex_initialized()
            handle = FLExProject()
            handle.OpenProject(projectName=project_name, writeEnabled=False)
        resolved = fwdata_path_for(project_name, projects_root, handle)
        counts = count_classes(handle, class_names, project_name=project_name)
        per_owner = (
            split_counts(handle, class_list) if class_list is not None else None
        )
    except CensusFailure:
        raise
    except Exception as exc:  # noqa: BLE001 -- LCM raises many types
        raise CensusError(
            "could not open " + repr(project_name) + " read-only for counting: "
            + type(exc).__name__ + ": " + str(exc)
        ) from exc
    finally:
        if handle is not None:
            try:
                handle.CloseProject()
            except Exception:  # noqa: BLE001 -- nothing was written to lose
                pass

    after = sha256_of(fwdata)
    if before != after:
        raise CensusError(
            "the .fwdata digest for " + repr(project_name) + " CHANGED under "
            "the census (" + before[:12] + "... -> " + after[:12] + "...) at "
            + str(fwdata) + " -- the census is read-only without exception "
            "(fidelity-census.md section 2), so a moved digest invalidates the "
            "whole run rather than one row"
        )

    return ProjectCensusReading(
        name=project_name,
        path=str(Path(resolved).parent),
        counted_at=counted_at,
        fwdata_sha256_before=before,
        fwdata_sha256_after=after,
        counts=counts,
        data_model_version=model_version,
        declared_freshly_created=declared_freshly_created,
        split_counts=per_owner,
    )


def count_for_entry(reading: ProjectCensusReading, entry: ClassListEntry):
    """The count for ONE class-list entry, or None when unmeasured.

    Prefers the A1 per-owner count for a split entry and returns None rather
    than the summed class total when the reading has none -- because handing a
    split row the class total is exactly the ambiguity A1 forbids, and a
    conspicuous None is the honest answer for a caller who never asked for the
    per-owner pass.
    """
    if entry.owning_feature_system is not None:
        per_owner = reading.split_counts or {}
        return per_owner.get(entry.row_key)
    return reading.counts.count_for(entry.object_class)


def projects_artifact(
    source: ProjectCensusReading, destination: ProjectCensusReading,
) -> dict:
    """-> artifact `projects`. Both readings, both digest pairs."""
    return {
        "source": source.artifact(),
        "destination": destination.artifact(),
    }


def unmeasurable_errors(*readings) -> tuple:
    """-> artifact `errors[]` entries, one per unresolved accessor.

    EMITTED, not logged. The `errors` array is what carries an unresolved
    accessor to its reader, and `recompute_verdict` treats a non-empty `errors`
    array as CENSUS_ERROR, so the failure cannot be read as a pass.
    """
    out = []
    for reading in readings:
        for name in reading.counts.unmeasurable:
            out.append({
                "code": "UNHANDLED_EXCEPTION",
                "message": (
                    "class " + name + " could not be counted in project "
                    + reading.name + "; the census makes no claim about it"
                ),
                "class": name,
                "evidence": reading.counts.unresolved_accessors[name],
            })
    return tuple(out)


# ===========================================================================
# T018 -- duplicate natural-key grouping, and Amendment A1's FsFeatStrucType
#        split by owning feature system
#
# WHY DUPLICATES ARE NOT OPTIONAL (fidelity-census.md section 6). A class row
# passes only when BOTH `difference == 0` (or every unit accounted) AND
# `duplicates.extra_objects == 0` (or each group accounted). The measured
# phoneme row is the proof: source 41, destination 64, starter 23, so
# 64 - 23 = 41 and `difference` is 0 -- on a run that had matched NONE of the
# 23 starter phonemes and created 41 beside them, with 21 duplicate names. The
# FIXED run gives the same 0. Baseline arithmetic cannot tell those two apart;
# grouping by natural key can, and is what makes this a gate for SC-002 rather
# than only for SC-005.
#
# COMPARISON STRICTNESS. Exact, case-sensitive, NO Unicode normalisation, NO
# case folding, NO whitespace trimming -- `Nasals`, `nasals` and
# `Nasal Consonants` were measured as three distinct natural classes. An object
# with no name in the scoped writing system has NO KEY and is excluded from
# grouping entirely: an empty key must never match another empty key, so two
# unnamed objects are not duplicates of each other.
# ===========================================================================

#: Writing-system scope tokens. The scope differs BY CLASS and in opposite
#: directions -- `PhPhoneme` keys on the default VERNACULAR (measured 97/97,
#: against only 44/97 in the analysis WS) while every other admitted class keys
#: on the default ANALYSIS WS -- so the scope is stored per class rather than
#: assumed once for all of them.
WS_SCOPE_VERNACULAR = "default_vernacular"
WS_SCOPE_ANALYSIS = "default_analysis"


@dataclass(frozen=True)
class NaturalKeyDefinition:
    """How one class's duplicate key is computed, and how it is described.

    `description` is emitted verbatim as `duplicates.key_definition`, so a
    reader of the artifact can tell WHICH key produced a duplicate group
    without reading this file. `roster_source` records which document admits the
    class, because admission to gate-failing duplicate detection is by roster
    enumeration only (FR-003's rule for matching, applied to duplicates).

    T098: `roster_source` IS A CHECKED CLAIM, and it took a filing to make it
    one. It had a DEFAULT (`"roster_extension_038"`) that six of the seven
    entries inherited and a seventh overrode with the other spelling -- two
    writers disagreeing about which document admits the roster, and no reader
    anywhere in `src/` or `tests/` to notice. 035 admitted all six on
    2026-08-19, so every one of those six inherited values had been WRONG for
    two days and nothing could say so. A field with no reader is not a tripwire;
    it is decoration.

    Two changes make it one. The default is GONE, so a new definition cannot
    acquire a provenance claim by omission -- it has to state which document
    admits the class. And `roster_source_disagreements` compares every claim
    against the two documents on disk, with `verify_roster_sources` raising on
    any disagreement before a census opens a project.

    Note what this field can NOT do, so it is not mistaken for the admission
    mechanism: `duplicates.roster_admitted` is computed by
    `roster_admitted_classes`, which READS 035's roster at run time. That is the
    tripwire the docstring below describes and it worked exactly as designed --
    the six classes became gate-failing on the merge with no edit here.
    `roster_source` is the code's own record of WHY it believes what it
    believes, and its job is to disagree out loud when that belief goes stale.
    """

    object_class: str
    property_name: str
    ws_scope: str
    description: str
    roster_source: str

    def __post_init__(self) -> None:
        if self.ws_scope not in (WS_SCOPE_VERNACULAR, WS_SCOPE_ANALYSIS):
            raise CensusError(
                "NaturalKeyDefinition.ws_scope for "
                + repr(self.object_class) + " is " + repr(self.ws_scope)
            )
        if self.roster_source not in ROSTER_SOURCES:
            raise CensusError(
                "NaturalKeyDefinition.roster_source for "
                + repr(self.object_class) + " is " + repr(self.roster_source)
                + ", outside " + repr(ROSTER_SOURCES) + " -- the two documents "
                "that can admit or propose a natural key are enumerated, so a "
                "third spelling is a typo that would be checked against "
                "nothing"
            )


#: The classes whose duplicate keys the census can compute. A class absent from
#: this table gets NO `duplicates` block rather than an `extra_objects: 0`
#: block, because 0 would claim the census looked.
#:
#: T098: every entry now names its admitting document, and all seven name 035's
#: roster. Six of them used to name 038's PROPOSAL by inheriting the field's
#: default -- accurate when written (2026-08-18) and stale from 2026-08-19,
#: when 035 appended all six in the order 038 asked for. The values are checked
#: against the documents by `verify_roster_sources`, so this comment is not the
#: thing keeping them true.
NATURAL_KEY_DEFINITIONS: dict = {
    "PhPhoneme": NaturalKeyDefinition(
        "PhPhoneme", "Name", WS_SCOPE_VERNACULAR,
        "Name (default vernacular alt), exact and case-sensitive",
        roster_source=ROSTER_SOURCE_035,
    ),
    "PhNCSegments": NaturalKeyDefinition(
        "PhNCSegments", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "PhPhonData natural-class list and restricted to PhNCSegments",
        roster_source=ROSTER_SOURCE_035,
    ),
    "PhNCFeatures": NaturalKeyDefinition(
        "PhNCFeatures", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "PhPhonData natural-class list and restricted to PhNCFeatures, "
        "AND ONLY WHERE THAT NAME IS NOT A FLEx AUTO-GENERATED RULE LABEL "
        "(`Created automatically for rule \"<rule>\"`) -- such a label names "
        "the RULE that owns the class, not the class, so two objects sharing "
        "one are not the same linguistic object and are not a duplicate pair",
        roster_source=ROSTER_SOURCE_035,
    ),
    "PartOfSpeech": NaturalKeyDefinition(
        "PartOfSpeech", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, project-wide "
        "over the recursive hierarchy; the owning parent is NOT part of the key",
        roster_source=ROSTER_SOURCE_035,
    ),
    "MoMorphType": NaturalKeyDefinition(
        "MoMorphType", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "lexicon's morph-types list",
        roster_source=ROSTER_SOURCE_035,
    ),
    "LexEntryInflType": NaturalKeyDefinition(
        "LexEntryInflType", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "variant-entry-types list and restricted to LexEntryInflType",
        roster_source=ROSTER_SOURCE_035,
    ),
    "WfiWordform": NaturalKeyDefinition(
        "WfiWordform", "Form", WS_SCOPE_VERNACULAR,
        "Form (default vernacular alt), exact and case-sensitive",
        roster_source=ROSTER_SOURCE_035,
    ),
}


def roster_admitted_classes(root: Optional[Path] = None) -> frozenset:
    """The classes 035's roster ADMITS, read at run time.

    Admission is what makes a duplicate group able to FAIL the gate. A duplicate
    name on an unadmitted class is surfaced as advisory instead, because
    homographs are legitimate content and the roster -- not this file -- decides
    which classes have a key. Reading the file rather than hard-coding the three
    current entries means the six entries feature 038 proposes (T028) become
    gate-failing the moment 035 merges them, with no edit here.
    """
    base = repo_root() if root is None else Path(root)
    path = base / NATURAL_KEY_ROSTER_DOCUMENT
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(
        entry["class"] for entry in data.get("entries", ())
        if entry.get("class")
    )


def roster_extension_proposed_classes(root: Optional[Path] = None) -> frozenset:
    """The classes 038's extension PROPOSES, read at run time.

    A proposal is not an admission and this file is not emptied when 035 takes
    an entry -- it is the proposal record -- so a class can legitimately appear
    here and in 035's roster at the same time. That is exactly why provenance
    has to be checked against BOTH documents rather than inferred from either.
    """
    base = repo_root() if root is None else Path(root)
    path = base / NATURAL_KEY_ROSTER_EXTENSION_DOCUMENT
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(
        entry["class"] for entry in data.get("proposed_entries", ())
        if entry.get("class")
    )


def roster_source_disagreements(root: Optional[Path] = None) -> tuple:
    """T098: every `roster_source` claim, checked against the two documents.

    THE READER THIS FIELD DID NOT HAVE. `roster_source` was written three times
    in `src/` and `tests/` and read none of them, so the six entries that
    claimed 038's proposal went on claiming it for two days after 035 admitted
    them. This is the check that makes the claim falsifiable.

    IT FIRES IN BOTH DIRECTIONS, and the second direction is the one worth
    having. A definition claiming `ROSTER_SOURCE_035` for a class 035 does NOT
    admit means the census believes that class's duplicates can fail the gate
    when `roster_admitted_classes` will quietly mark them advisory -- which is
    what a roster REMOVAL looks like from in here, and there is nothing else in
    the tree that would notice one. A definition claiming
    `ROSTER_SOURCE_038_PROPOSAL` for a class 035 has since admitted is the
    staleness T098 was filed for.

    Returns one human-readable line per disagreement, empty when the code and
    the documents agree.
    """
    base = repo_root() if root is None else Path(root)
    admitted = roster_admitted_classes(base)
    proposed = roster_extension_proposed_classes(base)
    out = []
    for name, definition in sorted(NATURAL_KEY_DEFINITIONS.items()):
        source = definition.roster_source
        if source == ROSTER_SOURCE_035 and name not in admitted:
            out.append(
                name + " claims roster_source " + repr(source) + " but "
                + NATURAL_KEY_ROSTER_DOCUMENT + " does not admit it -- the "
                "census believes this class's duplicates can FAIL the gate "
                "while roster_admitted_classes will mark them advisory"
            )
        elif source == ROSTER_SOURCE_038_PROPOSAL:
            if name in admitted:
                out.append(
                    name + " claims roster_source " + repr(source) + " but "
                    + NATURAL_KEY_ROSTER_DOCUMENT + " has ADMITTED it -- the "
                    "proposal landed and this claim is stale (T098)"
                )
            elif name not in proposed:
                out.append(
                    name + " claims roster_source " + repr(source) + " but "
                    + NATURAL_KEY_ROSTER_EXTENSION_DOCUMENT + " does not "
                    "propose it either, so no document accounts for this key"
                )
    return tuple(out)


def verify_roster_sources(root: Optional[Path] = None) -> None:
    """Raise `CensusError` naming every `roster_source` disagreement.

    Called before a census opens a project, for the same reason
    `derive_class_list` raises `CoverageIncomplete` on a CP-1 derivation
    mismatch: a disagreement between the code's belief and the contracts on
    disk is a defect in the instrument, and an instrument that is wrong about
    which classes can fail its own gate should not be measuring anything.
    """
    disagreements = roster_source_disagreements(root)
    if disagreements:
        raise CensusError(
            "the natural-key definitions disagree with the roster documents "
            "about which document admits which class: "
            + "; ".join(disagreements),
            tuple(line.split(" ", 1)[0] for line in disagreements),
        )


def _ws_handle_for(handle, ws_scope: str):
    """The writing-system handle one key scope names, or None.

    None means the key is NOT COMPUTABLE for this project, which the caller must
    report -- never silently fall back to another writing system. Matching a
    secondary vernacular would have fabricated 16 matches on `Yi Sichuan`
    alone (the roster's measured counterexample).
    """
    getter = (
        "GetDefaultVernacularWSHandle" if ws_scope == WS_SCOPE_VERNACULAR
        else "GetDefaultAnalysisWSHandle"
    )
    method = getattr(handle, getter, None)
    if callable(method):
        try:
            return method()
        except Exception:  # noqa: BLE001
            return None
    cache = getattr(handle, "Cache", None)
    attr = "DefaultVernWs" if ws_scope == WS_SCOPE_VERNACULAR else "DefaultAnalWs"
    return getattr(cache, attr, None)


def natural_key_of(obj, definition: NaturalKeyDefinition, ws_handle) -> Optional[str]:
    """One object's natural key, or None when it HAS no key.

    Exact string, taken from the named property's alt in the scoped writing
    system. Returned unchanged: no `.strip()`, no `.casefold()`, no
    `unicodedata.normalize`. None (no such property, no alt, empty alt) means
    the object has no key and must not be grouped -- an empty key never matches
    another empty key.

    **THIS FUNCTION STAYS A PURE NAME READER, AND THAT IS LOAD-BEARING.**
    `matcher` builds its key functions on this one *precisely* so the two can
    never hold different keys for a class (see `matcher.py`'s import comment),
    and then layers its OWN eligibility verdicts on top --
    `KEY_INELIGIBLE_AUTO_GENERATED` vs `KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS`
    are distinct reasons it must be able to tell apart. Filtering ineligible
    keys to `None` HERE collapses "has an ineligible name" into "has no name",
    which is a different and wrong statement about the object. Eligibility
    therefore belongs to the duplicate-detection path only, in
    `group_by_natural_key`. Measured the hard way on 2026-08-28: the filter was
    first put here and immediately turned
    `test_auto_generated_natural_class_names_are_ineligible` red by reporting
    the wrong reason.
    """
    if ws_handle is None:
        return None
    prop = getattr(obj, definition.property_name, None)
    if prop is None:
        return None
    try:
        alt = prop.get_String(ws_handle)
    except Exception:  # noqa: BLE001 -- not a multistring on this subclass
        alt = None
    text = getattr(alt, "Text", None)
    if text is None:
        return None
    text = str(text)
    return text if text else None


def _key_is_eligible(object_class: str, text: str) -> bool:
    """False when the roster declares this key string an ineligible KEY for
    this class, so duplicate detection must not group on it.

    **WHY THIS EXISTS (feature 038, T082 / `038-NK-P3`, 2026-08-28), AND WHY IT
    IS A CORRECTION RATHER THAN AN EXEMPTION.** The census shares its key
    DEFINITIONS with the matcher but never shared the matcher's ELIGIBILITY
    predicate, so for `PhNCFeatures` the census grouped on a key strictly WIDER
    than the roster ratifies. The roster entry
    (`contracts/natural-key-roster-extension.json`) admits that class by
    predicate -- "*and only where that name is not a FLEx auto-generated rule
    label*" -- with a `key_scoping_note` stating that such a name "identifies
    the RULE that owns the class, not the class" and is "never matched, and not
    treated as an ambiguity either".

    What the drift cost, measured across three live pairs (T124): **36 of 36**
    duplicate groups on `PhNCFeatures` are the auto-generated label (ejagham 1,
    ngoreme 12, mbugwe 23). They contribute ALL of `duplicate_extra_objects`
    (3 / 21 / 66) and force `DUPLICATE_IDENTITY` / exit 3 on every pair --
    while the row itself is MATCHED (15->15, 41->41, 113->113) against a
    starter baseline of ZERO. FLEx names every natural class it auto-creates
    after the rule that owns it, so one rule owning several context classes
    yields several identically-named objects **in the source**; mbugwe's source
    is independently measured at the same 113 objects / 66 collisions. The
    duplication is REPRODUCED, not manufactured, and the roster's own
    `collision_forensics` already calls it "correct data, not a defect".

    So the gate was failing on a FALSE READING produced by the wrong key. The
    fix is the right key, NOT an exemption: an exemption suppresses a true
    reading, whereas correcting the key keeps the detector live for a real
    `PhNCFeatures` duplicate on a linguist-chosen name -- the case actually
    worth catching.

    Reads `matcher`'s constants rather than restating the rule, so the two
    cannot drift again. The import is lazy and matches `matcher`'s own
    convention (it imports `census`, so a module-level import here would close
    a cycle). Fails OPEN: a census that cannot read the rule must not silently
    start ignoring objects, because a suppressed duplicate looks exactly like a
    clean transfer.
    """
    try:
        if __package__:
            from . import matcher as _matcher
        else:
            import matcher as _matcher  # type: ignore[no-redef]
    except Exception:  # noqa: BLE001 -- census must stay importable alone
        return True
    classes = getattr(_matcher, "_AUTO_GENERATED_LABEL_CLASSES", frozenset())
    prefix = getattr(_matcher, "_AUTO_GENERATED_NAME_PREFIX", None)
    if prefix and object_class in classes and text.startswith(prefix):
        return False
    return True


@dataclass(frozen=True)
class DuplicateReport:
    """-> artifact `$defs.duplicates` for one class row.

    `groups` counts keys held by MORE THAN ONE destination object;
    `extra_objects` is `sum(group_size - 1)` over those groups -- the number of
    objects that would not exist if matching had worked. `examples` is NEVER
    truncated (invariant 2): truncation is legal only in the console summary,
    which must state how many items it omitted.
    """

    object_class: str
    roster_admitted: bool
    key_definition: str
    groups: int
    extra_objects: int
    examples: tuple = ()

    def __post_init__(self) -> None:
        for name in ("groups", "extra_objects"):
            if getattr(self, name) < 0:
                raise CensusError(
                    "DuplicateReport." + name + " must be >= 0 on class "
                    + repr(self.object_class)
                )
        if self.groups and not self.extra_objects:
            raise CensusError(
                "DuplicateReport for " + repr(self.object_class) + " claims "
                + str(self.groups) + " duplicate groups but 0 extra objects -- "
                "a group of size > 1 contributes at least one extra object"
            )

    def artifact(self) -> dict:
        block = {
            "roster_admitted": self.roster_admitted,
            "key_definition": self.key_definition,
            "groups": self.groups,
            "extra_objects": self.extra_objects,
            "examples": [dict(e) for e in self.examples],
        }
        return block


def group_by_natural_key(objects, definition: NaturalKeyDefinition, ws_handle) -> dict:
    """`{key: [objects]}` over the objects that HAVE a key, insertion-ordered.

    Objects with no key are omitted rather than collected under a shared
    sentinel, which is the whole point: two unnamed phonemes are two unnamed
    phonemes, not a duplicate pair.

    **Objects whose key the roster declares INELIGIBLE are omitted for exactly
    the same reason** (feature 038, T082, 2026-08-28): two natural classes both
    named `Created automatically for rule "X"` are two classes FLEx named after
    one rule, not a duplicate pair. See `_key_is_eligible`. This is the only
    place the predicate is applied -- `natural_key_of` stays a pure name reader
    because `matcher` builds on it and must keep "ineligible name" and "no
    name" as distinct verdicts.
    """
    grouped: dict = {}
    for obj in objects:
        key = natural_key_of(obj, definition, ws_handle)
        if key is None:
            continue
        if not _key_is_eligible(definition.object_class, key):
            continue
        grouped.setdefault(key, []).append(obj)
    return grouped


def _guid_str(obj) -> str:
    try:
        return str(obj.Guid)
    except Exception:  # noqa: BLE001
        return ""


def duplicate_report(
    object_class: str,
    objects,
    *,
    ws_handle,
    definition: Optional[NaturalKeyDefinition] = None,
    roster_admitted: bool = False,
) -> Optional[DuplicateReport]:
    """Group one class's destination objects by natural key and count the extras.

    Returns None when the class has no key definition at all -- the honest
    answer, because an `extra_objects: 0` block would claim a measurement that
    never happened.
    """
    spec = definition or NATURAL_KEY_DEFINITIONS.get(object_class)
    if spec is None:
        return None
    grouped = group_by_natural_key(objects, spec, ws_handle)
    examples = []
    groups = 0
    extra = 0
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        groups += 1
        extra += len(members) - 1
        examples.append({
            "key": key,
            "count": len(members),
            "guids": [g for g in (_guid_str(m) for m in members) if g],
        })
    return DuplicateReport(
        object_class=object_class,
        roster_admitted=roster_admitted,
        key_definition=spec.description,
        groups=groups,
        extra_objects=extra,
        examples=tuple(examples),
    )


def duplicate_reports_for(
    handle,
    class_names,
    *,
    admitted: Optional[frozenset] = None,
    objects_for=None,
) -> dict:
    """`{class: DuplicateReport}` for every class that has a key definition.

    `objects_for(handle, class_name)` is the enumeration seam; it defaults to
    `objects_in_class`, which enumerates each class exactly ONCE and raises
    rather than returning an empty list when the class cannot be enumerated.
    """
    admitted_set = (
        roster_admitted_classes() if admitted is None else admitted
    )
    enumerate_objects = objects_for or objects_in_class
    handles: dict = {}
    out: dict = {}
    for name in dict.fromkeys(class_names):
        spec = NATURAL_KEY_DEFINITIONS.get(name)
        if spec is None:
            continue
        if spec.ws_scope not in handles:
            handles[spec.ws_scope] = _ws_handle_for(handle, spec.ws_scope)
        report = duplicate_report(
            name,
            enumerate_objects(handle, name),
            ws_handle=handles[spec.ws_scope],
            definition=spec,
            roster_admitted=name in admitted_set,
        )
        if report is not None:
            out[name] = report
    return out


# ---------------------------------------------------------------------------
# T048d -- THE IDENTITY AUDIT: a GUID-level comparison, for the class that
# arrives correct with no record of arriving
#
# THE DEFECT. `MoMorphType` reported `difference -19` on run
# `CENSUS-20260820-114752` while the two `.fwdata` files held the SAME 19 morph
# types by GUID -- source 19, destination 19, 0 missing, 0 destination-only,
# identical GUID sets. Nothing was wrong with the transfer. The row was wrong.
#
# WHY NOTHING ALREADY IN THE CENSUS COULD FIX IT. `_row_for_entry` earns the
# `baseline_matched` basis from ONE source of evidence: a per-class matched
# tally in the run report. T048b widened what feeds that tally (an
# `ALREADY_PRESENT_BY_GUID` skip is a match) and still could not reach this row,
# because `MoMorphType` has no record of ANY kind -- no action, no overwrite, no
# skip. The morph-types list is FW-global fixed content: `Lib/categories.py`'s
# `_resolve_target_morph_type` states it outright ("Morph types live in the
# global (shared) list at LangProject.LexDbOA.MorphTypesOA and carry identical
# GUIDs across every FW project"), and `_entry_all_deps` adds "MorphType is
# FW-global; no dependency edge is emitted for it". So the class arrives
# correct, nothing happens, nothing is recorded, and gross subtraction removes
# all 19 starters as surplus.
#
# A run report can never close this. The evidence has to come from the projects
# themselves, which is what this section adds.
#
# ---------------------------- THE BOUND, PROVED ----------------------------
# Write S for the starter set (|S| = the baseline count B), D for the
# destination set and Q for the source set. `starter_matched_to_source` is
# |S n Q| and `unmatched_starter` is |S \ Q|. The baseline document records
# `class`, `count` and `names` and NO GUIDS, so S itself is not addressable --
# but it does not need to be:
#
#     S subset of D                        (no starter object was deleted)
#     => S \ Q  subset of  D \ Q
#     => |S \ Q| <= |D \ Q|
#     => |S n Q| = B - |S \ Q| >= B - |D \ Q|
#
# So `B - |D \ Q|`, clamped to [0, B], is a PROVABLE LOWER BOUND on
# `starter_matched_to_source` computed from two GUID sets the census can read
# directly. On `MoMorphType` it is exact and tight: |D \ Q| is 0, so the bound
# is 19 of 19, `unmatched_starter` is 0, and `difference` is 0.
#
# A LOWER BOUND IS THE SAFE DIRECTION, and that is why a bound is acceptable
# here at all. Understating `starter_matched_to_source` OVER-subtracts, which
# can only ever manufacture a shortfall the run does not have; overstating it
# under-subtracts and HIDES a real one. `_row_for_entry` already reasons this
# way about the gross basis, and this bound errs the same way for the same
# reason: "being wrong in the capped, advisory direction is recoverable;
# silently claiming a trustworthy answer is not".
#
# THE ONE ASSUMPTION, NAMED, AND ITS GUARD. The proof needs `S subset of D`,
# i.e. that no starter object was deleted. This feature's engine is additive
# (FR-021: enrichment "MUST NOT remove, blank, or overwrite content already
# present"), but that is the engine's own contract and an instrument that
# audits the engine should not simply believe it. So the assumption is guarded
# by its own arithmetic: a deleted starter shows up as `|D| < B`, and
# `starter_matched_lower_bound` REFUSES (returns None, leaving the row on the
# gross basis) whenever the destination holds fewer objects than the starter
# did. What the guard does not catch is a delete-one-create-one within a single
# class, which would leave |D| unchanged; that residue is stated in
# `starter_matched_lower_bound`'s docstring rather than papered over.
#
# WHY NOT PUT GUIDS IN THE STARTER BASELINE INSTEAD. That was the other route
# and it would make |S n Q| exact rather than bounded. It was not taken: the
# baseline document is a captured artifact, the capture that produced the one in
# use ("GT038 T023b Scratch") no longer exists on disk, and a re-capture from a
# different blank project would move `content_hash` and `fwdata_sha256` and so
# invalidate the comparability of every measurement already taken against it.
# A bound that needs no re-capture, and that errs toward reporting a shortfall,
# buys the same row for none of that.
#
# THIS IS NOT AN ATTRIBUTED MATCH. Nothing here reads a plan, a report or a
# disposition, and nothing credits a match to a class on the strength of a
# record that does not exist. Both numbers are read off the two projects the
# census already opens, by GUID.
# ---------------------------------------------------------------------------


def guids_in_class(handle, object_class: str) -> frozenset:
    r"""Every GUID of exactly `object_class` in one project, as a set.

    Built on `objects_in_class`, so the exact-class filter and its raise-rather-
    than-yield-nothing posture are inherited verbatim: an empty set always
    means "measured, and none", never "could not look".

    An object that will not produce a GUID RAISES rather than being dropped.
    A silently short GUID set would understate `|D \ Q|` and so OVERSTATE the
    lower bound, which is the one direction this whole section must not be
    wrong in.
    """
    out = set()
    for obj in objects_in_class(handle, object_class):
        guid = _guid_str(obj)
        if not guid:
            raise CensusError(
                "cannot audit " + repr(object_class) + " by identity: an "
                "object of that class will not produce a Guid, and dropping "
                "it would shrink the destination-only set and OVERSTATE "
                "starter_matched_to_source -- the one direction the identity "
                "audit must never be wrong in",
                (object_class,),
            )
        out.add(guid)
    return frozenset(out)


def guid_sets_for(handle, class_names, *, objects_for=None) -> tuple:
    """`({class: frozenset(guid)}, {class: why not})` for one open project.

    Per class rather than per project: a class the census cannot enumerate is
    recorded in the second dict and simply absent from the first, so the audit
    declines for THAT row alone and every other row keeps its evidence. The
    alternative -- failing the whole pass -- would let one unreadable class
    push every row back onto the gross basis.

    `objects_for` is the same enumeration seam `duplicate_reports_for` takes,
    so a test can drive this without a live project.
    """
    enumerate_objects = objects_for or objects_in_class
    out: dict = {}
    unreadable: dict = {}
    for name in dict.fromkeys(class_names):
        try:
            found = set()
            for obj in enumerate_objects(handle, name):
                guid = _guid_str(obj)
                if not guid:
                    raise CensusError(
                        "an object of class " + repr(name) + " will not "
                        "produce a Guid", (name,))
                found.add(guid)
            out[name] = frozenset(found)
        except Exception as exc:  # noqa: BLE001 -- one class, not the pass
            unreadable[name] = type(exc).__name__ + ": " + str(exc)
    return out, unreadable


#: What `starter_matched_lower_bound` returns instead of a number when the
#: audit declines, spelled as a name so the caller's branch reads as a refusal
#: rather than as a missing value.
IDENTITY_AUDIT_DECLINED = None


def starter_matched_lower_bound(
    baseline_count: Optional[int],
    destination_count: Optional[int],
    destination_guids,
    source_guids,
) -> Optional[int]:
    r"""`B - |D \ Q|` clamped to `[0, B]` -- a lower bound on the starter
    objects matched to a source object, or None when the audit declines.

    The derivation is in this section's header. Four refusals, each of which
    leaves the row on the gross basis:

    * no baseline count for the row -- there is no B to bound;
    * either GUID set unread -- `guid_sets_for` recorded why;
    * `|D|` disagrees with the row's own `destination_count` -- the audit would
      then be measuring a different population from the row it is about to
      change, and reconciling the two by preferring one is exactly the kind of
      silent choice this instrument exists to avoid;
    * `|D| < B` -- a starter object is provably gone, so `S subset of D` (the
      proof's one assumption) has already failed and the bound does not hold.

    KNOWN RESIDUE, stated rather than hidden: a run that deleted one starter of
    a class AND created one object of the same class leaves `|D|` equal to `B`,
    passes the guard, and lets the bound overstate by one. Closing that needs
    the starter's GUIDs, which the baseline document does not carry (see the
    header). Nothing in this feature's engine has such a path for the classes
    the audit moves -- the FW-global lists are never created and never deleted
    -- but the bound does not prove that and does not claim to.
    """
    if baseline_count is None or destination_count is None:
        return IDENTITY_AUDIT_DECLINED
    if destination_guids is None or source_guids is None:
        return IDENTITY_AUDIT_DECLINED
    if len(destination_guids) != destination_count:
        return IDENTITY_AUDIT_DECLINED
    if destination_count < baseline_count:
        return IDENTITY_AUDIT_DECLINED
    destination_only = len(set(destination_guids) - set(source_guids))
    return max(0, min(baseline_count, baseline_count - destination_only))


# ---------------------------------------------------------------------------
# Amendment A1 -- `FsFeatStrucType` is counted PER FEATURE SYSTEM
#
# A FieldWorks project has TWO feature systems, and both own
# `FsFeatStrucType`: `LangProject.MsFeatureSystemOA` (morphosyntactic) and
# `LangProject.PhFeatureSystemOA` (phonological). A single summed row is
# ambiguous, because a shortfall in one system is masked by a surplus in the
# other -- the same masking defect section 6 rule 2 exists to prevent for
# duplicate identity. Each part is evaluated INDEPENDENTLY against section 9.
#
# THE OWNER ENCODING IS SETTLED: `row_property`.
#
# `fidelity-census.md:650-673` requires the row to "carry the owner". When this
# was first written `$defs.classRow` had no owner property, so two encodings
# were possible and the choice was left at the seam below:
#
#   1. "class_string"  -- `class: "FsFeatStrucType(MsFeatureSystem)"`. Needed no
#      contract edit and validated as it stood, but NOTHING checked the owner:
#      an unvalidated convention inside a string; a consumer joining on `class`
#      saw two unknown classes; the phase-predicate lookup had to prefix-match a
#      class name to find a split row; and the emitted class names outnumbered
#      the class roster by one pseudo-class while A1 insists the class count is
#      unchanged.
#   2. "row_property" -- `owning_feature_system` alongside a PLAIN `class`.
#
# Option 2 is now the choice, and the contract carries it: `classRow` gained
# `owning_feature_system` as a new OPTIONAL property, enumerated to exactly the
# two spellings A1 itself uses, so the owner is VALIDATED rather than merely
# conventional and `class` goes back to being the plain LCM class name on both
# halves. A row without the property -- every ordinary class -- validates
# unchanged, which is what makes the addition additive under the schema
# EVOLUTION RULE.
#
# "class_string" is RETAINED, unused, purely so the decision stays reversible at
# one constant. It is a fallback, not an equal alternative: switching back
# reintroduces all four costs above.
# ---------------------------------------------------------------------------

#: The A1 seam. `"row_property"` (settled, backed by the `classRow` property of
#: the same name) or `"class_string"` (retained fallback only).
A1_OWNER_ENCODING = "row_property"

#: The two owning feature systems. These spellings are the CONTRACT ones
#: (fidelity-census.md:650-673) and the schema enum members, not a local
#: shorthand: they are emitted verbatim into `owning_feature_system`, so a
#: shorter token invented here would fail validation.
#:
#: RE-EXPORT, NOT RE-DECLARATION -- `models.CENSUS_FEATURE_SYSTEM_OWNERS` owns
#: the literals, the same way it owns `CENSUS_REASON_TOKENS`. The direction is
#: forced: census -> models is the only legal import direction, and
#: `models.ClassCensusRow` has to reject an out-of-vocabulary owner at
#: construction, so the tuple cannot live here.
FEATURE_SYSTEM_OWNERS: tuple = CENSUS_FEATURE_SYSTEM_OWNERS

#: `LangProject` attribute per owner token.
FEATURE_SYSTEM_ATTRS: dict = {
    "LangProject.MsFeatureSystemOA": "MsFeatureSystemOA",
    "LangProject.PhFeatureSystemOA": "PhFeatureSystemOA",
}

#: Classes reachable from BOTH feature systems, which A1 therefore splits. A1's
#: closing sentence extends the requirement to "any other class reachable from
#: both feature systems", so this is a set rather than a single class name.
FEATURE_SYSTEM_SPLIT_CLASSES: frozenset = frozenset({"FsFeatStrucType"})


def encode_split_owner(row: dict, object_class: str, owner: Optional[str]) -> dict:
    """THE A1 SEAM. Put the owning feature system into an emitted class row.

    Every A1-aware emission goes through here, so the encoding is decided in
    exactly one place. `class` is the PLAIN LCM class name on every row,
    including both halves of a split, and the owner rides in
    `owning_feature_system`. See the settled-encoding note above.
    """
    if owner is None:
        row["class"] = object_class
        return row
    if A1_OWNER_ENCODING == "row_property":
        row["class"] = object_class
        row["owning_feature_system"] = owner
        return row
    # Retained fallback only; reintroduces the four costs named above.
    row["class"] = split_class_label(object_class, owner)
    return row


def split_feature_system_entries(class_list: ClassList) -> ClassList:
    """Expand each A1 class into one entry PER OWNING FEATURE SYSTEM.

    An accounting change only: the CP-1 required class count is untouched (A1's
    own words -- it "adds no class to the required list"), because both parts
    carry the same `object_class`. `ClassList.required_classes` therefore still
    reports `FsFeatStrucType` twice for one class, while `row_key` keeps the two
    rows distinct so neither can be summed into the other.
    """
    entries = []
    for entry in class_list.entries:
        if (entry.object_class not in FEATURE_SYSTEM_SPLIT_CLASSES
                or entry.owning_feature_system is not None):
            entries.append(entry)
            continue
        for owner in FEATURE_SYSTEM_OWNERS:
            entries.append(ClassListEntry(
                object_class=entry.object_class,
                in_class_list_via=entry.in_class_list_via,
                gate_scope=entry.gate_scope,
                engine_can_create=entry.engine_can_create,
                inventory_tables=entry.inventory_tables,
                not_evaluated_reason=entry.not_evaluated_reason,
                owning_feature_system=owner,
            ))
    return ClassList(
        entries=tuple(entries),
        derivation_check=dict(class_list.derivation_check),
        provenance=dict(class_list.provenance),
    )


def split_counts(handle, class_list: ClassList) -> dict:
    """`{row_key: count}` for every A1-split row in `class_list`.

    THE POINT OF THIS FUNCTION IS THAT IT EXISTS. `count_classes` returns one
    number per CLASS, which for `FsFeatStrucType` is the summed repository total
    -- precisely the ambiguous figure A1 forbids. A driver that fills the two
    split rows from that dict gives both halves the same number and the split
    becomes decorative: two rows, one measurement, and a shortfall in one system
    still masked by a surplus in the other. So the per-owner counts get their own
    call, keyed by `row_key`, for the driver to prefer over the class total.

    Measured on `Ejagham Mini`: 3 under MsFeatureSystemOA, 0 under
    PhFeatureSystemOA, summing to the repository total of 3.
    """
    out: dict = {}
    for object_class in sorted({
            e.object_class for e in class_list.entries
            if e.owning_feature_system is not None}):
        per_owner = count_by_feature_system(handle, object_class)
        for entry in class_list.entries_for(object_class):
            if entry.owning_feature_system is None:
                continue
            out[entry.row_key] = per_owner.get(entry.owning_feature_system, 0)
    return out


def count_by_feature_system(handle, object_class: str) -> dict:
    """`{owner: count}` for one A1 class, counted through each owning system.

    Counted from `LangProject.<system>OA.TypesOC` rather than from the class
    repository, because the repository total is exactly the ambiguous summed
    figure A1 forbids. An owning system that is absent counts 0 -- a project
    with no phonological feature system genuinely owns no phonological types,
    which is a measurement and not an unresolved accessor.
    """
    counts: dict = {}
    lang_project = getattr(handle, "lp", None)
    if lang_project is None:
        lang_project = getattr(getattr(handle, "project", None),
                               "LangProject", None)
    for owner in FEATURE_SYSTEM_OWNERS:
        system = getattr(lang_project, FEATURE_SYSTEM_ATTRS[owner], None)
        if system is None:
            counts[owner] = 0
            continue
        types = getattr(system, "TypesOC", None)
        if types is None:
            counts[owner] = 0
            continue
        try:
            counts[owner] = int(types.Count)
        except Exception as exc:  # noqa: BLE001
            raise CensusError(
                "cannot count " + object_class + " under "
                + FEATURE_SYSTEM_ATTRS[owner] + ": " + type(exc).__name__
                + ": " + str(exc) + " -- A1 requires the two feature systems "
                "to be counted separately, and a summed fallback is exactly "
                "the ambiguity it forbids",
                (object_class,),
            ) from exc
    return counts


# ===========================================================================
# T019 -- the accounting arithmetic, and the artifact emitter
#
# THE THREE COUNTS AND THE SIGN CONVENTION (fidelity-census.md 4, 5.2, 7):
#
#     unmatched_starter     = starter_baseline_count - starter_matched_to_source
#     destination_count_net = destination_count_total - unmatched_starter
#     difference            = destination_count_net - source_count
#     difference_raw        = destination_count_total - source_count
#
#     difference <  0  SHORTFALL   difference == 0  MATCHED   > 0  SURPLUS
#
# The subtrahend is the starter objects NOT matched to a source object, never
# the gross baseline. Gross subtraction is wrong the moment natural-key
# matching works: on the fixed phoneme run (source 41, destination 43, starter
# 23 of which 21 matched) gross gives 43 - 23 = 20 and reports -21, a shortfall
# on a CORRECT run. Matched gives 43 - 2 = 41, difference 0.
#
# NO CROSS-CLASS NETTING, EVER. Every function here takes ONE row's numbers.
# There is deliberately no signature anywhere in this module that can see two
# classes' differences at once, and `build_totals` reports `total_shortfall` and
# `total_surplus` separately and never sums them: Ejagham's MoAffixProcess
# 13 -> 0 and MoAffixAllomorph +13 are the SAME defect seen twice, and netting
# them to zero is precisely the SC-010 failure this feature exists to end.
#
# WHAT THIS TASK HAD TO SUPPLY ITSELF (T015's open disagreement 1).
# `$defs.classRow` REQUIRES 13 keys; `models.ClassCensusRow` has 9, and four of
# the required keys are not functions of those 9. Resolution:
#   * `gate_scope`, `in_class_list_via` (+ optional `inventory_tables`) come
#     from T016's `ClassListEntry`, carried through -- the loader is the only
#     thing that actually knows CP-3's advisory marking and CP-4's provenance,
#     so re-deciding them at emission time would be a second source of truth.
#   * `accounted_for` is an EMITTER ARGUMENT (`AccountedLine` objects): the row
#     carries only reason TOKENS, never their counts, directions or report refs.
#   * `unexplained_shortfall` / `unexplained_surplus` are DERIVED here from the
#     difference and the lines by section 7's formula -- never passed in, so a
#     caller cannot understate them.
# `ClassCensusRow` itself is unchanged: it is `data-model.md`'s frozen shape and
# `models.py` is the wrong place for artifact-only provenance.
# ===========================================================================

#: Precedence for picking the ONE `not_evaluated_reason` out of a row's reason
#: TUPLE (T015's open disagreement 3: `data-model.md`:112 is a tuple, schema
#: `:427-430` is a single token). Most absolute first: a class that cannot exist
#: at all outranks one that is merely outside this feature's scope, which
#: outranks one another feature governs. Chosen against the named set
#: `CENSUS_NOT_EVALUATED_REASONS` so the choice is auditable rather than
#: incidental to tuple order.
NOT_EVALUATED_REASON_PRECEDENCE: tuple = (
    "ABSENT_BY_CONSTRUCTION",
    "OUT_OF_SCOPE_CLASS",
    "GOVERNED_BY_OTHER_FEATURE",
)

#: `$defs.accountedLine.direction`.
DIRECTIONS: tuple = ("shortfall", "surplus")

#: `$defs.classRow.starter_subtraction_basis`.
SUBTRACTION_BASES: tuple = ("baseline_matched", "baseline_gross", "no_baseline")

#: The one `starter_baseline_source` on which a baseline count is a
#: MEASUREMENT of the starter project rather than a statement about what the
#: baseline failed to say. Named for the same reason as
#: `GROSS_SUBTRACTION_BASIS`: T110 makes `is_gross_basis_row` turn on it, so a
#: typo here would silently re-cap every exact-arithmetic row.
BASELINE_SOURCE_DOCUMENT: str = "baseline_document"

#: `$defs.classRow.starter_baseline_source`.
BASELINE_SOURCES: tuple = (
    BASELINE_SOURCE_DOCUMENT, "absent_from_baseline",
    "assumed_zero_not_permitted",
)


def select_not_evaluated_reason(reasons) -> Optional[str]:
    """The ONE `not_evaluated_reason` for a row, or None when it was measured.

    `NOT_EVALUATED_REASON_PRECEDENCE` decides when a row carries more than one
    qualifying token; anything outside `CENSUS_NOT_EVALUATED_REASONS` is ignored
    here (a measured row's accounting reasons are not evaluation reasons).
    """
    present = {r for r in reasons if r in NOT_EVALUATED_REASONS}
    for token in NOT_EVALUATED_REASON_PRECEDENCE:
        if token in present:
            return token
    return None


# ---------------------------------------------------------------------------
# One accounting line
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportRef:
    """-> `$defs.reportRef`. What makes a line resolvable to real content."""

    kind: str
    count_in_report: int
    run_id: str = ""
    report_path: str = ""
    record_ids: tuple = ()

    def artifact(self) -> dict:
        block = {"kind": self.kind, "count_in_report": self.count_in_report}
        if self.run_id:
            block["run_id"] = self.run_id
        if self.report_path:
            block["report_path"] = self.report_path
        if self.record_ids:
            block["record_ids"] = list(self.record_ids)
        return block


@dataclass(frozen=True)
class AccountedLine:
    """-> `$defs.accountedLine`. One claim against one direction of one class.

    R-1 is enforced AT CONSTRUCTION: every reason outside the four exempt tokens
    must carry a `report_ref` whose `count_in_report >= count`. A line with no
    resolvable report content is not accounting, so it cannot be built and then
    validated away -- the emitter never gets the chance to write one.
    """

    reason: str
    count: int
    direction: str
    report_ref: Optional[ReportRef] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.reason not in REASON_TOKENS:
            raise CensusError(
                "accounting reason " + repr(self.reason) + " is outside the "
                "closed 17-token vocabulary -- there is no UNEXPLAINED and no "
                "OTHER token: unexplained is the ABSENCE of a line and cannot "
                "be laundered into one"
            )
        if self.direction not in DIRECTIONS:
            raise CensusError(
                "accounting direction " + repr(self.direction)
                + " must be 'shortfall' or 'surplus'"
            )
        if self.count < 1:
            raise CensusError(
                "an accounting line must claim at least 1 object, got "
                + repr(self.count) + " for reason " + repr(self.reason)
            )
        if self.reason in REASONS_NOT_REQUIRING_REPORT_REF:
            return
        if self.report_ref is None:
            raise CensusError(
                "reason " + repr(self.reason) + " requires a report_ref (R-1): "
                "only STARTER_CONTENT, ABSENT_BY_CONSTRUCTION, "
                "OUT_OF_SCOPE_CLASS and GOVERNED_BY_OTHER_FEATURE account "
                "without one"
            )
        if self.report_ref.count_in_report < self.count:
            raise CensusError(
                "accounting line for " + repr(self.reason) + " claims "
                + str(self.count) + " against a report naming only "
                + str(self.report_ref.count_in_report)
                + " -- a line that outruns its evidence is CENSUS_ERROR, not a "
                "pass (R-1)"
            )

    def artifact(self) -> dict:
        block = {
            "reason": self.reason,
            "count": self.count,
            "direction": self.direction,
        }
        if self.report_ref is not None:
            block["report_ref"] = self.report_ref.artifact()
        if self.detail:
            block["detail"] = self.detail
        return block


# ---------------------------------------------------------------------------
# The arithmetic. One row at a time, on purpose.
# ---------------------------------------------------------------------------


def unmatched_starter(
    starter_baseline_count: Optional[int],
    starter_matched_to_source: Optional[int],
) -> Optional[int]:
    """`starter_baseline_count - starter_matched_to_source`, or None.

    None when either input is unknown: with no baseline there is nothing to
    subtract, and with no run report the matched count cannot be known. Neither
    may be silently read as zero -- a zero baseline is a positive claim that the
    destination shipped empty (5.3), and a zero matched count is the broken run.
    """
    if starter_baseline_count is None:
        return None
    if starter_matched_to_source is None:
        return None
    return starter_baseline_count - starter_matched_to_source


def net_destination_count(
    destination_count_total: Optional[int], unmatched: Optional[int],
) -> Optional[int]:
    """`destination_count_total - unmatched_starter`.

    With `unmatched` None the net IS the total (5.2's `no_baseline` row: "net =
    total; the run cannot pass") -- the number is still reported, and the
    verdict, not the arithmetic, is what refuses to pass.
    """
    if destination_count_total is None:
        return None
    return destination_count_total - (unmatched or 0)


def signed_difference(
    destination_count_net: Optional[int], source_count: Optional[int],
) -> Optional[int]:
    """`destination_count_net - source_count`, the GATE quantity."""
    if destination_count_net is None or source_count is None:
        return None
    return destination_count_net - source_count


def row_verdict_class(
    difference: Optional[int], not_evaluated_reason: Optional[str] = None,
) -> str:
    """MATCHED / SHORTFALL / SURPLUS / NOT_EVALUATED.

    NOT_EVALUATED wins over the sign, and an unmeasurable count is
    NOT_EVALUATED rather than MATCHED: a row that was never measured must not be
    reported as agreeing because two numbers nobody trusts happen to be equal.
    """
    if not_evaluated_reason is not None or difference is None:
        return "NOT_EVALUATED"
    if difference == 0:
        return "MATCHED"
    return "SHORTFALL" if difference < 0 else "SURPLUS"


def accounted_in_direction(lines, direction: str) -> int:
    """`sum(count)` over the lines claiming ONE direction of ONE class.

    R-3: a shortfall line never offsets a surplus, and a line on one class never
    touches another. That rule is expressed as a signature: this function cannot
    be handed two classes' lines because the caller only ever holds one row's.
    """
    return sum(line.count for line in lines if line.direction == direction)


def unexplained_counts(difference: Optional[int], lines) -> tuple:
    """`(unexplained_shortfall, unexplained_surplus)` for one row.

        unexplained_shortfall = max(0, -difference) - sum(shortfall lines)
        unexplained_surplus   = max(0,  difference) - sum(surplus lines)

    Clamped at 0, because a NEGATIVE residue means over-accounting, which is
    R-2's `CENSUS_ERROR` and is detected by `validate_artifact` rather than
    hidden by being folded into an unexplained count.
    """
    if difference is None:
        return (0, 0)
    shortfall = max(0, -difference) - accounted_in_direction(lines, "shortfall")
    surplus = max(0, difference) - accounted_in_direction(lines, "surplus")
    return (max(0, shortfall), max(0, surplus))


def over_accounted_directions(difference: Optional[int], lines) -> tuple:
    """The directions whose accounting EXCEEDS the difference (R-2).

    Separate from `unexplained_counts` on purpose: over-accounting is a
    different failure from under-accounting and must not be clamped away. "The
    census must not be able to explain away more than actually happened."
    """
    if difference is None:
        return ()
    out = []
    if accounted_in_direction(lines, "shortfall") > max(0, -difference):
        out.append("shortfall")
    if accounted_in_direction(lines, "surplus") > max(0, difference):
        out.append("surplus")
    return tuple(out)


# ---------------------------------------------------------------------------
# Match-basis tallies (section 8, invariant 11)
# ---------------------------------------------------------------------------

#: The four tallies that must sum to `source_count`. `enriched` is deliberately
#: ABSENT: it is a SUBSET of `identity + natural_key` (an object can be matched
#: and then gain owned children), so including it would double-count every
#: enriched object and turn a correct run into a tally mismatch.
MATCH_BASIS_SUMMANDS: tuple = (
    "identity", "natural_key", "created_new", "unmatched_reported",
)


@dataclass(frozen=True)
class MatchBasis:
    """-> `$defs.matchBasis`. How each source object was accounted for.

    FR-006 requires every natural-key match to be distinguishable from an
    identity match, and this is where that distinction survives into the gate
    artifact instead of being report-only prose.
    """

    basis_source: str = "run_report"
    identity: Optional[int] = None
    natural_key: Optional[int] = None
    created_new: Optional[int] = None
    enriched: Optional[int] = None
    unmatched_reported: Optional[int] = None
    ambiguous_key_reported: Optional[int] = None

    def __post_init__(self) -> None:
        if self.basis_source not in ("run_report", "unavailable"):
            raise CensusError(
                "MatchBasis.basis_source must be 'run_report' or "
                "'unavailable', got " + repr(self.basis_source)
            )
        if self.basis_source == "unavailable":
            populated = tuple(
                name for name in (
                    "identity", "natural_key", "created_new", "enriched",
                    "unmatched_reported", "ambiguous_key_reported")
                if getattr(self, name) is not None
            )
            if populated:
                raise CensusError(
                    "MatchBasis(basis_source='unavailable') must leave every "
                    "tally null, but these are populated: "
                    + ", ".join(populated) + " -- with no run report the census "
                    "does not know them and must say so (section 8)"
                )

    @property
    def summed(self) -> Optional[int]:
        """`identity + natural_key + created_new + unmatched_reported`, or None
        when any summand is unknown. `enriched` is excluded."""
        values = [getattr(self, name) for name in MATCH_BASIS_SUMMANDS]
        if any(v is None for v in values):
            return None
        return sum(values)

    def sums_to(self, source_count: Optional[int]) -> bool:
        """Invariant 11, on a `required` row whose basis is `run_report`."""
        total = self.summed
        if total is None or source_count is None:
            return True
        return total == source_count

    def artifact(self) -> dict:
        block = {"basis_source": self.basis_source}
        for name in ("identity", "natural_key", "created_new", "enriched",
                     "unmatched_reported", "ambiguous_key_reported"):
            value = getattr(self, name)
            if value is not None:
                block[name] = value
        return block


def match_basis_sum_error(
    object_class: str, basis: Optional[MatchBasis], source_count: Optional[int],
    *, gate_scope: str = "required",
) -> Optional[str]:
    """The invariant-11 failure string for one row, or None when it holds.

    A MISMATCH IS A FAIL, not a note: it means the census's own account of what
    happened to each source object does not add up to the number of source
    objects, so no statement it makes about that class can be trusted.
    """
    if basis is None or gate_scope != "required":
        return None
    if basis.basis_source != "run_report":
        return None
    if basis.sums_to(source_count):
        return None
    return (
        object_class + ": match_basis identity + natural_key + created_new + "
        "unmatched_reported == " + str(basis.summed) + " but source_count is "
        + str(source_count) + " (enriched is a SUBSET of the matches and is "
        "excluded from the sum, section 8)"
    )


# ---------------------------------------------------------------------------
# Emitting one class row
# ---------------------------------------------------------------------------


def class_row_artifact(
    row,
    entry: ClassListEntry,
    *,
    accounted_for=(),
    starter_baseline_count: Optional[int] = None,
    starter_matched_to_source: Optional[int] = None,
    starter_subtraction_basis: Optional[str] = None,
    starter_baseline_source: Optional[str] = None,
    match_basis: Optional[MatchBasis] = None,
    duplicates: Optional[DuplicateReport] = None,
    notes=(),
) -> dict:
    """-> one `$defs.classRow`, from a `models.ClassCensusRow` plus its entry.

    DRIVEN BY THE TRANSLATION TABLE. The internal-to-artifact key mapping is
    read out of `models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS`, where a `None` target
    means internal-only and MUST NOT be emitted; every object in the artifact is
    `additionalProperties: false`, so an extra key is a hard failure and not a
    harmless addition. Nothing here re-derives a name the table already states.
    """
    from .models import (  # noqa: PLC0415
        CLASS_CENSUS_ROW_ARTIFACT_FIELDS,
        CLASS_ROW_REQUIRED_NULLABLE_FIELDS,
    )

    block: dict = {}
    for internal, artifact_key in CLASS_CENSUS_ROW_ARTIFACT_FIELDS.items():
        if artifact_key is None:  # internal-only: never emitted
            continue
        value = getattr(row, internal, None)
        if value is None and internal not in CLASS_ROW_REQUIRED_NULLABLE_FIELDS:
            # An OPTIONAL artifact property the row does not carry -- currently
            # only A1's `owning_feature_system` on an ordinary class. Omitted,
            # never emitted as null: the property is enumerated and every
            # artifact object is `additionalProperties: false`, so a null is a
            # hard validation failure.
            #
            # T099: the guard is on the NAME, not on the value. It used to be
            # on the value alone, with a comment asserting "no REQUIRED mapped
            # field can be None (the row's own invariants reject that)" -- true
            # only because `ClassCensusRow` typed the counts `int`. The moment
            # the model told the truth about a class it could not count, this
            # branch would have DROPPED `source_count`,
            # `destination_count_total` and `difference` from a row where the
            # schema requires all three, turning an honest null into an invalid
            # artifact. The three names are the schema's own required-and-
            # nullable set; anything else still gets omitted.
            continue
        block[artifact_key] = value

    # A1 consistency: when both the row and its class-list entry name an owner
    # they must be the SAME owner. `encode_split_owner` below writes the
    # entry's, so a disagreement would silently relabel a measurement as
    # belonging to the other feature system -- the precise mislabelling A1
    # exists to prevent.
    row_owner = getattr(row, "owning_feature_system", None)
    if (row_owner is not None
            and entry.owning_feature_system is not None
            and row_owner != entry.owning_feature_system):
        raise CensusError(
            "class_row_artifact for " + repr(entry.object_class)
            + ": the row is measured under " + repr(row_owner)
            + " but its class-list entry is " + repr(entry.owning_feature_system)
            + " -- one of the two owners is wrong, and emitting either would "
            "attribute a per-owner count to the wrong feature system (A1)"
        )

    # Derived properties on the row -- read, never recomputed, so the emitter
    # cannot arrive at a second answer.
    block["destination_count_net"] = row.destination_count_net
    block["difference_raw"] = row.difference_raw

    lines = tuple(accounted_for)
    not_evaluated_reason = select_not_evaluated_reason(row.reasons)
    if entry.not_evaluated_reason is not None:
        not_evaluated_reason = select_not_evaluated_reason(
            tuple(row.reasons) + (entry.not_evaluated_reason,))

    block["verdict_class"] = row_verdict_class(
        row.difference, not_evaluated_reason)
    if not_evaluated_reason is not None:
        block["not_evaluated_reason"] = not_evaluated_reason

    # The four required keys `ClassCensusRow` cannot supply (see the task
    # header): two carried from the class-list entry, one an argument, one
    # derived.
    block["gate_scope"] = entry.gate_scope
    block["in_class_list_via"] = entry.in_class_list_via
    if entry.inventory_tables:
        block["inventory_tables"] = list(entry.inventory_tables)
    block["accounted_for"] = [line.artifact() for line in lines]
    shortfall, surplus = unexplained_counts(row.difference, lines)
    if block["verdict_class"] == "NOT_EVALUATED":
        # A row that was not measured explains nothing and owes nothing.
        shortfall, surplus = 0, 0
    block["unexplained_shortfall"] = shortfall
    block["unexplained_surplus"] = surplus

    if starter_baseline_count is not None:
        block["starter_baseline_count"] = starter_baseline_count
    if starter_matched_to_source is not None:
        block["starter_matched_to_source"] = starter_matched_to_source
    if starter_subtraction_basis is not None:
        if starter_subtraction_basis not in SUBTRACTION_BASES:
            raise CensusError(
                "starter_subtraction_basis " + repr(starter_subtraction_basis)
                + " is outside the schema enum " + repr(SUBTRACTION_BASES)
            )
        block["starter_subtraction_basis"] = starter_subtraction_basis
    if starter_baseline_source is not None:
        if starter_baseline_source not in BASELINE_SOURCES:
            raise CensusError(
                "starter_baseline_source " + repr(starter_baseline_source)
                + " is outside the schema enum " + repr(BASELINE_SOURCES)
            )
        block["starter_baseline_source"] = starter_baseline_source
    if match_basis is not None:
        block["match_basis"] = match_basis.artifact()
    if duplicates is not None:
        block["duplicates"] = duplicates.artifact()
    if notes:
        block["notes"] = list(notes)

    # A1: the one seam that decides how a split row carries its owner.
    return encode_split_owner(
        block, entry.object_class, entry.owning_feature_system)


def build_totals(rows) -> dict:
    """-> artifact `totals`. Shortfall and surplus are NEVER summed together.

    `total_shortfall` and `total_surplus` are reported separately and there is
    deliberately no net figure anywhere in this block: a net of zero over
    MoAffixProcess -13 and MoAffixAllomorph +13 would report a run clean while a
    whole class changed kind (section 4).
    """
    required = [r for r in rows if r.get("gate_scope") == "required"]
    diffs = [r["difference"] for r in required if r.get("difference") is not None]
    totals = {
        "classes_reported": len(rows),
        "classes_matched": sum(
            1 for r in rows if r.get("verdict_class") == "MATCHED"),
        "classes_shortfall": sum(
            1 for r in rows if r.get("verdict_class") == "SHORTFALL"),
        "classes_surplus": sum(
            1 for r in rows if r.get("verdict_class") == "SURPLUS"),
        "classes_not_evaluated": sum(
            1 for r in rows if r.get("verdict_class") == "NOT_EVALUATED"),
        "total_shortfall": sum(max(0, -d) for d in diffs),
        "total_surplus": sum(max(0, d) for d in diffs),
        "unexplained_shortfall": sum(
            r.get("unexplained_shortfall", 0) for r in required),
        "unexplained_surplus": sum(
            r.get("unexplained_surplus", 0) for r in required),
        "duplicate_extra_objects": sum(
            r.get("duplicates", {}).get("extra_objects", 0) for r in rows
            if r.get("duplicates", {}).get("roster_admitted")
        ),
        "accounted_shortfall": sum(
            line["count"] for r in rows for line in r.get("accounted_for", ())
            if line.get("direction") == "shortfall"
        ),
        "accounted_surplus": sum(
            line["count"] for r in rows for line in r.get("accounted_for", ())
            if line.get("direction") == "surplus"
        ),
        "advisory_shortfall": sum(
            max(0, -r["difference"]) for r in rows
            if r.get("gate_scope") == "advisory"
            and r.get("difference") is not None
        ),
    }
    return totals


def starter_baseline_artifact(baseline) -> dict:
    """-> artifact `starter_baseline`, driven by the translation table.

    `entries`, `content_hash` and the in-memory `schema_version` are
    internal-only (`STARTER_BASELINE_ARTIFACT_FIELDS` maps them to None);
    `class_count` and `carries_natural_keys` are derived properties, so they
    cannot drift from the entries they describe. `staleness` is NOT emitted from
    the baseline: it is a judgement the gate computes (T020), and finding a
    pre-baked answer here to trust would defeat the point.
    """
    from .models import STARTER_BASELINE_ARTIFACT_FIELDS  # noqa: PLC0415

    block: dict = {}
    for internal, artifact_key in STARTER_BASELINE_ARTIFACT_FIELDS.items():
        if artifact_key is None:
            continue
        value = getattr(baseline, internal)
        if internal == "kind":
            block[artifact_key] = value.value
            continue
        if value in ("", None):
            continue
        block[artifact_key] = value
    if not baseline.is_missing:
        block["class_count"] = baseline.class_count
        block["carries_natural_keys"] = baseline.carries_natural_keys
    return block


def build_artifact(
    census,
    class_list: ClassList,
    rows,
    *,
    projects: dict,
    instrument: dict,
    transfer_run: Optional[dict] = None,
    verdict: str = "",
    exit_code: Optional[int] = None,
    verdict_human_label: str = "",
    errors=(),
    notes=(),
) -> dict:
    """Assemble the whole census artifact from already-emitted class rows.

    Driven by `models.FIDELITY_CENSUS_ARTIFACT_FIELDS`, whose `gate_pass -> None`
    entry is why no `gate_pass` key appears at top level: the artifact is
    `additionalProperties: false` and carries `verdict` + `exit_code`, and the
    gate RECOMPUTES both rather than trusting a stored boolean.

    `verdict` / `exit_code` may be left empty and stamped by T020's
    `stamp_verdict`, which is the only path that computes them from evidence.
    """
    rows = list(rows)
    artifact = {
        "schema_version": census.schema_version,
        "census_id": census.run_id,
        "generated_at": census.taken_at,
        "instrument": dict(instrument),
        "projects": dict(projects),
        "class_list_provenance": class_list_provenance_artifact(class_list),
        "starter_baseline": starter_baseline_artifact(census.baseline),
        "classes": rows,
        "totals": build_totals(rows),
    }
    if transfer_run:
        artifact["transfer_run"] = dict(transfer_run)
    if verdict:
        artifact["verdict"] = verdict
        artifact["exit_code"] = (
            exit_code if exit_code is not None else exit_code_for(verdict)
        )
        artifact["verdict_human_label"] = (
            verdict_human_label or VERDICT_HUMAN_LABELS[verdict]
        )
    if errors:
        artifact["errors"] = [dict(e) for e in errors]
    if notes:
        artifact["notes"] = list(notes)
    return artifact


# ===========================================================================
# T020 -- the GATE: verdicts, exit codes, the published severity ordering, the
#         R-1..R-5 fail triggers, the 11 validator invariants, and the phase
#         predicates of fidelity-census.md 9.1
#
# THREE SEPARATE THINGS, DELIBERATELY NOT CONFLATED (house style, following
# `specs/035-fullsweep-fidelity/contracts/verdict-exit-model.md`): the MACHINE
# TOKEN the artifact stores and tests assert on, the HUMAN LABEL the console
# prints, and the PROCESS EXIT CODE. Storing all three is what stops the console
# and the artifact drifting apart.
#
# THE GATE RECOMPUTES. `recompute_verdict` never reads `artifact["verdict"]` or
# `artifact["exit_code"]`; it derives the verdict from the evidence in the
# document. Otherwise an artifact could buy a pass by simply writing
# `CENSUS_CLEAN` and `0` into itself, and "there is no path on which a missing
# baseline yields exit 0" would be false by construction.
# ===========================================================================

#: Section 9's table. Exactly two verdicts report success: there is deliberately
#: no verdict meaning "loss reported, review advisable, exit success" -- that is
#: the shape of the bug this feature exists to remove (SC-010).
VERDICT_EXIT_CODES: dict = {
    "CENSUS_CLEAN": 0,
    "CENSUS_ACCOUNTED": 0,
    "UNEXPLAINED_SHORTFALL": 1,
    "UNEXPLAINED_SURPLUS": 2,
    "DUPLICATE_IDENTITY": 3,
    "BASELINE_MISSING": 4,
    "BASELINE_STALE": 5,
    "COVERAGE_INCOMPLETE": 6,
    "CENSUS_ERROR": 7,
}

#: What the console prints. Stored rather than derived from the token so the
#: two cannot drift.
VERDICT_HUMAN_LABELS: dict = {
    "CENSUS_CLEAN": "Census clean",
    "CENSUS_ACCOUNTED": "Census accounted",
    "UNEXPLAINED_SHORTFALL": "Unexplained shortfall",
    "UNEXPLAINED_SURPLUS": "Unexplained surplus",
    "DUPLICATE_IDENTITY": "Duplicate identity",
    "BASELINE_MISSING": "Baseline missing",
    "BASELINE_STALE": "Baseline stale",
    "COVERAGE_INCOMPLETE": "Coverage incomplete",
    "CENSUS_ERROR": "Census error",
}

#: The PUBLISHED severity ordering, most severe FIRST. It is NOT the exit-code
#: integer and MUST NOT be derived from it: BASELINE_MISSING (exit 4) outranks
#: DUPLICATE_IDENTITY (exit 3), so sorting by the integer gives a different and
#: wrong sequence. A missing baseline outranks a duplicate because a census with
#: no baseline cannot be trusted to have found the duplicates in the first place.
VERDICT_SEVERITY_ORDER: tuple = (
    "CENSUS_ERROR",
    "COVERAGE_INCOMPLETE",
    "BASELINE_MISSING",
    "BASELINE_STALE",
    "DUPLICATE_IDENTITY",
    "UNEXPLAINED_SHORTFALL",
    "UNEXPLAINED_SURPLUS",
    "CENSUS_ACCOUNTED",
    "CENSUS_CLEAN",
)

#: PASS is exactly these two, and they are exactly the exit-0 verdicts.
PASSING_VERDICTS: frozenset = frozenset({"CENSUS_CLEAN", "CENSUS_ACCOUNTED"})

# ---------------------------------------------------------------------------
# 5.2's GROSS-BASIS VERDICT CAP (T023a)
#
# `fidelity-census.md:251`, the `starter_subtraction_basis` table:
#
#   | `baseline_gross` | baseline present, run report absent |
#   | `starter_matched_to_source: null`; gross subtraction used; EVERY ROW IS
#     ADVISORY FOR SHORTFALL PURPOSES and THE RUN VERDICT CANNOT EXCEED
#     `CENSUS_ACCOUNTED` |
#
# and `census-artifact.schema.json:408` says the same in one clause:
# "baseline_gross: net = total - baseline, used when no run report is
# available; caps the run verdict at CENSUS_ACCOUNTED."
#
# WHY THIS IS A CORRECTNESS FIX AND NOT A LENIENCY. On the gross basis the
# subtrahend is the WHOLE baseline count, not the unmatched part of it, so a
# starter object that the transfer correctly MATCHED to a source object is
# subtracted anyway -- once as a starter object and once as the source object
# it now stands in for. 5.2's own worked example: source 41, destination 43,
# starter 23, gross 43 - 23 = 20, `difference` -21. That is a 21-object
# shortfall reported on a run that lost nothing. The uncapped verdict is not a
# strict reading of weak evidence; it is a FALSE STATEMENT about a correct
# transfer, and `unexplained_shortfall` on such a row is arithmetic noise
# rather than evidence of loss.
#
# AND IT IS THE NORMAL PATH, not a degenerate one. `census-artifact.schema.json:337`
# on `carries_natural_keys`: "a count-only baseline forces
# `starter_subtraction_basis` 'baseline_gross'". A whole-project baseline
# CANNOT carry a natural key for every starter object -- measured on a blank
# FieldWorks project, 36 classes hold objects and 11 of them (CmDomainQ 7938,
# StTxtPara 86, PhCode 25, CmRow 30, CmCell 29, CmAgentEvaluation 8,
# DsDiscourseData, LangProject, MoMorphData, PhPhonData, StText 12) carry no
# name at all. So `carries_natural_keys` is false in practice and the gross
# basis is what a real starter baseline yields. An unimplemented cap would
# therefore make EVERY real run lie, not an edge case.
#
# THE CAP IS A CEILING, NOT A FLOOR, AND IT IS NOT A PASS.
# * Ceiling: it removes exactly `UNEXPLAINED_SHORTFALL` and
#   `UNEXPLAINED_SURPLUS`. Every verdict ABOVE `CENSUS_ACCOUNTED` in the
#   published ordering -- `CENSUS_ERROR`, `COVERAGE_INCOMPLETE`,
#   `BASELINE_MISSING`, `BASELINE_STALE`, `DUPLICATE_IDENTITY` -- is untouched
#   and still wins, because `most_severe_verdict` still chooses over the full
#   list. 5.3's "there is no path on which a missing baseline yields exit 0"
#   survives verbatim: the cap never ADDS a verdict less severe than
#   `CENSUS_ACCOUNTED`, so it can never displace exit 4.
# * Not `CENSUS_CLEAN`: a suppressed shortfall makes the run ACCOUNTED, never
#   CLEAN. Clean means nothing needed explaining; here something did, and what
#   explains it is the basis rather than a report line. Capping to
#   `CENSUS_CLEAN` would let a real difference read as "nothing happened".
# * Only the RUN VERDICT. `row_passes` and the section 9.1 phase predicates are
#   deliberately NOT relaxed: a phase declaring itself done needs trustworthy
#   evidence, and gross-basis arithmetic is by construction not that. So a
#   gross-basis run exits 0 while `census gate --phase N` still refuses.
#
# GRANULARITY. `starter_subtraction_basis` lives on the ROW
# (`census-artifact.schema.json:405`, `$defs.classRow`), while the cap sentence
# speaks of "the RUN verdict". The two agree in practice because the condition
# is a run-wide one -- `census-artifact.schema.json:139`: an absent
# `transfer_run.report_path` "forces starter_subtraction_basis 'baseline_gross'
# on EVERY row". The contract is silent on a mixed artifact, so the
# CONSERVATIVE reading is implemented: the suppression is applied PER ROW, so a
# `baseline_matched` row -- whose shortfall IS trustworthy evidence -- still
# raises `UNEXPLAINED_SHORTFALL` and still fails the run. One gross-basis row
# therefore caps only its own contribution, never the whole artifact. In the
# uniform case the contract describes, every row is gross and the two readings
# coincide exactly.
#
# T110: A ZERO STARTER BASELINE IS NOT A GROSS BASIS AT ALL. Everything above
# is an argument about ONE quantity -- the starter objects the transfer
# correctly matched, which gross subtraction removes twice. Where that quantity
# is provably zero the argument has no subject. A row whose baseline document
# says 0 for its class subtracts nothing (`starter_excluded` 0,
# `destination_count_net == destination_count_total`), and the two bases
# compute the same integer: `total - 0` on the gross basis, `total - (0 - 0)`
# on the matched one. 5.2's own worked example needs a baseline of 23 to
# manufacture its phantom 21; over a baseline of 0 there is no phantom to
# manufacture and the difference is the loss. Such a row is therefore EXACT,
# and `is_gross_basis_row` returns False for it, so the cap, the notes and the
# exit code all stop excusing it at once -- one predicate, per T024b, rather
# than three call sites that could drift.
#
# WHAT THAT WAS COSTING. Measured on T078's three artifacts: 13 of 19 / 19 of
# 27 / 15 of 23 required non-MATCHED rows had a zero baseline from a real
# `baseline_document`, and 2602 / 57,955 / 8849 objects were being announced as
# "ADVISORY, not evidence" on arithmetic that could not have been wrong in the
# excusing direction. Worst single row: mbugwe `CmFile` 2173 -> 0. It changed
# no verdict on those three (`DUPLICATE_IDENTITY` outranks the cap on all
# three), which is precisely why it survived -- on a duplicate-free artifact a
# run that lost 69,406 objects would have read `CENSUS_ACCOUNTED`.
#
# AND ABSENT IS STILL CAPPED. The exemption is granted only against a baseline
# document that was READ and said zero (`starter_baseline_source` ==
# `BASELINE_SOURCE_DOCUMENT`), never against a missing count. An
# `absent_from_baseline` row also subtracts 0, but for the opposite reason: not
# because the starter project held none of that class, but because nobody
# counted. Its true baseline may be any number, so its arithmetic is not exact
# and the cap keeps applying. See `is_gross_basis_row`.
# ---------------------------------------------------------------------------

#: The one basis on which a row's shortfall/surplus is arithmetic noise rather
#: than evidence. Spelled as a named constant because the string appears in
#: `SUBTRACTION_BASES`, in the validator's invariant 4, and here, and a typo in
#: any one of the three would silently disable the cap.
GROSS_SUBTRACTION_BASIS: str = "baseline_gross"

#: The ceiling 5.2 imposes. Deliberately NOT `CENSUS_CLEAN`: see above.
GROSS_BASIS_VERDICT_CAP: str = "CENSUS_ACCOUNTED"

#: The two verdicts the cap suppresses, and the only two. Everything more
#: severe than `GROSS_BASIS_VERDICT_CAP` is untouched.
GROSS_BASIS_CAPPED_VERDICTS: frozenset = frozenset({
    "UNEXPLAINED_SHORTFALL", "UNEXPLAINED_SURPLUS",
})

#: `$defs.starterBaseline.staleness.verdict`.
STALENESS_VERDICTS: tuple = ("current", "stale", "unknown", "not_applicable")

#: The reason that admits a duplicate group as ACCOUNTED. A duplicate is always
#: a defect; it is admissible as accounting only while a report line names it.
DUPLICATE_ACCOUNTING_REASON = "DUPLICATE_CREATED"

#: P5's two admissible reasons (9.1). `DUPLICATE_CREATED` is real accounting but
#: is deliberately NOT phase-5 done: it is exactly the reason a phase's exit
#: criteria should drive to zero.
PHASE_5_ADMISSIBLE_REASONS: frozenset = frozenset({
    "GOVERNED_BY_OTHER_FEATURE", "NO_CREATE_PATH",
})

_CENSUS_ID_PATTERN = re.compile(r"^CENSUS-[0-9]{8}-[0-9]{6}$")
_TRANSFER_RUN_ID_PATTERN = re.compile(r"^GT-[0-9]{8}-[0-9]{6}$")


def reason_requires_report_ref(reason: str) -> bool:
    """True unless the reason is one of the four exempt tokens (R-1).

    An unknown token RAISES rather than returning False: "a reason the census
    cannot classify is CENSUS_ERROR, never a free-text pass", so absorbing an
    unrecognised token as exempt is the one answer that must not be possible.
    """
    if reason not in REASON_TOKENS:
        raise CensusError(
            "reason " + repr(reason) + " is outside the closed 17-token "
            "vocabulary -- there is no UNEXPLAINED and no OTHER token, and an "
            "unclassifiable reason is CENSUS_ERROR rather than an 18th token"
        )
    return reason not in REASONS_NOT_REQUIRING_REPORT_REF


def exit_code_for(verdict: str) -> int:
    """The section-9 exit code for a verdict token. Raises on an unknown one."""
    try:
        return VERDICT_EXIT_CODES[verdict]
    except KeyError:
        raise CensusError(
            "verdict " + repr(verdict) + " is not one of the nine tokens "
            + repr(tuple(VERDICT_EXIT_CODES))
        ) from None


def is_passing_verdict(verdict: str) -> bool:
    """True for the two success verdicts. Raises on an unknown token."""
    exit_code_for(verdict)  # validates the token
    return verdict in PASSING_VERDICTS


def most_severe_verdict(verdicts) -> str:
    """The most severe of several verdicts, by the PUBLISHED ordering."""
    tokens = tuple(verdicts)
    if not tokens:
        raise CensusError(
            "most_severe_verdict needs at least one verdict token"
        )
    for token in tokens:
        exit_code_for(token)  # validates every token before choosing
    return min(tokens, key=lambda t: VERDICT_SEVERITY_ORDER.index(t))


# ---------------------------------------------------------------------------
# Reading the artifact -- small helpers, so every rule below reads the same way
# ---------------------------------------------------------------------------


def _rows(artifact) -> list:
    rows = artifact.get("classes")
    return list(rows) if isinstance(rows, list) else []


def _row_label(row) -> str:
    return str(row.get("class", "(unnamed class)"))


def _is_required(row) -> bool:
    return row.get("gate_scope") == "required"


def _lines(row) -> list:
    lines = row.get("accounted_for")
    return list(lines) if isinstance(lines, list) else []


def _line_sum(row, direction: str) -> int:
    return sum(
        int(line.get("count", 0)) for line in _lines(row)
        if line.get("direction") == direction
    )


def _duplicates(row) -> dict:
    block = row.get("duplicates")
    return block if isinstance(block, dict) else {}


def _projects(artifact) -> list:
    projects = artifact.get("projects")
    if not isinstance(projects, dict):
        return []
    return [
        (role, block) for role, block in projects.items()
        if isinstance(block, dict)
    ]


def _int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def duplicates_unaccounted(row) -> int:
    """Unaccounted `duplicates.extra_objects` on ONE row.

    A duplicate group is accounted only while a `DUPLICATE_CREATED` line names
    it, which is why the count is netted against those lines and nothing else.
    Roster admission is what makes the residue able to FAIL the gate: a
    duplicate name on an unadmitted class is advisory, because homographs are
    legitimate content (section 6).
    """
    block = _duplicates(row)
    if not block.get("roster_admitted"):
        return 0
    extra = int(block.get("extra_objects", 0) or 0)
    claimed = sum(
        int(line.get("count", 0)) for line in _lines(row)
        if line.get("reason") == DUPLICATE_ACCOUNTING_REASON
    )
    return max(0, extra - claimed)


# ---------------------------------------------------------------------------
# Baseline staleness -- a JUDGEMENT the gate computes (5.3)
# ---------------------------------------------------------------------------


def baseline_staleness(artifact) -> Optional[str]:
    """`"stale"` / `"current"` / `None` (nothing to judge).

    Three shapes count as stale, all three tested: an explicit `staleness`
    marker, a recorded `flex_version` differing from the running FieldWorks
    version, and a destination `data_model_version` EXCEEDING the baseline's.
    FLEx changes what a new project ships between versions, so an old capture
    silently mis-subtracts.
    """
    baseline = artifact.get("starter_baseline")
    if not isinstance(baseline, dict) or baseline.get("kind") == "none":
        return None
    marker = baseline.get("staleness")
    if isinstance(marker, dict) and marker.get("verdict") == "stale":
        return "stale"
    instrument = artifact.get("instrument") or {}
    running = instrument.get("flex_version")
    recorded = baseline.get("flex_version")
    if running and recorded and running != recorded:
        return "stale"
    projects = artifact.get("projects") or {}
    destination = projects.get("destination") or {}
    dest_version = _int_or_none(destination.get("data_model_version"))
    base_version = _int_or_none(baseline.get("data_model_version"))
    if dest_version is not None and base_version is not None:
        if dest_version > base_version:
            return "stale"
    return "current"


def baseline_misdeclared(artifact) -> bool:
    """True for a `starter_capture` baseline used against a destination the
    operator did not declare freshly created.

    The spec's edge case "destination content FLEx ships but the linguist has
    since edited" is handled the only honest way: any destination that is not
    demonstrably fresh requires a `pre_transfer_census`. An ABSENT declaration
    is not a permissive default -- an undeclared destination is undeclared.
    """
    baseline = artifact.get("starter_baseline")
    if not isinstance(baseline, dict):
        return False
    if baseline.get("kind") != "starter_capture":
        return False
    projects = artifact.get("projects") or {}
    destination = projects.get("destination") or {}
    return destination.get("declared_freshly_created") is not True


#: The three counted fields a row may carry as `null`. `destination_count_net`
#: is deliberately NOT here: it is derived from `destination_count_total`, so a
#: null net with an integer total is invariant 3's business, not invariant 12's.
NULLABLE_COUNT_FIELDS: tuple = (
    "source_count", "destination_count_total", "difference",
)


def uncorroborated_null_rows(artifact) -> tuple:
    """Invariant 12: gate-required rows nulled without corroboration.

    Returns `((label, nulled_field_names), ...)`, empty when every null count on
    a required row is either named by an `errors[]` entry or carries a
    `not_evaluated_reason`.

    WHY THIS IS AN INVARIANT AND NOT A ROW FAILURE. Every step of the path it
    closes is individually right, which is why nothing caught it: a null
    `difference` reads `NOT_EVALUATED` (an unmeasured row must not report
    MATCHED); `row_passes` returns True on NOT_EVALUATED before reading any
    count (a row nobody measured proves nothing); `unexplained_counts(None, ..)`
    is `(0, 0)` so R-2's over-accounting check is skipped (there is no
    difference to over-account against); and invariants 3, 4 and 11 are all
    guarded `None not in (...)` (they cannot recompute what is not there).
    COMPOSED, they mean nulling a class retires its shortfall without measuring
    anything. The refusal therefore belongs where the CORROBORATION is.

    THE FIX NOT TO MAKE is failing `row_passes` on a null count: the
    `excluded_not_measurable` rows every artifact carries -- `MoForm` and
    `MoMorphSynAnalysis`, abstract LCM bases with no factory -- are legitimately
    null, and they are exempt here because they are `advisory`, never because a
    null is tolerated on a row that could fail a gate.

    Corroboration by `errors[]` buys nothing: a non-empty `errors[]` is
    CENSUS_ERROR on its own, so the admissible shape still exits 7.

    The producer states the same prohibition earlier and slightly TIGHTER --
    `census_cli._refuse_uncorroborated_nulls` accepts only the two shapes that
    CLI can emit and cannot mint a `not_evaluated_reason` for a required row.
    A tighter producer inside a looser format is the safe direction.
    """
    named = {
        entry.get("class")
        for entry in (artifact.get("errors") or [])
        if isinstance(entry, dict)
    }
    offenders = []
    for row in _rows(artifact):
        if not _is_required(row):
            continue
        nulled = tuple(
            key for key in NULLABLE_COUNT_FIELDS if row.get(key) is None
        )
        if not nulled:
            continue
        if row.get("class") in named:
            continue
        if row.get("not_evaluated_reason") is not None:
            continue
        offenders.append((_row_label(row), nulled))
    return tuple(offenders)


# ---------------------------------------------------------------------------
# The 12 validator invariants (section 11) plus the R-1..R-5 fail triggers
# ---------------------------------------------------------------------------


def validate_artifact(artifact) -> tuple:
    """Every section-11 invariant and R-1/R-2 violation, as failure strings.

    Empty when the artifact is internally consistent. Each string NAMES the
    class or project it failed on, because a gate failure a reader cannot
    localise is a gate failure they will ignore.

    Unlike `recompute_verdict`, this DOES read the stored `verdict` and
    `exit_code`: invariant 8 is precisely the claim that the stored pair agrees
    with the recomputed one, which is how a forged verdict is caught.
    """
    failures: list = []
    rows = _rows(artifact)

    # -- 1. exactly one row per required class -----------------------------
    provenance = artifact.get("class_list_provenance") or {}
    required_count = _int_or_none(provenance.get("required_class_count"))
    if required_count is not None and required_count != len(rows):
        failures.append(
            "invariant 1: len(classes) is " + str(len(rows))
            + " but class_list_provenance.required_class_count is "
            + str(required_count)
            + " -- a class with no instances is a NOT_EVALUATED row, never an "
            "omitted one (CP-2)"
        )
    seen = set()
    for row in rows:
        # Keyed on (class, owner), not on class alone: Amendment A1 splits one
        # class into one row PER OWNING FEATURE SYSTEM, and both halves emit the
        # same plain class name with the owner in `owning_feature_system`. Two
        # rows for one class are a defect; two rows for one class-and-owner are
        # the same row twice, which is the thing this invariant is for.
        key = (_row_label(row), row.get("owning_feature_system"))
        if key in seen:
            owner = key[1]
            failures.append(
                "invariant 1: two rows for class " + key[0]
                + (" under " + str(owner) if owner else "")
                + " -- exactly one row per class"
            )
        seen.add(key)

    derivation = provenance.get("derivation_check") or {}
    if derivation.get("performed") is not True:
        failures.append(
            "CP-1: class_list_provenance.derivation_check.performed is not "
            "true -- a census that skipped the derivation cannot make a "
            "coverage claim"
        )
    if derivation.get("result") not in (None, "match"):
        named = tuple(derivation.get("in_inventory_not_in_floor", ())) + tuple(
            derivation.get("in_floor_not_in_inventory", ()))
        failures.append(
            "CP-1: derivation_check.result is "
            + repr(derivation.get("result")) + ", naming "
            + (", ".join(str(n) for n in named) or "(no classes)")
        )

    for row in rows:
        label = _row_label(row)
        source = _int_or_none(row.get("source_count"))
        total = _int_or_none(row.get("destination_count_total"))
        net = _int_or_none(row.get("destination_count_net"))
        difference = _int_or_none(row.get("difference"))
        difference_raw = _int_or_none(row.get("difference_raw"))
        lines = _lines(row)

        # -- 3. both stored differences must follow from the counts ---------
        if None not in (net, source) and difference is not None:
            if difference != net - source:
                failures.append(
                    "invariant 3: " + label + " stores difference "
                    + str(difference) + " but destination_count_net - "
                    "source_count is " + str(net - source)
                )
        if None not in (total, source) and difference_raw is not None:
            if difference_raw != total - source:
                failures.append(
                    "invariant 3: " + label + " stores difference_raw "
                    + str(difference_raw) + " but destination_count_total - "
                    "source_count is " + str(total - source)
                )

        # -- 4. the matched subtraction, when that is the declared basis ----
        if row.get("starter_subtraction_basis") == "baseline_matched":
            baseline_count = _int_or_none(row.get("starter_baseline_count"))
            matched = _int_or_none(row.get("starter_matched_to_source"))
            if None not in (total, net, baseline_count, matched):
                expected = total - (baseline_count - matched)
                if net != expected:
                    failures.append(
                        "invariant 4: " + label + " declares "
                        "starter_subtraction_basis 'baseline_matched' but "
                        "destination_count_net " + str(net) + " != "
                        + str(total) + " - (" + str(baseline_count) + " - "
                        + str(matched) + ") = " + str(expected)
                    )

        # -- 5 / R-1. every line resolves to real report content -----------
        for line in lines:
            reason = line.get("reason")
            count = int(line.get("count", 0) or 0)
            if reason not in REASON_TOKENS:
                failures.append(
                    "UNCLASSIFIABLE_REASON: " + label + " carries reason "
                    + repr(reason) + ", outside the closed 17-token vocabulary "
                    "-- unexplained is the ABSENCE of a line and cannot be "
                    "laundered into one"
                )
                continue
            if not reason_requires_report_ref(reason):
                continue
            ref = line.get("report_ref")
            if not isinstance(ref, dict):
                failures.append(
                    "invariant 5 (R-1): " + label + " line " + reason
                    + " carries no report_ref; only STARTER_CONTENT, "
                    "ABSENT_BY_CONSTRUCTION, OUT_OF_SCOPE_CLASS and "
                    "GOVERNED_BY_OTHER_FEATURE account without one"
                )
                continue
            in_report = _int_or_none(ref.get("count_in_report"))
            if in_report is None or in_report < count:
                failures.append(
                    "invariant 5 (R-1): " + label + " line " + reason
                    + " claims " + str(count) + " against a report naming "
                    + str(in_report) + " -- a line that outruns its evidence "
                    "is CENSUS_ERROR, not a pass"
                )

        # -- 6 / R-2. accounting never exceeds the difference ---------------
        if difference is not None:
            for direction, room in (
                    ("shortfall", max(0, -difference)),
                    ("surplus", max(0, difference))):
                claimed = _line_sum(row, direction)
                if claimed > room:
                    failures.append(
                        "invariant 6 (R-2): " + label + " accounts "
                        + str(claimed) + " " + direction
                        + " against a difference of " + str(difference)
                        + " -- the census must not explain away more than "
                        "actually happened"
                    )

        # -- R-5 / section 7. the stored unexplained counts must be the
        # formula's, so a row cannot understate what it failed to explain.
        if difference is not None and row.get("verdict_class") != "NOT_EVALUATED":
            expected_short, expected_surplus = (
                max(0, -difference) - _line_sum(row, "shortfall"),
                max(0, difference) - _line_sum(row, "surplus"),
            )
            for key, expected in (
                    ("unexplained_shortfall", max(0, expected_short)),
                    ("unexplained_surplus", max(0, expected_surplus))):
                stored = _int_or_none(row.get(key))
                if stored is not None and stored != expected:
                    failures.append(
                        "section 7 (R-5): " + label + " stores " + key + " "
                        + str(stored) + " but max(0, difference) less its "
                        "accounted lines is " + str(expected)
                        + " -- absence of an accounting line is not an excuse"
                    )

        # -- 2. no list is ever truncated ----------------------------------
        dup = _duplicates(row)
        groups = _int_or_none(dup.get("groups")) or 0
        examples = dup.get("examples")
        if groups > 0 and (not isinstance(examples, list) or len(examples) < groups):
            failures.append(
                "invariant 2: " + label + " reports " + str(groups)
                + " duplicate groups but carries "
                + str(len(examples) if isinstance(examples, list) else 0)
                + " examples -- duplicates.examples is never truncated; "
                "truncation is legal only in the console summary"
            )

        # -- 11. the match-basis tallies -----------------------------------
        basis = row.get("match_basis")
        if isinstance(basis, dict) and basis.get("basis_source") == "run_report":
            if _is_required(row):
                summands = [
                    _int_or_none(basis.get(name))
                    for name in MATCH_BASIS_SUMMANDS
                ]
                if all(v is not None for v in summands) and source is not None:
                    if sum(summands) != source:
                        failures.append(
                            "invariant 11: " + label + " match_basis identity + "
                            "natural_key + created_new + unmatched_reported == "
                            + str(sum(summands)) + " but source_count is "
                            + str(source) + " (enriched is a SUBSET of the "
                            "matches and is excluded from the sum)"
                        )

    # -- 7. read-only, and nothing written --------------------------------
    for role, block in _projects(artifact):
        if block.get("opened_read_only") is not True:
            failures.append(
                "invariant 7: projects." + role + ".opened_read_only is not "
                "true -- the census is READ-ONLY without exception"
            )
        before = block.get("fwdata_sha256_before")
        after = block.get("fwdata_sha256_after")
        if before != after:
            failures.append(
                "invariant 7: projects." + role + " ("
                + str(block.get("name", "?")) + ") fwdata_sha256 changed under "
                "the census: " + str(before)[:12] + "... -> "
                + str(after)[:12] + "..."
            )

    # -- 10. the two id formats are deliberately distinct ------------------
    census_id = artifact.get("census_id")
    if not isinstance(census_id, str) or not _CENSUS_ID_PATTERN.match(census_id):
        failures.append(
            "invariant 10: census_id " + repr(census_id) + " does not match "
            "^CENSUS-\\d{8}-\\d{6}$ (a transfer run id is GT-..., and the two "
            "prefixes are deliberately distinct)"
        )
    transfer_run = artifact.get("transfer_run")
    if isinstance(transfer_run, dict):
        run_id = transfer_run.get("run_id")
        if not isinstance(run_id, str) or not _TRANSFER_RUN_ID_PATTERN.match(run_id):
            failures.append(
                "invariant 10: transfer_run.run_id " + repr(run_id)
                + " does not match ^GT-\\d{8}-\\d{6}$"
            )

    # -- 12. a required row nulled with nothing to corroborate it ----------
    for label, nulled in uncorroborated_null_rows(artifact):
        failures.append(
            "UNCORROBORATED_NULL: " + label + " is gate_scope 'required' and "
            "carries a null " + ", ".join(nulled) + " with no errors[] entry "
            "naming the class and no not_evaluated_reason -- a null difference "
            "reads NOT_EVALUATED and NOT_EVALUATED passes the section 6 row "
            "test, so an uncorroborated null retires the class's shortfall "
            "without measuring it (invariant 12)"
        )

    # -- the baseline's own two hard failures ------------------------------
    if baseline_misdeclared(artifact):
        failures.append(
            "BASELINE_KIND_MISDECLARED: a starter_capture baseline is used "
            "against a destination that is not declared freshly created -- an "
            "edited starter inventory is not disposable, so a destination that "
            "is not demonstrably fresh requires a pre_transfer_census (5.3)"
        )

    # -- totals must be the rows' own arithmetic ---------------------------
    stored_totals = artifact.get("totals")
    if isinstance(stored_totals, dict) and rows:
        recomputed = build_totals(rows)
        for key in (
                "classes_reported", "classes_matched", "classes_shortfall",
                "classes_surplus", "classes_not_evaluated", "total_shortfall",
                "total_surplus", "unexplained_shortfall", "unexplained_surplus",
                "duplicate_extra_objects"):
            stored = _int_or_none(stored_totals.get(key))
            if stored is not None and stored != recomputed[key]:
                failures.append(
                    "totals." + key + " is " + str(stored) + " but the rows "
                    "give " + str(recomputed[key])
                    + " -- every verdict-bearing datum must be recomputable "
                    "from this artifact (invariant 9)"
                )

    # -- 8. the stored verdict must be the recomputed one ------------------
    stored_verdict = artifact.get("verdict")
    computed = recompute_verdict(artifact)
    if stored_verdict != computed:
        failures.append(
            "invariant 8: the artifact stores verdict " + repr(stored_verdict)
            + " but its own evidence gives " + repr(computed)
            + " -- verdict is the most severe applicable token by the section 9 "
            "ordering, and the gate recomputes it rather than trusting it"
        )
    stored_exit = artifact.get("exit_code")
    if isinstance(stored_verdict, str) and stored_verdict in VERDICT_EXIT_CODES:
        if stored_exit != VERDICT_EXIT_CODES[stored_verdict]:
            failures.append(
                "invariant 8: verdict " + stored_verdict + " carries exit_code "
                + repr(stored_exit) + ", not the section 9 table's "
                + str(VERDICT_EXIT_CODES[stored_verdict])
            )
        label = artifact.get("verdict_human_label")
        if label is not None and label != VERDICT_HUMAN_LABELS[stored_verdict]:
            failures.append(
                "invariant 8: verdict " + stored_verdict + " carries "
                "verdict_human_label " + repr(label) + ", not "
                + repr(VERDICT_HUMAN_LABELS[stored_verdict])
            )
    elif stored_verdict is not None:
        failures.append(
            "invariant 8: verdict " + repr(stored_verdict) + " is not one of "
            "the nine section 9 tokens"
        )

    return tuple(failures)


# ---------------------------------------------------------------------------
# The verdict, recomputed from evidence
# ---------------------------------------------------------------------------


def is_gross_basis_row(row) -> bool:
    """True when this row's starter subtraction was GROSS *and over something*.

    The single predicate the cap turns on, so `recompute_verdict` and the note
    that makes the cap visible cannot disagree about which rows are capped.
    A row that declares no basis at all is NOT capped: the cap is a claim the
    artifact has to make about itself, never a default.

    T110 EXTENDS THAT PRINCIPLE ONE STEP, in the excusing direction. The cap
    exists because gross subtraction "also subtracts the starter objects the
    transfer correctly matched" (see the 5.2 block above). On a row whose
    baseline count is a MEASURED ZERO there are no such objects to subtract
    twice: `starter_excluded` is 0, `destination_count_net ==
    destination_count_total`, and the gross and matched bases compute the
    IDENTICAL number (`total - 0` against `total - (0 - 0)`). Nothing is
    advisory about arithmetic that does not depend on which basis you name, so
    such a row is NOT a gross-basis row for capping purposes -- its shortfall
    is evidence and must fail the run. `census_cli`'s T048d comment already
    reasons this way ("A class the baseline counts as ZERO cannot carry a
    phantom shortfall: gross subtraction subtracts nothing from it, so the two
    bases already agree") but spent it only on skipping the identity audit.

    THE ROW'S DECLARED BASIS STRING IS NOT TOUCHED, here or upstream. The
    artifact's own arithmetic has to stay reproducible from what it published,
    the validator's invariant 4 and `SUBTRACTION_BASES` are written against
    that vocabulary, and `baseline_gross` remains the literally true
    description of the subtraction performed. What changes is only whether that
    subtraction was capable of the over-subtraction the cap compensates for.

    ABSENT IS NOT ZERO, and the corroboration is what keeps them apart. The
    exemption requires BOTH a `starter_baseline_count` that is an integer 0 AND
    `starter_baseline_source` == `BASELINE_SOURCE_DOCUMENT` -- i.e. a baseline
    document that was read and that said zero for this class. A row with no
    count key, or a null one, or one whose source is `absent_from_baseline`
    (the A1 split halves, and any class the baseline never mentions) stays
    CAPPED: its true starter population is unknown, and reading that absence as
    a measured zero is exactly the error `unmatched_starter` refuses to make.
    Requiring the positive corroboration rather than inferring it from key
    presence keeps the docstring's first rule intact in both directions: the
    cap is a claim the artifact makes about itself, and so is the exemption.
    """
    if row.get("starter_subtraction_basis") != GROSS_SUBTRACTION_BASIS:
        return False
    if (row.get("starter_baseline_source") == BASELINE_SOURCE_DOCUMENT
            and _int_or_none(row.get("starter_baseline_count")) == 0):
        return False
    return True


def gross_basis_suppressions(artifact, classes=None) -> tuple:
    """Every shortfall/surplus 5.2's cap turns from a failure into accounting.

    Each entry is `(class_label, direction, count)`. Pure: derived from the
    rows' own basis, baseline and unexplained tallies -- every input is a field
    of the row `is_gross_basis_row` reads -- and, like the rest of the gate,
    never from `artifact["verdict"]`.

    Empty means the cap changed nothing, which is the ordinary case on a
    `baseline_matched` run. Non-empty is what `gross_basis_cap_notes` renders,
    and what stops a capped `CENSUS_ACCOUNTED` from reading as `CENSUS_CLEAN`.

    `classes` BOUNDS the answer to the rows the caller named, for the one
    question that is legitimately phase-scoped -- see
    `phase_scoped_suppressions`, which is the only caller that passes it. The
    default is unbounded, so the cap, its notes and `census_cli`'s capped-pass
    exit code all keep reading the same project-wide answer they always did;
    T024b's comment is explicit that those three must not be able to disagree
    about which rows are capped, and one implementation is how that is kept
    true. A bound is tested against the row's LABEL *and* its bare `class`, so
    an Amendment A1 split row -- whose label carries the owning feature system
    -- is still recognised by a caller that named the plain class name.
    """
    found = []
    for row in _rows(artifact):
        if not _is_required(row) or not is_gross_basis_row(row):
            continue
        if (classes is not None
                and _row_label(row) not in classes
                and row.get("class") not in classes):
            continue
        for direction, key in (
                ("shortfall", "unexplained_shortfall"),
                ("surplus", "unexplained_surplus")):
            count = int(row.get(key, 0) or 0)
            if count > 0:
                found.append((_row_label(row), direction, count))
    return tuple(found)


def gross_basis_cap_notes(artifact) -> tuple:
    """The human sentences that make the cap VISIBLE rather than silent.

    Without these, `CENSUS_ACCOUNTED` on a gross-basis run is indistinguishable
    from `CENSUS_ACCOUNTED` on a run where every difference was explained by a
    report line -- and a reader would take "accounted" to mean "no shortfall
    found". These say a shortfall WAS found, how big, on which class, and that
    what accounts for it is the subtraction basis rather than evidence of
    correctness.

    They live in the artifact's `notes` array (schema top level, and
    `$defs.classRow.notes` per row), which is the only string-array the
    `additionalProperties: false` document offers -- there is no
    `verdict_capped` / `verdict_floor` property to add without a breaking
    schema change, and inventing one is forbidden. Notes are explicitly NOT
    load-bearing (invariant 9: no verdict may depend on a note), and this cap
    does not depend on one: it reads the counted fields `is_gross_basis_row`
    reads. The note reports the decision; it never makes it.
    """
    suppressions = gross_basis_suppressions(artifact)
    if not suppressions:
        return ()
    one = len(suppressions) == 1
    notes = [
        "[WARN] verdict CAPPED at " + GROSS_BASIS_VERDICT_CAP
        + " by fidelity-census.md 5.2: " + str(len(suppressions))
        + " unexplained tall" + ("y " if one else "ies ")
        + "on rows whose starter_subtraction_basis is "
        + GROSS_SUBTRACTION_BASIS + (" is" if one else " are")
        + " ADVISORY, not evidence -- gross "
        "subtraction also subtracts the starter objects the transfer correctly "
        "matched, so it reports a shortfall on a correct run. This is NOT a "
        "statement that nothing was lost; supply the run report to get a "
        "baseline_matched basis and a trustworthy answer."
    ]
    for label, direction, count in suppressions:
        notes.append(
            "[WARN]   " + label + ": unexplained_" + direction + " "
            + str(count) + " suppressed (basis " + GROSS_SUBTRACTION_BASIS + ")"
        )
    return tuple(notes)


def recompute_verdict(artifact) -> str:
    """The verdict this artifact's OWN EVIDENCE supports.

    NEVER reads `artifact["verdict"]` or `artifact["exit_code"]`. Those are the
    two fields a forged document would set, and trusting either of them would
    make the whole gate a formality: an artifact could buy exit 0 by writing 0
    into itself. Every branch below reads counts, digests, baselines and
    accounting lines instead.

    Returns the MOST SEVERE applicable token by `VERDICT_SEVERITY_ORDER`.
    """
    applicable = []
    rows = _rows(artifact)

    # -- CENSUS_ERROR (7) --------------------------------------------------
    if artifact.get("errors"):
        applicable.append("CENSUS_ERROR")
    for _role, block in _projects(artifact):
        if block.get("opened_read_only") is not True:
            applicable.append("CENSUS_ERROR")
        if block.get("fwdata_sha256_before") != block.get("fwdata_sha256_after"):
            applicable.append("CENSUS_ERROR")
    if baseline_misdeclared(artifact):
        applicable.append("CENSUS_ERROR")
    if uncorroborated_null_rows(artifact):
        applicable.append("CENSUS_ERROR")  # invariant 12
    for row in rows:
        difference = _int_or_none(row.get("difference"))
        for line in _lines(row):
            reason = line.get("reason")
            count = int(line.get("count", 0) or 0)
            if reason not in REASON_TOKENS:
                applicable.append("CENSUS_ERROR")  # UNCLASSIFIABLE_REASON
                continue
            if reason in REASONS_NOT_REQUIRING_REPORT_REF:
                continue
            ref = line.get("report_ref")
            in_report = (
                _int_or_none(ref.get("count_in_report"))
                if isinstance(ref, dict) else None
            )
            if in_report is None or in_report < count:
                applicable.append("CENSUS_ERROR")  # R-1
        if difference is not None:
            if (_line_sum(row, "shortfall") > max(0, -difference)
                    or _line_sum(row, "surplus") > max(0, difference)):
                applicable.append("CENSUS_ERROR")  # R-2
        basis = row.get("match_basis")
        if (isinstance(basis, dict)
                and basis.get("basis_source") == "run_report"
                and _is_required(row)):
            summands = [
                _int_or_none(basis.get(name)) for name in MATCH_BASIS_SUMMANDS
            ]
            source = _int_or_none(row.get("source_count"))
            if (all(v is not None for v in summands) and source is not None
                    and sum(summands) != source):
                applicable.append("CENSUS_ERROR")  # invariant 11

    # -- COVERAGE_INCOMPLETE (6) ------------------------------------------
    provenance = artifact.get("class_list_provenance") or {}
    derivation = provenance.get("derivation_check") or {}
    if derivation.get("result") not in (None, "match"):
        applicable.append("COVERAGE_INCOMPLETE")
    if derivation.get("performed") is not True:
        applicable.append("COVERAGE_INCOMPLETE")
    required_count = _int_or_none(provenance.get("required_class_count"))
    if required_count is not None and required_count != len(rows):
        applicable.append("COVERAGE_INCOMPLETE")

    # -- BASELINE_MISSING (4) / BASELINE_STALE (5) ------------------------
    baseline = artifact.get("starter_baseline")
    if not isinstance(baseline, dict) or baseline.get("kind") == "none":
        # An ABSENT baseline block is treated exactly like `kind: "none"`: the
        # census cannot subtract what it never had, and absence is a verdict.
        applicable.append("BASELINE_MISSING")
    elif baseline_staleness(artifact) == "stale":
        applicable.append("BASELINE_STALE")

    # -- DUPLICATE_IDENTITY (3) -------------------------------------------
    if any(duplicates_unaccounted(row) > 0 for row in rows):
        applicable.append("DUPLICATE_IDENTITY")

    # -- UNEXPLAINED_SHORTFALL (1) / UNEXPLAINED_SURPLUS (2) --------------
    # R-4, and SC-005 in one line. Scoped to `required` rows: an advisory row
    # cannot by itself fail the gate (CP-3).
    #
    # T023a / 5.2's GROSS-BASIS CAP. `is_gross_basis_row` rows are skipped here
    # -- "every row is advisory for SHORTFALL purposes" (fidelity-census.md:251)
    # -- because gross subtraction removes the matched starter objects twice and
    # so manufactures a shortfall on a correct run (43 - 23 = 20 against a
    # source of 41). The suppression is a CEILING and nothing more: the two
    # tokens simply never enter `applicable`, so every more-severe token
    # already appended above (CENSUS_ERROR, COVERAGE_INCOMPLETE,
    # BASELINE_MISSING, BASELINE_STALE, DUPLICATE_IDENTITY) still wins the
    # `most_severe_verdict` choice untouched.
    #
    # A `baseline_matched` row is NOT skipped: its shortfall is trustworthy
    # evidence and must still fail the run even in the same artifact as a
    # gross-basis row. Nor is a row whose baseline document counted ZERO for
    # its class: gross subtraction over a baseline of 0 removes nothing, so it
    # cannot have over-removed anything either, and both bases yield the same
    # integer. T110; `is_gross_basis_row` is where that lives, so this branch
    # needed no second condition.
    if any(_is_required(r) and not is_gross_basis_row(r)
           and int(r.get("unexplained_shortfall", 0) or 0) > 0
           for r in rows):
        applicable.append("UNEXPLAINED_SHORTFALL")
    if any(_is_required(r) and not is_gross_basis_row(r)
           and int(r.get("unexplained_surplus", 0) or 0) > 0
           for r in rows):
        applicable.append("UNEXPLAINED_SURPLUS")

    # -- CENSUS_ACCOUNTED (0) vs CENSUS_CLEAN (0) -------------------------
    # Clean means nothing needed explaining. Accounted means something did and
    # every unit of it is explained by a valid line.
    if any(_lines(row) for row in rows):
        applicable.append("CENSUS_ACCOUNTED")
    # ...or, on the gross basis, by the SUBTRACTION BASIS rather than a line.
    # This is the FLOOR half of the cap and it is not optional: without it a
    # suppressed 21-object shortfall would leave `applicable` holding only
    # CENSUS_CLEAN, and the run would report that NOTHING needed explaining.
    # The cap's ceiling is CENSUS_ACCOUNTED, so CENSUS_CLEAN must stay
    # unreachable BY CAPPING while remaining reachable on a run's own merits
    # (no suppressions, no lines -> the append below still wins).
    if gross_basis_suppressions(artifact):
        applicable.append(GROSS_BASIS_VERDICT_CAP)
    applicable.append("CENSUS_CLEAN")

    return most_severe_verdict(applicable)


def stamp_verdict(artifact) -> dict:
    """Write the recomputed verdict, exit code and human label into `artifact`.

    The ONLY sanctioned way those three fields get their values, so the console
    label and the artifact token cannot disagree and neither can be authored by
    hand.

    Also appends 5.2's cap notes when the gross basis suppressed anything, so a
    stamped `CENSUS_ACCOUNTED` always carries the reason it is not
    `UNEXPLAINED_SHORTFALL`. Appending is deduplicated, so stamping twice does
    not double the notes; the notes are reportage and the verdict never reads
    them back (invariant 9).
    """
    verdict = recompute_verdict(artifact)
    artifact["verdict"] = verdict
    artifact["exit_code"] = exit_code_for(verdict)
    artifact["verdict_human_label"] = VERDICT_HUMAN_LABELS[verdict]
    cap_notes = gross_basis_cap_notes(artifact)
    if cap_notes:
        notes = artifact.get("notes")
        notes = list(notes) if isinstance(notes, list) else []
        notes.extend(n for n in cap_notes if n not in notes)
        artifact["notes"] = notes
    return artifact


# ---------------------------------------------------------------------------
# Row-level pass, for the record
# ---------------------------------------------------------------------------


def row_passes(row) -> bool:
    """Section 6's two conditions, BOTH required:

    1. `difference == 0`, or every non-zero unit accounted for; AND
    2. `duplicates.extra_objects == 0`, or each duplicate group accounted.

    Condition 2 is why the census is a gate for SC-002 and not merely for
    SC-005: the measured phoneme row satisfies condition 1 exactly (difference
    0) while carrying 21 duplicate names.
    """
    if row.get("verdict_class") == "NOT_EVALUATED":
        return True
    if not _is_required(row):
        return True
    if int(row.get("unexplained_shortfall", 0) or 0) > 0:
        return False
    if int(row.get("unexplained_surplus", 0) or 0) > 0:
        return False
    return duplicates_unaccounted(row) == 0


# ---------------------------------------------------------------------------
# The phase predicates (fidelity-census.md 9.1)
#
# Acceptance for Phases 1..5 is a census DIFF, not a unit test. Each predicate
# names classes and counts, and every failure string NAMES THE CLASS it failed
# on -- a predicate that says only "phase 1 failed" cannot be acted on.
# ---------------------------------------------------------------------------

#: P1 (identity): the four MSA subclasses plus PartOfSpeech. (SC-001, SC-002)
PHASE_1_MATCHED_CLASSES: tuple = (
    "MoStemMsa", "MoInflAffMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa",
    "PartOfSpeech",
)

#: P2 (closure): the template and its slots. (SC-004)
PHASE_2_MATCHED_CLASSES: tuple = ("MoInflAffixTemplate", "MoInflAffixSlot")

#: P3 (enrichment): the owned-child classes FR-020 enriches rather than
#: recreates. (SC-007)
PHASE_3_OWNED_CHILD_CLASSES: tuple = (
    "MoInflAffixTemplate", "MoInflAffixSlot", "MoInflClass", "MoStemName",
    "MoStemAllomorph", "MoMorphType",
)

#: P4 (process rules): BOTH halves, because either alone can be satisfied by the
#: defect itself -- 13 MoAffixProcess became 13 extra MoAffixAllomorph, so
#: checking only the allomorph difference would pass a whole-class downgrade.
PHASE_4_CLASSES: tuple = ("MoAffixProcess", "MoAffixAllomorph")

#: P1's full scope: the five classes it requires MATCHED, PLUS `PhPhoneme`,
#: which it names on a DIFFERENT condition (duplicates, SC-002) and does not
#: require MATCHED. The distinction matters here and nowhere else: a phase's
#: scope is every class it NAMES, not only the ones it counts, so a suppression
#: on the phoneme row is P1's business even though the predicate would still be
#: satisfied with it.
PHASE_1_CLASSES: tuple = PHASE_1_MATCHED_CLASSES + ("PhPhoneme",)

#: P3's full scope: `PartOfSpeech`, named on the enrichment condition rather
#: than on MATCHED, plus the owned children it does require MATCHED.
PHASE_3_CLASSES: tuple = ("PartOfSpeech",) + PHASE_3_OWNED_CHILD_CLASSES

#: P5 (residual) has NO closed class set, and that is not an omission. Its
#: predicate is "every remaining `required` row", so its scope IS the whole
#: artifact. Recorded as `None` rather than as a tuple because the difference
#: is load-bearing: `phase_scoped_suppressions` returns EVERY suppression for
#: an unbounded phase, which is what denies P5 the out-of-scope reading that
#: P1..P4 may legitimately claim. T081 gets no escape hatch here.
PHASE_5_CLASSES = None


# ---------------------------------------------------------------------------
# T109 LOCK 1 -- IMPORT-TIME DISJOINTNESS. A phase-owned class must be UNABLE
# to appear on the governed-by-another-feature roster.
#
# Enforced HERE, at module scope, and not in a test, for the reason T079 states
# at `report.py`'s equivalent: reclassifying an owned class as somebody else's
# is the one direction that lets this feature dodge its own gate, and a rule
# that only a test enforces is a rule a `-k` selection can skip past. A module
# that cannot be imported cannot emit a laundered artifact.
#
# STRONGER THAN T079'S, in one specific way. `report.py` checks the roster
# against `models.CENSUS_PHASE_GATED_CLASSES`, a hand-spelled MIRROR of the
# predicate scopes (models cannot import this module -- the dependency
# direction is census -> models), and needs a second check to prove the mirror
# still matches. This check is against `PHASE_1_CLASSES`, `PHASE_2_
# MATCHED_CLASSES`, `PHASE_3_CLASSES` and `PHASE_4_CLASSES` THEMSELVES, three
# lines above, so there is no mirror to drift. `PHASE_5_CLASSES` is excluded
# for the reason its own comment gives: it is `None`, meaning "every required
# row", and folding that in would make every class phase-gated and the roster
# necessarily empty.
_T109_PHASE_OWNED = (
    frozenset(PHASE_1_CLASSES)
    | frozenset(PHASE_2_MATCHED_CLASSES)
    | frozenset(PHASE_3_CLASSES)
    | frozenset(PHASE_4_CLASSES)
)
_T109_OVERREACH = sorted(
    set(GOVERNED_BY_OTHER_FEATURE_CLASSES) & _T109_PHASE_OWNED)
if _T109_OVERREACH:  # pragma: no cover - a source defect, not a state
    raise CensusError(
        "feature 038 T109: " + ", ".join(_T109_OVERREACH) + " is both on the "
        "GOVERNED_BY_OTHER_FEATURE roster and named by a 038 phase predicate. "
        "That line is admissible accounting under PHASE_5_ADMISSIBLE_REASONS "
        "and subtracts from unexplained_shortfall, so rostering a class this "
        "feature has an executable gate on would turn its own red row green"
    )
_T109_UNOWNED = sorted(
    cls for cls, entry in GOVERNED_BY_OTHER_FEATURE_CLASSES.items()
    if not (isinstance(entry, tuple) and len(entry) == 2
            and all(isinstance(half, str) and half.strip() for half in entry))
)
if _T109_UNOWNED:  # pragma: no cover - a source defect, not a state
    raise CensusError(
        "feature 038 T109: " + ", ".join(_T109_UNOWNED) + " carries no "
        "(owner, reason) pair. An accounting line that names no owner is the "
        "unowned claim the roster's own derivation refuses -- SC-010's 'a "
        "report line the user cannot act on is not a report', applied to a "
        "line that also retires a measured shortfall"
    )


@dataclass(frozen=True)
class PhaseResult:
    """The answer for one phase: satisfied, and if not, exactly why."""

    phase: int
    satisfied: bool
    failures: tuple = ()

    def __post_init__(self) -> None:
        if self.satisfied and self.failures:
            raise CensusError(
                "PhaseResult for phase " + str(self.phase) + " claims "
                "satisfied with failures recorded: " + "; ".join(self.failures)
            )


def _row_by_class(artifact, object_class: str) -> Optional[dict]:
    """One row, matched EXACTLY on the emitted class name.

    Exact match is sufficient because `class` is always the plain LCM class
    name: an A1 split carries its owner in `owning_feature_system` rather than
    inside the label, so the prefix-matching fallback this function used to need
    is gone. No phase predicate names a split class; one that ever does must
    select on the owner too, because either half alone is not the class.
    """
    for row in _rows(artifact):
        if _row_label(row) == object_class:
            return row
    return None


def _require_matched(artifact, object_class: str, phase: int) -> tuple:
    """`(failures,)` for "class X's row is MATCHED"."""
    row = _row_by_class(artifact, object_class)
    if row is None:
        return (
            "P" + str(phase) + ": no census row for " + object_class
            + " -- FR-012 requires one row per class, so an absent row is a "
            "coverage defect and not a pass",
        )
    verdict_class = row.get("verdict_class")
    if verdict_class != "MATCHED":
        return (
            "P" + str(phase) + ": " + object_class + " is " + str(verdict_class)
            + " (difference " + str(row.get("difference")) + "), not MATCHED",
        )
    if not row_passes(row):
        return (
            "P" + str(phase) + ": " + object_class + " counts as MATCHED but "
            "does not pass its row conditions (unexplained "
            + str(row.get("unexplained_shortfall")) + "/"
            + str(row.get("unexplained_surplus")) + ", unaccounted duplicates "
            + str(duplicates_unaccounted(row)) + ")",
        )
    return ()


def _phase_1(artifact) -> tuple:
    failures: list = []
    for name in PHASE_1_MATCHED_CLASSES:
        failures.extend(_require_matched(artifact, name, 1))
    row = _row_by_class(artifact, "PhPhoneme")
    if row is None:
        failures.append(
            "P1: no census row for PhPhoneme -- SC-002 is measured on that row"
        )
    else:
        extra = int(_duplicates(row).get("extra_objects", 0) or 0)
        if extra != 0:
            failures.append(
                "P1: PhPhoneme duplicates.extra_objects is " + str(extra)
                + ", not 0 -- difference is " + str(row.get("difference"))
                + ", so baseline arithmetic alone would have passed this row "
                "(SC-002)"
            )
    return tuple(failures)


def _phase_2(artifact) -> tuple:
    failures: list = []
    for name in PHASE_2_MATCHED_CLASSES:
        failures.extend(_require_matched(artifact, name, 2))
    return tuple(failures)


def _phase_3(artifact) -> tuple:
    failures: list = []
    row = _row_by_class(artifact, "PartOfSpeech")
    if row is None:
        failures.append(
            "P3: no census row for PartOfSpeech, so nothing can show it was "
            "enriched"
        )
    else:
        basis = row.get("match_basis")
        enriched = (
            _int_or_none(basis.get("enriched")) if isinstance(basis, dict)
            else None
        )
        if not enriched:
            failures.append(
                "P3: PartOfSpeech match_basis.enriched is " + str(enriched)
                + ", not > 0 -- nothing was enriched, which is what a "
                "whole-object SKIP decided by GUID presence alone looks like "
                "(defect G3) while every row still reports MATCHED"
            )
    for name in PHASE_3_OWNED_CHILD_CLASSES:
        failures.extend(_require_matched(artifact, name, 3))
    return tuple(failures)


def _phase_4(artifact) -> tuple:
    failures: list = []
    failures.extend(_require_matched(artifact, "MoAffixProcess", 4))
    row = _row_by_class(artifact, "MoAffixAllomorph")
    if row is None:
        failures.append(
            "P4: no census row for MoAffixAllomorph -- the downgrade is only "
            "visible in BOTH rows at once"
        )
    else:
        difference = _int_or_none(row.get("difference"))
        if difference != 0:
            failures.append(
                "P4: MoAffixAllomorph difference is " + str(difference)
                + ", not 0 -- 13 MoAffixProcess became 13 extra "
                "MoAffixAllomorph, so either half alone can be satisfied by "
                "the defect itself"
            )
        elif not row_passes(row):
            failures.append(
                "P4: MoAffixAllomorph difference is 0 but the row does not "
                "pass its own conditions (unaccounted duplicates "
                + str(duplicates_unaccounted(row)) + ")"
            )
    return tuple(failures)


def _phase_5(artifact) -> tuple:
    failures: list = []
    for row in _rows(artifact):
        if not _is_required(row):
            continue
        verdict_class = row.get("verdict_class")
        if verdict_class in ("MATCHED", "NOT_EVALUATED"):
            if verdict_class == "MATCHED" and not row_passes(row):
                failures.append(
                    "P5: " + _row_label(row) + " is MATCHED but carries "
                    + str(duplicates_unaccounted(row))
                    + " unaccounted duplicate objects"
                )
            continue
        lines = _lines(row)
        if not lines:
            failures.append(
                "P5: " + _row_label(row) + " is " + str(verdict_class)
                + " (difference " + str(row.get("difference"))
                + ") and carries NO accounting line -- absence of an "
                "accounted_for list is not an excuse (R-5)"
            )
            continue
        wrong = tuple(sorted({
            str(line.get("reason")) for line in lines
            if line.get("reason") not in PHASE_5_ADMISSIBLE_REASONS
        }))
        if wrong:
            failures.append(
                "P5: " + _row_label(row) + " accounts with " + ", ".join(wrong)
                + ", which is real accounting but not phase-5 done -- P5 admits "
                "GOVERNED_BY_OTHER_FEATURE and NO_CREATE_PATH only"
            )
        if (int(row.get("unexplained_shortfall", 0) or 0)
                or int(row.get("unexplained_surplus", 0) or 0)):
            failures.append(
                "P5: " + _row_label(row) + " still has unexplained "
                + str(row.get("unexplained_shortfall")) + " shortfall / "
                + str(row.get("unexplained_surplus")) + " surplus after its "
                "accounting lines"
            )
    return tuple(failures)


@dataclass(frozen=True)
class PhasePredicate:
    """One phase's exit criteria, as a predicate over the ARTIFACT.

    "A phase is not done when its unit tests pass; it is done when the census
    run for its predicate exits 0 with the predicate satisfied." Both halves
    live in `gate_artifact`.
    """

    phase: int
    name: str
    description: str
    check: object
    #: Every class this predicate NAMES, or `None` for "every required row".
    #: Required, with no default: a phase that forgets to declare its scope
    #: must fail to construct rather than quietly inherit somebody else's.
    classes: object

    def __post_init__(self) -> None:
        if self.classes is not None and not self.classes:
            raise CensusError(
                "phase " + str(self.phase) + " declares an EMPTY class scope. "
                "None means 'every required row' (P5's answer); an empty tuple "
                "would mean 'no row is in scope', which turns every capped row "
                "into somebody else's problem and makes the phase-scoped "
                "reading of the gate unfalsifiable"
            )

    def evaluate(self, artifact) -> PhaseResult:
        failures = tuple(self.check(artifact))
        return PhaseResult(
            phase=self.phase, satisfied=not failures, failures=failures)


PHASE_PREDICATES: dict = {
    1: PhasePredicate(
        1, "identity",
        "MoStemMsa, MoInflAffMsa, MoDerivAffMsa, MoUnclassifiedAffixMsa and "
        "PartOfSpeech rows MATCHED; PhPhoneme.duplicates.extra_objects == 0 "
        "(SC-001, SC-002)",
        _phase_1, PHASE_1_CLASSES,
    ),
    2: PhasePredicate(
        2, "closure",
        "MoInflAffixTemplate and MoInflAffixSlot rows MATCHED (SC-004)",
        _phase_2, PHASE_2_MATCHED_CLASSES,
    ),
    3: PhasePredicate(
        3, "enrichment",
        "match_basis.enriched > 0 on PartOfSpeech, and the owned-child classes "
        "MATCHED (SC-007)",
        _phase_3, PHASE_3_CLASSES,
    ),
    4: PhasePredicate(
        4, "process rules",
        "MoAffixProcess MATCHED and MoAffixAllomorph difference == 0 -- both, "
        "because either alone can be satisfied by the defect itself (SC-006)",
        _phase_4, PHASE_4_CLASSES,
    ),
    5: PhasePredicate(
        5, "residual",
        "every remaining required row is either MATCHED or carries a valid "
        "GOVERNED_BY_OTHER_FEATURE / NO_CREATE_PATH line (SC-005)",
        _phase_5, PHASE_5_CLASSES,
    ),
}


def evaluate_phase(artifact, phase: int) -> PhaseResult:
    """Evaluate one phase predicate against an artifact."""
    return _predicate(phase).evaluate(artifact)


def _predicate(phase: int) -> PhasePredicate:
    try:
        return PHASE_PREDICATES[phase]
    except KeyError:
        raise CensusError(
            "phase " + repr(phase) + " is not one of "
            + repr(tuple(sorted(PHASE_PREDICATES)))
        ) from None


def phase_classes(phase: int):
    """The closed set of classes phase `phase` names, or `None` if unbounded.

    Read off the predicate itself so no caller has to hand-maintain a second
    copy that can drift from the one `evaluate_phase` actually enforces.
    `None` is P5's answer and means "every required row".
    """
    classes = _predicate(phase).classes
    return None if classes is None else frozenset(classes)


def phase_scoped_suppressions(artifact, phase: int) -> tuple:
    """The 5.2 suppressions that fall INSIDE phase `phase`'s declared scope.

    9.1 says a phase "is done when the census run for its predicate exits 0
    with the predicate satisfied", and `census_cli.CAPPED_PASS_EXIT_CODE`
    (T024b) makes exit 0 a PROJECT-WIDE property: one suppressed row anywhere
    denies it. That is right for the release gate and it has a consequence 9.1
    does not mention -- no early phase can be declared done until the last one
    is, because P1's exit code waits on accounting that belongs to Phase 9
    (T079). Measured: on `CENSUS-20260820-150540` all of P1, P2 and P3 are
    satisfied and the gate still exits 8, on 13 capped rows of which not one is
    named by any of the three.

    **This does not change the gate, by design.** The gate stays project-wide,
    so `gate --phase 1` still exits 8 while anything at all is capped, and
    SC-010's "there is deliberately no verdict meaning loss reported, review
    advisable, exit success" is untouched. What this adds is the ability to say
    MECHANICALLY, rather than in a task's prose, that every capped row lies
    outside the phase being gated -- which is the amended third clause on
    T038/T048/T075.

    On an unbounded phase it returns every suppression. That is P5: the
    residual phase's scope is every required row, so it can never claim a
    suppressed row is somebody else's (T081 gets no escape hatch).
    """
    scope = phase_classes(phase)
    if scope is None:
        return gross_basis_suppressions(artifact)
    return gross_basis_suppressions(artifact, classes=scope)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateOutcome:
    """The gate's whole answer: token, exit code, pass/fail, and the reasons.

    `passed` is `verdict in PASSING_VERDICTS` AND no validator failure AND, when
    a phase was named, that phase satisfied. There is deliberately no fourth
    state: a run either passes the gate or it does not.
    """

    verdict: str
    exit_code: int
    passed: bool
    failures: tuple = ()
    phase: Optional[PhaseResult] = None

    @property
    def human_label(self) -> str:
        return VERDICT_HUMAN_LABELS[self.verdict]


def gate_artifact(artifact, phase: Optional[int] = None) -> GateOutcome:
    """Gate one census artifact, optionally against a phase predicate.

    The verdict is RECOMPUTED from the artifact's evidence, never read from it,
    so a document that claims `CENSUS_CLEAN` with `exit_code: 0` over
    `starter_baseline.kind == "none"` is still refused with exit 4. That is the
    whole point of 5.3's "there is no path on which a missing baseline yields
    exit 0".
    """
    verdict = recompute_verdict(artifact)
    failures = list(validate_artifact(artifact))
    phase_result = None
    if phase is not None:
        phase_result = evaluate_phase(artifact, phase)
        failures.extend(phase_result.failures)
    passed = (
        is_passing_verdict(verdict)
        and not failures
        and (phase_result is None or phase_result.satisfied)
    )
    return GateOutcome(
        verdict=verdict,
        exit_code=exit_code_for(verdict),
        passed=passed,
        failures=tuple(failures),
        phase=phase_result,
    )
