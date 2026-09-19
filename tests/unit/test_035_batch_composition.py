"""Feature 035 -- T035: pin WHICH projects a batch runs.

FR-160 specifies batch 1's composition as exactly the three pilot projects
with prior recorded historical results ("Ejagham Mini", "Esperanto",
"Mbugwe LizzieHC practice"), so that batch's numbers can be set beside the
historical ones. The driver's derived composition -- the ledger's not-yet-passed
list in corpus-enumeration order, capped at --batch-size -- cannot express that:
against the 84 admitted sources on this machine it yields the first three names
alphabetically, which is not the pilot set.

So the composition is a caller decision with two forms, and this file pins the
part that is easy to get quietly wrong:

  * an explicitly named composition is used VERBATIM and IN ORDER, and is NOT
    silently truncated by the --batch-size default;
  * FR-159's canary is prepended when absent under EITHER form, so naming a
    composition is not a way to drop the canary out of a batch;
  * the label saying which form produced the batch is returned alongside it,
    for the run record -- never inferred later from the batch's contents.

Offline: ``compose_batch`` reads the frozen manifest and the ledger and nothing
else. No FLEx project, no corpus enumeration, no filesystem.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep.corpus import CANARY_PROJECTS  # noqa: E402
from debug.run_fullcopy_sweep import compose_batch  # noqa: E402

#: FR-160, transcribed independently of the module under test.
PILOTS = ("Ejagham Mini", "Esperanto", "Mbugwe LizzieHC practice")

#: A stand-in for the 84-project frozen manifest: sorted, as
#: ``freeze_source_manifest`` returns it, and with the pilots NOT at the front.
FROZEN = tuple(sorted(PILOTS + ("Aweti", "Hdi", "Nyika", "Sena 3")))


class _Ledger:
    """The two-method slice of ``Ledger`` that ``compose_batch`` touches."""

    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {})

    def get(self, name):
        return self._statuses.get(name)


def test_pilots_are_not_what_the_derived_composition_would_pick():
    """The premise. If the derived form already yielded the pilots, FR-160
    would need no explicit composition and this whole surface would be dead
    code -- so assert the gap the flag exists to close."""
    derived, _ = compose_batch(FROZEN, _Ledger(), only=None, batch_size=3,
                               canary=CANARY_PROJECTS[0])
    assert set(derived) != set(PILOTS)


def test_explicit_composition_is_used_verbatim_and_in_order():
    batch, label = compose_batch(FROZEN, _Ledger(), only=list(PILOTS),
                                 batch_size=3, canary=CANARY_PROJECTS[0])
    assert batch == list(PILOTS)
    assert "explicit" in label


def test_explicit_composition_is_not_truncated_by_batch_size():
    """A caller naming four sources under the default size of three must not
    silently measure three of them."""
    named = list(PILOTS) + ["Sena 3"]
    batch, _ = compose_batch(FROZEN, _Ledger(), only=named, batch_size=3,
                             canary=CANARY_PROJECTS[0])
    assert batch == named


def test_canary_is_prepended_to_an_explicit_composition_that_omits_it():
    """FR-159: the canary re-runs in EVERY batch, whatever the ledger says and
    whatever the caller named."""
    canary = CANARY_PROJECTS[0]
    named = ["Sena 3", "Hdi"]
    assert canary not in named
    batch, _ = compose_batch(FROZEN, _Ledger(), only=named, batch_size=2,
                             canary=canary)
    assert batch == [canary] + named


def test_canary_present_in_the_named_composition_is_not_duplicated():
    batch, _ = compose_batch(FROZEN, _Ledger(), only=list(PILOTS),
                             batch_size=3, canary=CANARY_PROJECTS[0])
    assert batch.count(CANARY_PROJECTS[0]) == 1


def test_derived_composition_still_honours_the_ledger_and_the_cap():
    passed = {n: {"status": "passed"} for n in ("Aweti", "Hdi")}
    batch, label = compose_batch(FROZEN, _Ledger(passed), only=None,
                                 batch_size=3, canary=CANARY_PROJECTS[0])
    assert "derived" in label
    assert len(batch) == 3
    assert "Aweti" not in batch and "Hdi" not in batch


def test_derived_composition_includes_the_canary_even_when_it_passed():
    """The canary having passed is exactly when a regression in it would
    otherwise go unnoticed until the end of the corpus."""
    canary = CANARY_PROJECTS[0]
    batch, _ = compose_batch(FROZEN, _Ledger({canary: {"status": "passed"}}),
                             only=None, batch_size=3, canary=canary)
    assert canary in batch


def test_an_empty_only_list_falls_back_to_the_derived_composition():
    """``--only`` with no names is argparse-indistinguishable from an operator
    who meant to name nothing; it must not produce an empty batch that reports
    a clean run over zero projects."""
    batch, label = compose_batch(FROZEN, _Ledger(), only=[], batch_size=3,
                                 canary=CANARY_PROJECTS[0])
    assert "derived" in label
    assert batch
