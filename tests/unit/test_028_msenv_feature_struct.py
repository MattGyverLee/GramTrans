"""Unit tests for feature 028 (Affix-Allomorph Morphosyntax Fidelity):
reproduction of the `MoAffixAllomorph.MsEnvFeaturesOA` owned feature structure
(US3) — deep-copy of the owned `IFsFeatStruc` with its feature-value
specifications resolved against the target feature system (reusing feature
031's closed-feature machinery), reporting unresolvable/complex values.

See:
- specs/028-affix-allomorph-morphosyntax/spec.md (US3)
- specs/028-affix-allomorph-morphosyntax/research.md (R3)
- specs/028-affix-allomorph-morphosyntax/contracts/affix-msenv-reproduction.md

T003 SCAFFOLD (Phase 1): import-smoke only. The RED-before-GREEN deep-copy
tests are authored in Phase 5 (US3, T010).
"""

from gramtrans.Lib import owned


def test_028_msenv_features_dispatch_present():
    """The MsEnvFeaturesOA leg is reproduced through the shared 028 dispatch
    seam. Import-smoke: the dispatch entry points exist."""
    assert callable(owned.reproduce_moaffix_msenv_data)
    assert callable(owned._plan_moaffix_msenv_decisions)
