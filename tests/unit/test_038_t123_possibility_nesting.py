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

def test_all_three_sites_cast_the_owner_before_reading_classname():
    """The fix, asserted where it has to hold. `ICmObject(src_obj).Owner` is
    not enough -- the value it RETURNS needs the cast."""
    for fn in _SITES:
        code = _code(fn)
        assert "owner = ICmObject(owner)" in code, fn.__name__


def test_no_site_reads_classname_off_an_uncast_owner():
    """The shape that caused it, asserted absent: `.Owner` assigned and then
    `ClassName` read with no intervening cast."""
    for fn in _SITES:
        code = _code_no_comments(fn)
        m = re.search(
            r"owner = ICmObject\(src_obj\)\.Owner\s*\n(.*?)owner_class",
            code, re.S)
        assert m, fn.__name__
        between = m.group(1)
        assert "ICmObject(owner)" in between, fn.__name__


def test_the_cast_tolerates_a_null_owner():
    """A top-level possibility has no owner of interest; casting None must not
    become a new crash on the ordinary path."""
    for fn in _SITES:
        code = _code(fn)
        assert "if owner is not None:" in code, fn.__name__


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
    which is how it got to three in the first place."""
    src = inspect.getsource(categories)
    assert src.count("owner = ICmObject(src_obj).Owner") == 3
    assert src.count("owner = ICmObject(owner)") == 3
