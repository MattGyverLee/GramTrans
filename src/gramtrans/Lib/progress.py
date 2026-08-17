"""Progress reporting surface -- the toolkit-free half (feature 036).

Two modules, one protocol. THIS module carries the protocol, the null
implementation, the one threshold, the anticipated-cost arithmetic and the
cheap source-count cache. It is imported by ``Lib/selection.py``, which must
stay importable with no GUI application object -- exactly as
``Lib/merge_preview.py`` is. The GUI implementation lives alone in
``Lib/ui/progress_indicator.py`` and is imported only by the wizard.

HARD CONSTRAINTS
----------------
- **Toolkit-free** (contracts/progress-sink.md preamble). This module MUST NOT
  import a GUI toolkit at any level, lazily or otherwise. Three tests in
  ``tests/unit/test_036_progress_sink.py`` enforce it: a static AST scan, a
  source-substring scan, and a subprocess import with every toolkit flavour
  blocked by an empty sentinel module.
- **No intra-package imports.** ``Lib/selection.py`` imports this module, and
  ``Lib/selection.py`` imports ``Lib/categories.py``; importing either from
  here would close a cycle. The handful of LCM accessor names this module
  needs are therefore restated locally (see ``_CUSTOM_FIELD_OWNER_CLASSES``)
  rather than imported from ``categories.py``.
- **py38 target**: ``from __future__ import annotations`` plus typing generics
  only, so ``int | None`` in a signature never evaluates at runtime.
- ASCII only: Windows terminals mangle anything else (house rule), so labels
  in this file's examples spell an ellipsis as three periods.

WHY A SINK AND NOT A CALLBACK
-----------------------------
An inventory walk needs three distinct events -- announce, advance, dismiss --
and the dismiss must fire on the failure path too (FR-020). A single callable
would have to encode all three in its arguments, and every walk would have to
remember to call it on the way out of an exception. A tiny protocol plus the
``reporting`` context manager puts that obligation in one place.

WHY ``NullSink`` AND NOT ``if progress is not None``
----------------------------------------------------
FR-022 and FR-045 require that ``progress=None`` be indistinguishable from the
code as it stands today: identical inventory, no measurable cost. A no-op sink
with ``__slots__ = ()`` gives the walk one unconditional method call per tick
against an object that holds no state and allocates nothing -- no per-tick
branch, no timer, no counter. ``NULL_SINK`` is a shared instance so a caller
that declines progress does not even allocate the sink.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ===========================================================================
# The one threshold (FR-019a, data-model section 2)
# ===========================================================================

PROGRESS_THRESHOLD_MS = 500
"""The one project-wide threshold (FR-019a).

Used twice and tuned never:

1. as the elapsed-time delay before an indicator appears for work whose size
   is not cheaply knowable (FR-014b), and
2. as the bar a predicted wait must clear to be shown up front (FR-014a).

Declared exactly once in the whole repository, which
``test_threshold_declared_in_exactly_one_place`` enforces by AST scan. A second
declaration would let the two uses drift apart silently: the delay and the bar
must be the same number, or an operation can be predicted "fast" and then get
its indicator at a different moment than an unpredictable one would.

This is NOT a per-operation number. The only per-operation number in the
feature is ``UNITS_PER_SECOND`` below.
"""


# ===========================================================================
# The protocol (FR-016, FR-017, FR-020)
# ===========================================================================


@runtime_checkable
class ProgressSink(Protocol):
    """Where an operation reports what it is doing. Toolkit-free by contract.

    ``runtime_checkable`` so tests and defensive call sites can assert the
    shape with ``isinstance``. That check is structural -- it confirms the three
    methods exist and nothing about their behaviour -- which is exactly the
    guarantee a walk needs before it starts ticking.
    """

    def begin(self, label: str, total: Optional[int] = None) -> None:
        """Announce an operation. ``total`` None => indeterminate (FR-017)."""

    def tick(self, n: int = 1) -> None:
        """Advance by ``n`` units. Cheap, and safe to call thousands of times."""

    def end(self) -> None:
        """Dismiss. Called on success, failure and abandonment alike (FR-020)."""


class NullSink:
    """The default. Every method is a no-op, so ``progress=None`` is free.

    ``__slots__ = ()`` is load-bearing, not tidiness: it means an instance has
    no ``__dict__``, so there is no counter to increment, no start time to read
    and nothing for a walk to pay for or observe (FR-022, FR-045). Every method
    body is a bare ``return None``.

    All three contract guarantees hold trivially here, which is why the
    guarantees are phrased as they are: ``tick`` never raises (including after
    ``end``), and ``end`` is idempotent, because neither method looks at any
    state.
    """

    __slots__ = ()

    def begin(self, label: str, total: Optional[int] = None) -> None:
        """Announce nothing."""
        return None

    def tick(self, n: int = 1) -> None:
        """Advance nothing. Never raises, in any order, at any time."""
        return None

    def end(self) -> None:
        """Dismiss nothing. Idempotent because there is nothing to dismiss."""
        return None


NULL_SINK = NullSink()
"""Shared no-op sink.

