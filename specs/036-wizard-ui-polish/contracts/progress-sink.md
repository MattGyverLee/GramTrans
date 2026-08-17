# Contract: progress sink

**Feature**: 036-wizard-ui-polish | **Requirements**: FR-014..FR-023, FR-045

Two modules, one protocol. `Lib/progress.py` is **Qt-free** — it is imported by
`Lib/selection.py`, which must stay importable without a `QApplication`, exactly
as `Lib/merge_preview.py` does. `Lib/ui/progress_indicator.py` is the only Qt
implementation.

## `Lib/progress.py`

```python
PROGRESS_THRESHOLD_MS = 500
"""The one project-wide threshold (FR-019a).

Used twice and tuned never: as the elapsed-time delay before an indicator
appears for work whose size is unknowable (FR-014b), and as the bar a predicted
wait must clear to be shown up front (FR-014a).
"""


class ProgressSink(Protocol):
    """Where an operation reports what it is doing. Qt-free by contract."""

    def begin(self, label: str, total: int | None = None) -> None:
        """Announce an operation. `total` None => indeterminate (FR-017)."""

    def tick(self, n: int = 1) -> None:
        """Advance by `n` units. Cheap, and safe to call thousands of times."""

    def end(self) -> None:
        """Dismiss. Called on success, failure and abandonment alike (FR-020)."""


class NullSink:
    """The default. Every method is a no-op, so `progress=None` is free."""


def predicted_ms(total_units: int, units_per_second: float) -> float:
    """Anticipated duration for an operation of a known size (FR-014a)."""


def warrants_indicator(total_units: int | None, units_per_second: float) -> bool:
    """True when the anticipated cost clears PROGRESS_THRESHOLD_MS.

    `total_units` None (size unknowable) returns False: such an operation is
    covered by the elapsed-time fallback, not by up-front display (FR-014d).
    """


@contextmanager
def reporting(sink, label: str, total: int | None = None):
    """`begin` on entry, `end` on exit through any path, including an exception."""
```

Guarantees:

- `NullSink` and `progress=None` are indistinguishable from today's behaviour:
  no allocation, no timing, no branch that the walk can observe (FR-022, FR-045).
- `tick` never raises. A sink whose display has already been dismissed absorbs
  further ticks silently — a nested walk that outlives its indicator must not
  take the operation down with it.
- `end` is idempotent.

## `Lib/ui/progress_indicator.py`

```python
class QtProgressSink:
    """One modal indicator for the whole application (FR-021).

    - Modal, with no cancel affordance: cancellation is out of scope, and wizard
      input is blocked for the duration (FR-018).
    - `tick` advances the bar and pumps the event loop, so the window keeps
      repainting and the OS never reports it unresponsive (FR-018, SC-002).
    - Drawn from the active palette, never from hard-coded colour, so a wait
      entered in dark mode shows a dark indicator.
    """

    def begin(self, label: str, total: int | None = None) -> None:
        """Show, or re-label an indicator that is already up (FR-021).

        With `total`, determinate from the first frame (FR-014c). Without,
        indeterminate but visibly animating (FR-017).
        """

    def tick(self, n: int = 1) -> None:
        """Advance, pump, and degrade to indeterminate on overrun.

        Pumping is throttled so a million-tick walk does not spend its time in
        the event loop. Exceeding `total` switches the bar to indeterminate
        rather than displaying over 100%.
        """

    def end(self) -> None:
        """Dismiss, restoring an outer indicator's label if one was nested."""


def deferred(label: str, total: int | None = None) -> QtProgressSink:
    """A sink that shows nothing until PROGRESS_THRESHOLD_MS has elapsed.

    This is the elapsed-time fallback (FR-014b). An operation that finishes
    first displays nothing at all -- no flash, no flicker (FR-019).
    """


def immediate(label: str, total: int) -> QtProgressSink:
    """A sink that is on screen before the work starts (FR-014a).

    For an operation whose cheap count predicted a wait past the threshold. The
    operator never sees a still window ahead of the indicator (SC-001b).
    """
```

## Covered operations (FR-023, enumerated explicitly)

Every row is wired; the trigger column is what the operator actually experiences.

| # | Operation | Label shown | Total | Trigger |
|---|---|---|---|---|
| 1 | Bind source project | `Opening source project…` | — | elapsed |
| 2 | Bind target project | `Opening target project…` | — | elapsed |
| 3 | Custom-fields enumeration | `Reading custom fields…` | list count | anticipated |
| 4 | Phonology enumeration | `Reading phonology…` | list count | anticipated |
| 5 | Affix enumeration | `Reading affixes…` | entry count | anticipated |
| 6 | Stem enumeration | `Reading stems…` | entry count | anticipated |
| 7 | Skeleton enumeration | `Reading morphology skeleton…` | entry count | anticipated |
| 8 | Dependency enumeration | `Reading grammatical dependencies…` | entry count | anticipated |
| 9 | Entry-type enumeration | `Reading lexical-entry types…` | list count | anticipated |
| 10 | Rules enumeration | `Reading rules…` | list count | anticipated |
| 11 | Texts enumeration | `Reading texts…` | text count | anticipated |
| 12 | Dry-run plan assembly | `Building the transfer plan…` | selected categories | anticipated |
| 13 | Execute-move write | `Writing to the target project…` | plan actions | anticipated |

Labels are operator vocabulary, not internal vocabulary (FR-015): no class name,
no category enum value, no "inventory".

## Builder signatures (`Lib/selection.py`)

Each gains one keyword-only, defaulted parameter. No positional signature
changes, so every existing call site is untouched.

```python
def build_pos_grouped_inventory(source, target=None, want_affix=True, *, progress=None): ...
def build_skeleton_inventory(source, affix_picks, target=None, *, progress=None): ...
def build_deps_inventory(source, affix_picks, target=None, stem_picks=None, *, progress=None): ...
def build_phonology_inventory(source, target=None, *, orphan_nc_guids=None, progress=None): ...
def build_rules_inventory(source, target=None, *, progress=None): ...
def build_entry_types_inventory(source, target=None, *, progress=None): ...
def build_text_inventory(source, target=None, *, progress=None): ...
```

`progress=None` means no sink: the walk runs exactly as it does today and returns
the identical inventory. This is the equality FR-045 and SC-011 assert.
