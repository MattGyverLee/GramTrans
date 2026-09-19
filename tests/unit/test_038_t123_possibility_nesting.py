"""Feature 038 T123: the right number of variant types, in the wrong tree.

THE CLAUSE NO TASK OWNED. T118 found `LexEntryInflType` count-MATCHED (7 -> 7
on ejagham) while its items MOVE between `CmPossibility.SubPossibilitiesOS` and
`CmPossibilityList.Possibilities`: **6 nested / 1 top-level arrives as 2 nested
/ 5 top-level**. Variant types arrive as SIBLINGS of their parent instead of
children of it. The census is structurally blind to this -- the count is right
and only the shape is wrong -- so its acceptance is a NESTING assertion, never
a count.

THE CAUSE IS A MISSING CAST, AND IT IS T088'S DEFECT IN A THIRD PLACE.
`variant_types_execute_action` discriminated nested-vs-top-level with:

    owner = ICmObject(src_obj).Owner
    owner_class = getattr(owner, "ClassName", "")
    if owner_class and "EntryType" in owner_class:
        src_owner_guid = _guid_str_from(owner)

`.Owner` yields an `ICmObjectOrId` PROXY on which `ClassName` does not surface
-- the comment two lines above the original code says exactly that about
`src_obj`, and the cast was applied to `src_obj` rather than to what it
returns. So `owner_class` read `""` for every object, `src_owner_guid` stayed
None, and every nested possibility took the top-level branch. Wave 1's own
probe hit the same proxy behaviour on its first run
(`journal/T114-T118-every-row-was-a-bucket.md`: "`OwningFlid` and `Owner` are
declared on `ICmObject` and are INVISIBLE on the `ICmObjectOrId` proxies").

THREE SITES, because the same block was copied twice with "(see variant_types
for rationale)": variant types, complex-form types, semantic domains.

THE SECOND DEFECT, EXPOSED BY FIXING THE FIRST. With the cast working, the
parent lookup actually runs -- and its failure path had already created the
object and then `return None`d, abandoning it unowned. That is the orphan risk
`_safe_add_to_owner` exists to prevent, reached by the one path that never
called it. It is now a reported demotion to top level: losing the OBJECT is
worse than losing its NESTING.

Host-free: duck fakes only.
"""
from __future__ import annotations

import inspect
import re

from gramtrans.Lib import categories


_SITES = (
    categories.variant_types_execute_action,
    categories.complex_form_types_execute_action,
    categories.semantic_domains_execute_action,
)


def _code(fn):
    """Source with the docstring removed, so a claim about the CODE is not
    satisfied by prose that merely mentions the same words."""
    src = inspect.getsource(fn)
    parts = src.split('"""')
    return parts[2] if len(parts) > 2 else src


def _code_no_comments(fn):
    """`_code` with `#` comment lines dropped too. The comments explaining
    these fixes necessarily QUOTE the constructs being asserted absent, so a
    substring test over them would always fail."""
    return "\n".join(
        line for line in _code(fn).split("\n")
        if not line.strip().startswith("#"))


# --------------------------------------------------------------------------
# The cast
# --------------------------------------------------------------------------

def _code_no_comments_module():
    """The whole module's source with comment lines removed -- so a test
    cannot pass because an identifier appears in prose EXPLAINING that it was
    removed. That exact false-green happened twice in this feature."""
    return "\n".join(
        ln for ln in inspect.getsource(categories).splitlines()
        if not ln.lstrip().startswith("#"))


def test_all_three_sites_use_the_shared_nesting_helper():
    """CONSOLIDATED 2026-08-28. These tests used to assert the INLINE shape of
    T123's cast fix (`owner = ICmObject(owner)` present at each site). That fix
    was correct and INSUFFICIENT: the line immediately after it tested
    `"EntryType" in owner_class`, which is False for `"LexEntryInflType"` --
    the substring is not contiguous -- so the correctly-cast owner was thrown
    away and every nested item was demoted anyway.

    Three copies of a predicate is how this codebase keeps acquiring the same
    bug in parallel functions, so the predicate now lives in ONE function and
    the sites call it. Asserting the call keeps that true; the predicate's own
    behaviour is asserted on values below.
    """
    for fn in _SITES:
        code = _code_no_comments(fn)
        assert "_source_possibility_parent_guid(src_obj)" in code, fn.__name__