Stateless and immutable, so one instance serves every caller and declining
progress costs not even an allocation.
"""


# ===========================================================================
# AnticipatedSize (data-model section 3)
# ===========================================================================


def predicted_ms(total_units: Optional[int], units_per_second: Optional[float]) -> float:
    """Anticipated duration for an operation of a known size (FR-014a).

    ``predicted_ms = total_units / units_per_second * 1000`` (data-model s3).

    Two degenerate inputs are answered rather than rejected, because this is
    called on the display path and must never be the reason a page fails to
    open:

    - ``total_units`` of None (size not cheaply knowable) or <= 0 predicts
      ``0.0``. None deliberately does NOT mean "assume large": an unknown size
      is covered by the elapsed-time fallback (FR-014b/FR-014d), and answering
      0.0 here is what lets ``warrants_indicator`` express that rule without a
      second code path.
    - a rate that is None or non-positive predicts ``inf``: zero throughput
      never finishes. ``warrants_indicator`` does not turn that into an
      up-front indicator -- see its docstring for why.
    """
    if total_units is None or total_units <= 0:
        return 0.0
    if units_per_second is None or units_per_second <= 0:
        return float("inf")
    return (float(total_units) / float(units_per_second)) * 1000.0


def warrants_indicator(total_units: Optional[int], units_per_second: Optional[float]) -> bool:
    """True when the anticipated cost clears PROGRESS_THRESHOLD_MS.

    ``total_units`` None (size unknowable) returns False: such an operation is
    covered by the elapsed-time fallback, not by up-front display (FR-014d).
    We have no basis for claiming the wait will be long, and a wrong up-front
    indicator on fast work is exactly the flash FR-019 forbids.

    An absent or non-positive ``units_per_second`` also returns False, even
    though ``predicted_ms`` calls that infinite. The rate is a calibration
    constant, and a missing calibration is a gap in OUR data, not evidence
    about the operator's wait -- so it degrades to the elapsed-time fallback
    like any other unknown. Whichever trigger fires first wins, so nothing is
    lost: an operation that then runs long still gets its indicator at
    PROGRESS_THRESHOLD_MS.

    Comparison is ``>=``, so a prediction of exactly the threshold shows.
    """
    if total_units is None:
        return False
    if units_per_second is None or units_per_second <= 0:
        return False
    return predicted_ms(total_units, units_per_second) >= PROGRESS_THRESHOLD_MS


@contextmanager
def reporting(
    sink: Optional[ProgressSink], label: str, total: Optional[int] = None
) -> Iterator[ProgressSink]:
    """``begin`` on entry, ``end`` on exit through any path, including an exception.

    This is the whole of FR-020 in one place. Without it every walk would carry
    its own try/finally, and the one that forgot would leave a modal indicator
    on screen over a failed operation -- the worst outcome available, since the
    indicator blocks the input the operator needs to dismiss the error.

    ``sink`` may be None: that is the documented "no progress" value on every
    builder signature, and it yields ``NULL_SINK`` so the body can tick
    unconditionally.

    ``begin`` is deliberately OUTSIDE the try: an operation that never began
    has nothing to dismiss, so a failure there must not also call ``end``.

    ``end`` is called inside a guard. A sink is a display object, and a display
    fault must never become the exception the caller sees -- the operation's own
    error is the one that matters, and on a clean exit there is no error to
    report at all. The fault is logged at debug level so it is recoverable
    during development without ever reaching the operator.
    """
    if sink is None:
        sink = NULL_SINK
    sink.begin(label, total)
    try:
        yield sink
    finally:
        try:
            sink.end()
        except Exception:  # noqa: BLE001 - a display fault is never the caller's error
            logger.debug("progress sink end() failed for %r", label, exc_info=True)


# ===========================================================================
# T019 -- per-operation units_per_second calibration table
# ===========================================================================

UNITS_PER_SECOND: Dict[str, Optional[float]] = {
    # FR-023 row 1: bind source project -- no cheap total exists, so there is
    # nothing to predict. None records that explicitly rather than inventing a
    # rate that could never be applied; the elapsed-time fallback governs.
    "bind_source": None,
    # FR-023 row 2: bind target project -- same.
    "bind_target": None,
    # FR-023 row 3: "Reading custom fields..." -- unit: custom-field definition.
    "custom_fields": 400.0,
    # FR-023 row 4: "Reading phonology..." -- unit: phoneme / natural class /
    # phonological rule. Rules carry structural descriptions, so the mixed
    # population reads slower per item than a flat possibility list.
    "phonology": 250.0,
    # FR-023 row 5: "Reading affixes..." -- unit: lexical entry.
    "affixes": 900.0,
    # FR-023 row 6: "Reading stems..." -- unit: lexical entry.
    "stems": 900.0,
    # FR-023 row 7: "Reading morphology skeleton..." -- unit: lexical entry.
    # Slower per entry than the affix/stem walks: it visits MSAs and slots.
    "skeleton": 500.0,
    # FR-023 row 8: "Reading grammatical dependencies..." -- unit: lexical
    # entry. The heaviest per-entry walk (reference closure).
    "dependencies": 350.0,
    # FR-023 row 9: "Reading lexical-entry types..." -- unit: list item.
    "entry_types": 1500.0,
    # FR-023 row 10: "Reading rules..." -- unit: list item.
    "rules": 600.0,
    # FR-023 row 11: "Reading texts..." -- unit: text.
    "texts": 60.0,
    # FR-023 row 12: "Building the transfer plan..." -- unit: selected category.
    "plan_assembly": 8.0,
    # FR-023 row 13: "Writing to the target project..." -- unit: plan action.
    "move_write": 40.0,
}
"""Per-operation throughput, in units per second, keyed by FR-023 row.

