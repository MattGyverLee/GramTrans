"""Issue #22 audit follow-up: NFC-normalised form matching in selection."""
from gramtrans.Lib import selection

DECOMP = "é"   # e + combining acute
PRECOMP = "é"


def test_norm_form_unifies_nfc_nfd_case_and_space():
    assert selection._norm_form(DECOMP) == selection._norm_form(PRECOMP)
    assert selection._norm_form("  É ") == selection._norm_form(DECOMP)


def test_entry_status_similar_across_normalisation():
    forms = {selection._norm_form(PRECOMP)}
    assert selection._entry_status("g1", DECOMP, set(), forms) == "similar"
    assert selection._entry_status("g1", "zzz", set(), forms) == "new"


def test_suggested_target_guid_across_normalisation():
    cand = selection.SimilarCandidate(target_guid="t1", form=PRECOMP, gloss=())
    m = {selection._norm_form(PRECOMP): (cand,)}
    assert selection._suggested_target_guid_for(DECOMP, m) == "t1"