def test_no_site_reads_nesting_off_a_class_NAME_any_more():
    """The shape that caused it, asserted absent module-wide: a substring test
    against a class name. No amount of casting rescues it.

    ASSERTS THE PREDICATE, NOT THE IDENTIFIER. The first draft of this test
    asserted `'"EntryType" in' not in src` and failed on the DOCSTRING that
    explains the defect -- the third time in this session that a source-text
    assertion tripped over prose about the very thing it was checking. The
    lesson is now in the assertion itself: match the executable shape.
    """
    src = _code_no_comments_module()
    assert 'if owner_class and "EntryType" in owner_class:' not in src
    assert re.search(r"^\s*if .*\bin owner_class\s*:", src, re.M) is None


def test_the_helper_tolerates_a_null_owner():
    """A top-level possibility has no owner of interest; the helper must
    return None rather than raise, on the ordinary path."""
    class _NoOwner:
        OwningFlid = categories._CMPOSSIBILITY_SUBPOSSIBILITIES_FLID
        Owner = None

    assert categories._source_possibility_parent_guid(_NoOwner()) is None
    assert categories._source_possibility_parent_guid(None) is None


# --------------------------------------------------------------------------
# The orphan, exposed by fixing the cast
# --------------------------------------------------------------------------

def test_a_missing_parent_no_longer_abandons_the_created_object():
    """`return None` after a successful `Create(Guid)` leaves an unowned
    object. Every site must now place it and report instead."""
    for fn in _SITES:
        code = _code_no_comments(fn)
        m = re.search(r"if target_parent_raw is None:\s*\n(.*?)\n\s*_safe_add_to_owner",
                      code, re.S)
        assert m, fn.__name__
        assert "return None" not in m.group(1), fn.__name__


def test_the_demotion_is_reported():
    for fn in _SITES:
        assert "_log_possibility_demoted" in _code(fn), fn.__name__


def test_log_possibility_demoted_names_all_three_facts(caplog):
    """What was demoted, what it should have nested under, and that no census
    row will show it -- the last part is the point, since the count is
    unchanged."""
    import logging
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.categories"):
        categories._log_possibility_demoted(
            "ILexEntryInflTypeFactory", "child-guid", "parent-guid")
    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "child-guid" in msg
    assert "parent-guid" in msg
    assert "TOP LEVEL" in msg
    assert "census" in msg


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------

def test_the_fix_landed_at_exactly_three_sites():
    """The block was copied twice under "(see variant_types for rationale)".
    Fixing one and not the others would leave the same bug in two places --
    which is how it got to three in the first place.

    Now asserted as three CALLS to one helper rather than three copies of one
    block: the duplication was itself the hazard, and the second defect
    (`"EntryType" in ...`) proved it by surviving in all three copies at once.
    """
    src = _code_no_comments_module()
    calls = [ln for ln in src.splitlines()
             if "_source_possibility_parent_guid(src_obj)" in ln
             and not ln.lstrip().startswith("def ")]
    assert len(calls) == 3, calls


def test_the_nesting_predicate_keys_on_the_flid_not_the_class_name():
    """THE REGRESSION TEST, ON VALUES, FOR THE DEFECT THAT SURVIVED T123.

    Measured live on `Ejagham W Mini` 2026-08-28 (read-only): 6 of its 7
    `LexEntryInflType` objects are `OwningFlid=7004` owned by an object whose
    `ClassName` is `"LexEntryInflType"`; 1 is `OwningFlid=8008` under the
    `CmPossibilityList`. The old predicate asked whether `"EntryType"` was a
    substring of the owner's class name -- False for all 6 -- so all 6 were
    demoted to top level. T124 measured the result per GUID: ejagham arrives
    2 nested / 5 top-level with 4 NAMED demotions (`Perfective`, `Hortative`,
    `Conditional`, `Retrospective`).

    A flid is what LCM actually keyed on, and it is class-agnostic, so a
    sibling possibility list cannot acquire this bug by being named
    differently.
    """
    class _Owner:
        Guid = "parent-guid"

    class _Nested:
        OwningFlid = 7004          # CmPossibility.SubPossibilities
        Owner = _Owner()

    class _TopLevel:
        OwningFlid = 8008          # CmPossibilityList.Possibilities
        Owner = _Owner()

    assert categories._source_possibility_parent_guid(
        _Nested()) == "parent-guid"
    assert categories._source_possibility_parent_guid(_TopLevel()) is None


def test_the_substring_that_was_never_a_substring():
    """Pinned as a plain fact, because it IS the whole defect and it reads as
    though it should be true."""
    assert "EntryType" not in "LexEntryInflType"
    assert "EntryType" in "LexEntryType"