This is the ONLY per-operation number in the feature (FR-019a). The 500 ms
threshold is deliberately absent: it is one project-wide value
(``PROGRESS_THRESHOLD_MS``) and putting a copy here would reintroduce exactly
the per-operation drift FR-019a forbids.

**These are placeholders.** They are order-of-magnitude estimates chosen so
that the up-front/elapsed split behaves sensibly on the available test
projects, NOT measurements. T047 times a live full run and T048 replaces every
value here with the measured figure, so each prediction becomes auditable
against a real run. Until then, a wrong value can only pick the wrong
*trigger* -- up-front display versus the elapsed-time fallback -- and never
suppress the indicator altogether, because whichever trigger fires first wins.

Rounder numbers than a measurement would produce, on purpose: nothing here
should read as calibrated data before T048 does the calibrating.
"""


def rate_for(operation: str) -> Optional[float]:
    """The calibration constant for one FR-023 operation.

    Raises ``KeyError`` on an unknown name. That is deliberate: this lookup
    happens where a page sets its indicator up, never inside a walk, so a
    typo'd operation name is a wiring bug that should surface at wiring time
    rather than silently disabling an indicator forever.

    Returns None for the two bind operations, which have no cheap total;
    ``warrants_indicator`` reads that None as "use the elapsed-time fallback".
    """
    if operation not in UNITS_PER_SECOND:
        raise KeyError(
            f"unknown progress operation {operation!r}; "
            f"known operations: {sorted(UNITS_PER_SECOND)}"
        )
    return UNITS_PER_SECOND[operation]


# ===========================================================================
# T004 -- SourceCounts: the cheap count cache (FR-014d)
# ===========================================================================

# Restated from `categories._CUSTOM_FIELD_OWNER_CLASSES` rather than imported.
# `Lib/selection.py` imports THIS module and also imports `Lib/categories.py`,
# so importing categories from here would close an import cycle. Four string
# literals are a cheaper price than that cycle; if the owner-class set ever
# grows, the custom-field count here reports a floor, which degrades the
# indicator to indeterminate on overrun and nothing worse (data-model s2).
_CUSTOM_FIELD_OWNER_CLASSES = ("LexEntry", "LexSense", "LexExampleSentence", "MoForm")


def _int_or_none(value: Any) -> Optional[int]:
    """An ``int`` when ``value`` really is one, else None ("unknown").

    ``bool`` is rejected along with everything else non-int: a count of True is
    a bug upstream, not a count of 1. An LCM ``.Count`` arrives through
    Python.NET as a plain int, so a non-int here means the attribute was not
    the collection we assumed and its value must not be trusted as a total.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _count_of(collection: Any) -> Optional[int]:
    """Size of an LCM collection in O(1), or None when it cannot be had cheaply.

    Three probes, in cost order, and **no iteration at any point** -- iterating
    would be the counting pass FR-014d forbids, and it is precisely the
    expensive walk the indicator exists to cover.

    1. ``PossibilitiesOS.Count`` -- for a ``CmPossibilityList`` the interesting
       number is how many possibilities it owns, not the list object's own
       ``.Count``. Checked first because a possibility list has both.
    2. ``.Count`` -- LCM owning/reference collections expose this and often do
       not support ``len()`` (see ``selection._nonempty_seq`` for the same
       asymmetry).
    3. ``len()`` -- for the plain Python lists that the headless fakes and
       ``GetAllFields`` return.

    Anything else, including None, is "unknown".
    """
    if collection is None:
        return None

    possibilities = getattr(collection, "PossibilitiesOS", None)
    if possibilities is not None:
        nested = _int_or_none(getattr(possibilities, "Count", None))
        if nested is not None:
            return nested

    direct = _int_or_none(getattr(collection, "Count", None))
    if direct is not None:
        return direct

    try:
        return len(collection)
    except TypeError:
        return None


