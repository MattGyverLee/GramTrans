"""Issue #22 live gate -- NFC/NFD forms match in target-status classification.

READ-ONLY: opens the real `Ejagham Mini` read-only (never written). Takes real
target forms, re-spells them decomposed (NFD) and precomposed (NFC), and checks
`_entry_status` classifies both as "similar" against the live target sets.

    set FLEXLIBS_REQUIRE_LIVE=1 && set PYTHONPATH=src && python -m pytest \
        tests/integration/test_issue22_nfc_live.py -v -s
"""
import os
import unicodedata

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]
if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1", allow_module_level=True)


def test_nfc_nfd_similar_live():
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    from gramtrans.Lib import selection
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName="Ejagham Mini", writeEnabled=False)
    try:
        guids, forms, cands, _ = selection._build_target_sets(proj, want_affix=False)
        assert forms, "[FAIL] no live target forms"
        # a form whose spelling changes under NFD (accented), else synthesize
        accented = [c.form for cs in cands.values() for c in cs
                    if unicodedata.normalize("NFD", c.form) != c.form]
        base = accented[0] if accented else next(iter(cands.values()))[0].form
        nfd = unicodedata.normalize("NFD", base) if accented else base + "́"
        nfc = unicodedata.normalize("NFC", base) if accented else base + "́"
        if not accented:  # synthetic: target side must hold the NFC spelling
            forms = set(forms) | {selection._norm_form(nfc)}
        print("[INFO] accented live form:", bool(accented), repr(base))
        assert selection._entry_status("zz", nfd, set(), forms) == "similar"
        assert selection._entry_status("zz", nfc, set(), forms) == "similar"
    finally:
        proj.CloseProject()
