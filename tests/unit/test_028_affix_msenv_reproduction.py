"""Unit tests for feature 028 (Affix-Allomorph Morphosyntax Fidelity):
reproduction of three of the four `MoAffixAllomorph`/`MoAffixForm`
morphosyntactic-environment field families —

- `MsEnvPartOfSpeechRA` (US1, POS reference),
- `InflectionClassesRC` (US2, inflection-class references, read from the
  `IMoAffixForm` parent),
- `PositionRS` (US4, ordered infix-position environment references).

(`MsEnvFeaturesOA` — US3, owned feature structure — lives in
`test_028_msenv_feature_struct.py`.)

See:
- specs/028-affix-allomorph-morphosyntax/spec.md (US1/US2/US4/US5)
- specs/028-affix-allomorph-morphosyntax/contracts/affix-msenv-reproduction.md
- specs/028-affix-allomorph-morphosyntax/data-model.md

T002 SCAFFOLD (Phase 1): import-smoke only — assert the module under test and
its 028 dispatch seam import cleanly. The RED-before-GREEN tests are authored
per user story in Phase 3 (US1, T006), Phase 4 (US2, T008), Phase 6 (US4, T012),
and Phase 7 (US5, T014).
"""

from gramtrans.Lib import owned


def test_028_dispatch_seam_present():
    """T005 adds the reproduce leg (`reproduce_moaffix_msenv_data`) and its
    read-only Preview twin (`_plan_moaffix_msenv_decisions`). Import-smoke: the
    module and both dispatch entry points exist and are callable."""
    assert callable(owned.reproduce_moaffix_msenv_data)
    assert callable(owned._plan_moaffix_msenv_decisions)