def _walk_attrs(root: Any, *names: str) -> Any:
    """Follow an attribute chain defensively; None the moment it breaks.

    The chains this module needs (``Cache.LangProject.PhonologicalDataOA...``)
    are four links long and every link is optional in a project that has never
    used that subsystem -- and absent entirely in the duck-typed fakes the unit
    tests bind. A missing link is "unknown", never an ``AttributeError``.

    Property access on a live LCM object can also throw, so each hop is
    guarded rather than merely checked for existence.
    """
    current = root
    for name in names:
        if current is None:
            return None
        try:
            current = getattr(current, name, None)
        except Exception:  # noqa: BLE001 - a hostile property is "unknown"
            return None
    return current


def _probe(fn) -> Optional[int]:
    """Run one count probe; any failure at all means "unknown".

    Every count in ``SourceCounts`` goes through here, which is the single
    reason the class can promise it never raises. A count is a display input:
    losing one costs an indeterminate bar instead of a determinate one, and
    that is never worth failing a project bind over.
    """
    try:
        return _int_or_none(fn())
    except Exception:  # noqa: BLE001 - a failed probe is "unknown", not an error
        logger.debug("SourceCounts probe failed", exc_info=True)
        return None


def _sum_or_none(*parts: Optional[int]) -> Optional[int]:
    """Sum the parts, or None if ANY part is unknown.

    Conservative on purpose. A partial sum would under-state the total, and an
    under-stated total is worse than no total: the bar fills, overruns, and
    degrades to indeterminate anyway (data-model s2) after first promising the
    operator a finish line that was never real. None asks for an indeterminate
    bar from the first frame instead.
    """
    total = 0
    for part in parts:
        if part is None:
            return None
        total += part
    return total


