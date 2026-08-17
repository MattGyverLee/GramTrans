"""T031 / FR-022, FR-027, FR-054 — what the gate says, and what it must not.

Wording is the mechanism here, not decoration. FR-027 exists because the
FlexTools subtitle ends "changes can be undone in FLEx with Ctrl+Z" — true
there, false here — and a user who reads that sentence in the standalone has
been actively misled about whether they can back out.

So this file asserts two things:

* the **content** the gate must carry (irreversibility, back up first, the
  Send/Receive recovery path);
* the **claim it must never make**, checked by finding every mention of undo
  and requiring each one to be negated.

The negation check is deliberately not a bare `"undo" not in text` — "this
cannot be undone" is the clearest possible phrasing of FR-022 and contains the
word. What is forbidden is the *affirmative* claim.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

TARGET = "Ejagham Full GT-Test"


@pytest.fixture(scope="session")
def qapp():
    from PyQt6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture()
def texts(qapp):
    from gramtrans.standalone.gate import StandaloneConfirmationGate, warning_text

    return {
        "warning": warning_text(TARGET),
        "subtitle": StandaloneConfirmationGate().finish_page_subtitle(),
    }


# ---------------------------------------------------------------------------
# FR-022 / FR-054 — what must be said
# ---------------------------------------------------------------------------

def test_the_warning_says_the_change_cannot_be_undone_in_the_application(texts):
    lowered = texts["warning"].lower()
    assert "cannot be undone" in lowered
    assert "gramtrans" in lowered, (
        "FR-022 is 'cannot be undone *from within the application*' — the "
        "sentence has to be scoped, or a Send/Receive user reads it as "
        "'nothing can be recovered', which is not true"
    )


def test_the_warning_tells_the_user_to_back_up_first(texts):
    lowered = texts["warning"].lower()
    assert "back" in lowered and "up" in lowered
    assert "backup" in lowered or "back up" in lowered


def test_the_warning_carries_the_send_receive_recovery_path(texts):
    """FR-054 — stated, not enforced (research R15)."""
    lowered = texts["warning"].lower()
    assert "send/receive" in lowered
    assert "delete" in lowered, "the recovery path is delete-local-then-receive"
    assert "receive it again" in lowered or "receive again" in lowered


def test_the_warning_names_the_target_project(texts):
    assert TARGET in texts["warning"]
    # Twice: once in the consequence, once as the string to type. A user who
    # skims the prose still has the name in front of them at the field.
    assert texts["warning"].count(TARGET) >= 2


def test_the_warning_asks_for_the_name_typed_exactly(texts):
    lowered = texts["warning"].lower()
    assert "type" in lowered
    assert "exactly" in lowered


def test_the_subtitle_states_irreversibility(texts):
    lowered = texts["subtitle"].lower()
    assert "cannot undo" in lowered or "cannot be undone" in lowered
    assert "backup" in lowered or "back up" in lowered


# ---------------------------------------------------------------------------
# FR-027 — what must never be said
# ---------------------------------------------------------------------------

_UNDO_MENTION = re.compile(r"\b(undo|undone|undoable|reversible|reversed)\b", re.I)

#: Text immediately before an undo mention that makes it a denial rather than
#: a promise. Checked over a window ending at the mention.
_NEGATORS = ("cannot", "can not", "can't", "no ", "not ", "never", "unable")


def _affirmative_undo_claims(text: str):
    """Every undo mention that is *not* negated by nearby wording."""
    offenders = []
    for m in _UNDO_MENTION.finditer(text):
        window = text[max(0, m.start() - 40): m.start()].lower()
        if not any(neg in window for neg in _NEGATORS):
            offenders.append((m.group(0), text[max(0, m.start() - 40): m.end() + 20]))
    return offenders


@pytest.mark.parametrize("key", ["warning", "subtitle"])
def test_no_ctrl_z_claim_anywhere(texts, key):
    assert "ctrl+z" not in texts[key].lower(), (
        f"the {key} mentions Ctrl+Z — there is no undo stack in this host, so "
        "that sentence is false (FR-027)"
    )


@pytest.mark.parametrize("key", ["warning", "subtitle"])
def test_no_affirmative_undo_claim(texts, key):
    offenders = _affirmative_undo_claims(texts[key])
    assert not offenders, (
        f"the {key} makes an un-negated undo claim: {offenders}"
    )


def test_the_negation_matcher_would_actually_fire():
    """A green result above means nothing if the matcher cannot go red."""
    assert _affirmative_undo_claims("Changes can be undone in FLEx with Ctrl+Z.")
    assert _affirmative_undo_claims("This write is reversible.")
    # ...and does not fire on the phrasings the gate legitimately uses.
    assert not _affirmative_undo_claims("This cannot be undone from within GramTrans.")
    assert not _affirmative_undo_claims("There is no Undo in this application.")
    assert not _affirmative_undo_claims("GramTrans cannot undo the write.")


def test_the_flextools_default_still_makes_the_claim_this_one_forbids(qapp):
    """The two gates must differ *here*, and only here, on purpose.

    If this ever fails, either the FlexTools subtitle changed (an SC-013
    regression, caught in `test_034_flextools_contract.py`) or the two hosts
    have been given the same text — which would mean one of them is lying.
    """
    from gramtrans.Lib.gate import AlwaysSatisfiedGate
    from gramtrans.standalone.gate import StandaloneConfirmationGate

    flextools = AlwaysSatisfiedGate().finish_page_subtitle()
    standalone = StandaloneConfirmationGate().finish_page_subtitle()

    assert "Ctrl+Z" in flextools
    assert "Ctrl+Z" not in standalone
    assert flextools != standalone