class SourceCounts:
    """Cheap counts read once, when a source project binds (FR-014d).

    WHY A SNAPSHOT AND NOT LIVE READS
    ---------------------------------
    Two callers need these numbers, and both need them to be free:

    - the anticipated-cost prediction (data-model s3) turns a count into a
      ``predicted_ms`` before a walk starts, and
    - the wizard's page-skip predicates (data-model s1) consult them from
      ``QWizardPage.nextId()``, which the toolkit may call on every
      ``completeChanged`` -- so a live read there would re-hit the project
      dozens of times per keystroke.

    Filling once at bind makes both O(1) forever after. The cost is a snapshot
    that can go stale, which is correct for this use: the source project is
    read-only for the whole run (Phase-0 transfer is additive, target-only), so
    nothing in the session can change these numbers.

    GUARANTEES
    ----------
    - **Never raises.** Every probe goes through ``_probe``; a missing
      accessor, a hostile property or an unexpected type all yield None.
    - **Never counts.** No accessor iterates a collection. ``.Count`` and
      ``len()`` only -- see ``_count_of``.
    - **Every accessor is ``int`` or None.** None means "unknown", which every
      consumer treats conservatively: ``warrants_indicator`` answers False and
      the indicator falls back to elapsed time, and a page-skip predicate shows
      the page (data-model s1: conservative means True when unsure).

    ONE HONEST CAVEAT
    -----------------
    The two count methods are the project's own, and their internals are not
    ours: ``LexiconNumberOfEntries()`` is an LCM repository count (O(1)), while
    flexicon's ``TextsNumberOfTexts()`` enumerates the text repository. Neither
    walks entry contents, and both are paid exactly once, inside the project
    bind that already carries its own indicator ("Opening source project...").
    So no wizard page and no ``nextId()`` call ever pays for them. What this
    class guarantees on its own behalf is that IT adds no pass of its own.
    """

    __slots__ = (
        "_lexicon_entries",
        "_texts",
        "_custom_fields",
        "_phoneme_sets",
        "_natural_classes",
        "_phonological_rules",
        "_variant_types",
        "_complex_form_types",
        "_adhoc_prohibitions",
    )

    def __init__(self, source: Any = None) -> None:
        """Fill the snapshot from a bound source handle, or all-None from None.

        ``source=None`` is the "nothing bound yet" state and is the reason the
        wizard can construct this before step 1 completes.

        Accessor paths mirror the ones ``Lib/selection.py`` and
        ``Lib/categories.py`` already use against live projects, so this reads
        the same shape the transfer engine does:

        - ``Cache.LangProject.PhonologicalDataOA.{PhonemeSetsOS,
          NaturalClassesOS, PhonRulesOS}``
        - ``Cache.LangProject.LexDbOA.{VariantEntryTypesOA,
          ComplexEntryTypesOA}`` (possibility lists -> ``PossibilitiesOS``)
        - ``Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC``
        """
        if source is None:
            self._lexicon_entries = None
            self._texts = None
            self._custom_fields = None
            self._phoneme_sets = None
            self._natural_classes = None
            self._phonological_rules = None
            self._variant_types = None
            self._complex_form_types = None
            self._adhoc_prohibitions = None
            return

        # -- Whole-lexicon and whole-text counts: the project's own methods.
        self._lexicon_entries = _probe(lambda: source.LexiconNumberOfEntries())
        self._texts = _probe(lambda: source.TextsNumberOfTexts())

        # -- Custom fields: metadata-cache definitions, not data. GetAllFields
        # returns a real list per owner class, so len() is O(1) on each; the
        # four calls read the MDC, never the database. A class that is missing
        # or throws contributes nothing rather than voiding the whole count,
        # because a partial definition list is still a usable floor here (see
        # _CUSTOM_FIELD_OWNER_CLASSES).
        self._custom_fields = _probe(lambda: self._count_custom_fields(source))

        # -- Phonology: three owning sequences under PhonologicalDataOA.
        phon = _walk_attrs(source, "Cache", "LangProject", "PhonologicalDataOA")
        self._phoneme_sets = _probe(lambda: _count_of(_walk_attrs(phon, "PhonemeSetsOS")))
        self._natural_classes = _probe(lambda: _count_of(_walk_attrs(phon, "NaturalClassesOS")))
        self._phonological_rules = _probe(lambda: _count_of(_walk_attrs(phon, "PhonRulesOS")))

        # -- Entry types: two possibility lists under LexDbOA.
        lex_db = _walk_attrs(source, "Cache", "LangProject", "LexDbOA")
        self._variant_types = _probe(lambda: _count_of(_walk_attrs(lex_db, "VariantEntryTypesOA")))
        self._complex_form_types = _probe(
            lambda: _count_of(_walk_attrs(lex_db, "ComplexEntryTypesOA"))
        )

        # -- Ad-hoc prohibitions: the Rules page's declared cheap total
        # (data-model s1 row 10).
        morph = _walk_attrs(source, "Cache", "LangProject", "MorphologicalDataOA")
        self._adhoc_prohibitions = _probe(
            lambda: _count_of(_walk_attrs(morph, "AdhocCoProhibitionsOC"))
        )

    @classmethod
    def unknown(cls) -> "SourceCounts":
        """The explicit "no source bound" value: every count None.

        Named rather than spelled ``SourceCounts(None)`` at call sites so the
        wizard's pre-bind state reads as a deliberate choice.
        """
        return cls(None)

    @staticmethod
    def _count_custom_fields(source: Any) -> Optional[int]:
        """Definitions across the four supported owner classes, or None.

        None only when the handle has no ``CustomFields`` accessor at all -- a
        project always has the metadata cache, so that means the handle is not
        a project. A single failing class is skipped instead (see the comment
        in ``__init__``).
        """
        cf_ops = getattr(source, "CustomFields", None)
        if cf_ops is None:
            return None
        total = 0
        for owner_class in _CUSTOM_FIELD_OWNER_CLASSES:
            try:
                fields = cf_ops.GetAllFields(owner_class)
            except Exception:  # noqa: BLE001 - class missing or read error
                continue
            size = _count_of(fields)
            if size is not None:
                total += size
        return total

    # -- Atoms -------------------------------------------------------------
    # Properties, not methods, to make it visually obvious at every call site
    # that reading one is a field access and not a project query.

    @property
    def lexicon_entries(self) -> Optional[int]:
        """``LexiconNumberOfEntries()`` -- the unit for rows 5-8 of FR-023.

        Affix, stem, skeleton and dependency enumeration all walk the lexicon,
        so all four predict from this one number with their own rate.
        """
        return self._lexicon_entries

    @property
    def texts(self) -> Optional[int]:
        """``TextsNumberOfTexts()`` -- FR-023 row 11, and the row-11 skip check."""
        return self._texts

    @property
    def custom_fields(self) -> Optional[int]:
        """Custom-field definitions -- FR-023 row 3, and the row-3 skip check."""
        return self._custom_fields

    @property
    def phoneme_sets(self) -> Optional[int]:
        """``PhonologicalDataOA.PhonemeSetsOS.Count``."""
        return self._phoneme_sets

    @property
    def natural_classes(self) -> Optional[int]:
        """``PhonologicalDataOA.NaturalClassesOS.Count``."""
        return self._natural_classes

    @property
    def phonological_rules(self) -> Optional[int]:
        """``PhonologicalDataOA.PhonRulesOS.Count``."""
        return self._phonological_rules

    @property
    def variant_types(self) -> Optional[int]:
        """``LexDbOA.VariantEntryTypesOA`` possibility count."""
        return self._variant_types

    @property
    def complex_form_types(self) -> Optional[int]:
        """``LexDbOA.ComplexEntryTypesOA`` possibility count."""
        return self._complex_form_types

    @property
    def adhoc_prohibitions(self) -> Optional[int]:
        """``MorphologicalDataOA.AdhocCoProhibitionsOC.Count``."""
        return self._adhoc_prohibitions

    # -- Page-level aggregates --------------------------------------------
    # One per wizard page whose unit is "list item", so a page asks for its own
    # total by name instead of adding atoms up at the call site.

    @property
    def phonology(self) -> Optional[int]:
        """FR-023 row 4: phonemes + natural classes + phonological rules."""
        return _sum_or_none(
            self._phoneme_sets, self._natural_classes, self._phonological_rules
        )

    @property
    def entry_types(self) -> Optional[int]:
        """FR-023 row 9: variant types + complex-form types."""
        return _sum_or_none(self._variant_types, self._complex_form_types)

    @property
    def rules(self) -> Optional[int]:
        """FR-023 row 10: the ad-hoc prohibition count.

        The declared cheap total for the Rules page (data-model s1 row 10 and
        s3). The rules walk also visits compound rules, which are not counted
        here, so this can under-state a project that uses them; the bar then
        overruns and degrades to indeterminate (data-model s2), which is the
        documented behaviour and not a defect.
        """
        return self._adhoc_prohibitions

    # -- Diagnostics -------------------------------------------------------

    def as_dict(self) -> Dict[str, Optional[int]]:
        """Snapshot as a plain dict, for logging and for tests.

        Atoms only: the aggregates are derived, and including them would make a
        log line look like it had measured something twice.
        """
        return {
            "lexicon_entries": self._lexicon_entries,
            "texts": self._texts,
            "custom_fields": self._custom_fields,
            "phoneme_sets": self._phoneme_sets,
            "natural_classes": self._natural_classes,
            "phonological_rules": self._phonological_rules,
            "variant_types": self._variant_types,
            "complex_form_types": self._complex_form_types,
            "adhoc_prohibitions": self._adhoc_prohibitions,
        }

    def __repr__(self) -> str:
        """ASCII-only one-liner naming every measured count."""
        body = ", ".join(f"{k}={v}" for k, v in self.as_dict().items())
        return f"SourceCounts({body})"
