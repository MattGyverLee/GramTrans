"""Write-first unit tests for `walk_owned_children` (feature 024 US3, T027-T028).

Covers the `OwnedObjectSpec` rows in
`specs/024-lexicon-reference-fidelity/data-model.md` and the behavior
contract in `specs/024-lexicon-reference-fidelity/contracts/owned-object-walk.md`:

- Sense.``ExamplesOS`` (ordered owned) via ``ILexExampleSentenceFactory``,
  each example owning ``TranslationsOC`` (unordered owned, ``ICmTranslation``)
  via ``ICmTranslationFactory``; child ref ``ICmTranslation.TypeRA`` ->
  ``lp.TranslationTagsOA``. Examples also carry ref fields
  ``DoNotPublishInRC``/``PublishIn`` -> ``PublicationTypesOA``.
- Entry.``PronunciationsOS`` (ordered owned) via ``ILexPronunciationFactory``.
- Entry.``EtymologyOS`` (ordered owned) via ``ILexEtymologyFactory``; ref
  ``ILexEtymology.LanguageRS`` (seq) -> ``lp.LexDbOA.LanguagesOA``.
- Sense.``SensesOS`` (ordered owned, recurse) via ``ILexSenseFactory`` --
  re-entering the full sense-copy path so a sub-sense gets the same
  reference + owned treatment as a top-level sense.
- FR-009: anything unreproducible appends exactly one `DroppedItemRecord`
  to the `dropped` collector -- never silent.

TDD RED STATE (this cycle): `walk_owned_children` IS implemented, but it
drives every `OWNED_OBJECT_MAP` row through one uniform
`factory.Create(guid, new_owner)` call. MCP verification against a live
Ejagham Mini project confirmed this uniform shape is wrong for 3 of the 5
owned-child factories:

  - `ICmTranslationFactory` has NO `(guid, owner)` overload -- only
    `Create(owner, translationType)` / `Create(owner, translationType, guid)`,
    with the type required UP FRONT.
  - `ILexPronunciationFactory` / `ILexEtymologyFactory` have only
    `Create()` / `Create(Guid)` -- no owner parameter; the caller must
    separately `.Add()` the unowned result to the owning collection.

The fakes below now model each factory's REAL signature (see the
"Child factories" section) and reject the wrong arity/shape, so
`test_examples_reproduced_ordered_with_translations_and_publication_refs`,
`test_pronunciations_reproduced_under_entry_ordered`, and
`test_etymology_reproduced_under_entry_with_language_rs_resolved` are
expected to FAIL against the current uniform-Create `walk_owned_children`
(translations/pronunciations/etymologies fail to create, or land unowned).
Do NOT fix `walk_owned_children`/`OWNED_OBJECT_MAP` here -- this file only
strengthens the write-first contract to the MCP-verified real shapes,
matching the style of `tests/unit/test_reference_resolver.py`.
`test_recursive_sub_senses_reproduced_ordered_with_own_ref_fields_resolved`
(sub-senses, OWNER_TAKING like examples) is expected to keep PASSING.

Fake style: modeled on `test_reference_resolver.py`'s `_FakePossibility` /
`_FakeMultiString` / `_FakeTargetList` (reused here, same shape, for the
child reference fields -- translation `TypeRA`, example
`DoNotPublishInRC`/`PublishIn`, etymology `LanguageRS`) plus
`test_reference_create_paths.py`'s `_FakeCollection` (`.Add()` + iterable,
reused here as `_FakeOwningCollection` for every owned/reference collection
on a freshly-created target-side object) and `Lib/categories.py`'s
production `_walk_lex_entry_closure` shape for `ctx` (`context.source_handle`,
`context.target_handle`, `context._ws_map`) and the
`context.source_handle.<X>.GetSyncableProperties` /
`target.<X>.ApplySyncableProperties` sync-ops pattern.
"""
from __future__ import annotations

from gramtrans.Lib import owned
from gramtrans.Lib.models import DroppedItemRecord

WS_EN = 100


# ============================================================================
# Reference-field fakes -- reused shape from test_reference_resolver.py
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakePossibility:
    """Duck-typed ICmPossibility -- same shape as
    test_reference_resolver.py's fake, reused here for the child reference
    fields the owned walk must route through `references.decide_reference`/
    `apply_reference` (translation `TypeRA`, example `DoNotPublishInRC`/
    `PublishIn`, etymology `LanguageRS`)."""

    def __init__(self, guid, name="", abbr="", is_protected=False, owner=None):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})
        self.Abbreviation = _FakeMultiString({WS_EN: abbr} if abbr else {})
        self.IsProtected = is_protected
        self.Owner = owner
        self.OwningPossibility = owner


class _FakeTargetList:
    """Fake ICmPossibilityList: a flat container the resolver searches by
    GUID, or `None` for "list absent" (see test 5, dropped-record case)."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


# ============================================================================
# Owned-collection fake -- reused shape from test_reference_create_paths.py's
# `_FakeCollection`: iterable + `.Add()`-able, used for every owned/reference
# collection on a freshly-created target-side object (ExamplesOS,
# TranslationsOC, PronunciationsOS, EtymologyOS, SensesOS, and the resolved
# DoNotPublishInRC/PublishIn/LanguageRS reference collections).
# ============================================================================

class _FakeOwningCollection:
    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def Add(self, item):
        self._items.append(item)


# ============================================================================
# Source-side owned-child fakes (read-only; the walk iterates these)
# ============================================================================

class _FakeTranslation:
    """Fake ICmTranslation: owned by LexExampleSentence.TranslationsOC;
    carries Translation content + the child ref field `TypeRA`."""

    def __init__(self, guid, text="", type_ra=None):
        self.Guid = guid
        self.guid = guid
        self.Translation = _FakeMultiString({WS_EN: text} if text else {})
        self.TypeRA = type_ra


class _FakeExample:
    """Fake ILexExampleSentence: owns TranslationsOC; carries Example
    content plus ref fields DoNotPublishInRC/PublishIn -> PublicationTypesOA."""

    def __init__(self, guid, text="", translations=(),
                 do_not_publish_in=(), publish_in=()):
        self.Guid = guid
        self.guid = guid
        self.Example = _FakeMultiString({WS_EN: text} if text else {})
        self.TranslationsOC = list(translations)
        self.DoNotPublishInRC = list(do_not_publish_in)
        self.PublishIn = list(publish_in)


class _FakePronunciation:
    def __init__(self, guid, form=""):
        self.Guid = guid
        self.guid = guid
        self.Form = _FakeMultiString({WS_EN: form} if form else {})


class _FakeEtymology:
    """Fake ILexEtymology: carries Form content + the seq ref field
    `LanguageRS` -> `lp.LexDbOA.LanguagesOA`."""

    def __init__(self, guid, form="", language_rs=()):
        self.Guid = guid
        self.guid = guid
        self.Form = _FakeMultiString({WS_EN: form} if form else {})
        self.LanguageRS = list(language_rs)


class _FakeSourceSense:
    def __init__(self, guid, gloss="", examples=(), sub_senses=(), sense_type=None):
        self.Guid = guid
        self.guid = guid
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.ExamplesOS = list(examples)
        self.SensesOS = list(sub_senses)
        self.SenseTypeRA = sense_type


class _FakeSourceEntry:
    def __init__(self, guid, pronunciations=(), etymologies=()):
        self.Guid = guid
        self.guid = guid
        self.PronunciationsOS = list(pronunciations)
        self.EtymologyOS = list(etymologies)


# ============================================================================
# Target-side ("new") owner fakes -- freshly created, empty collections the
# walk is expected to populate.
# ============================================================================

class _NewSense:
    def __init__(self, guid="new-sense-guid"):
        self.Guid = guid
        self.guid = guid
        self.ExamplesOS = _FakeOwningCollection()
        self.SensesOS = _FakeOwningCollection()
        self.SenseTypeRA = None


class _NewEntry:
    def __init__(self, guid="new-entry-guid"):
        self.Guid = guid
        self.guid = guid
        self.PronunciationsOS = _FakeOwningCollection()
        self.EtymologyOS = _FakeOwningCollection()


# ============================================================================
# Child factories -- each fake models its OWN real LCM `Create` signature
# (MCP-verified against Ejagham Mini, live), NOT a uniform `Create(guid,
# owner)`. Only 2 of 5 are actually OWNER_TAKING that shape:
#
#   - ILexExampleSentenceFactory.Create(Guid, ILexSense owner)        -- OWNER_TAKING
#   - ILexSenseFactory.Create(Guid, ILexSense owner)  (sub-senses)     -- OWNER_TAKING
#   - ICmTranslationFactory: NO (guid, owner) overload; only
#     Create(ILexExampleSentence owner, ICmPossibility translationType)
#     / Create(owner, translationType, Guid) -- type required UP FRONT -- OWNER_PLUS_TYPE
#   - ILexPronunciationFactory: only Create() / Create(Guid) -- UNOWNED;
#     caller must then `entry.PronunciationsOS.Add(obj)`            -- UNOWNED_THEN_ADD
#   - ILexEtymologyFactory: only Create() / Create(Guid) -- UNOWNED;
#     caller must then `entry.EtymologyOS.Add(obj)`                 -- UNOWNED_THEN_ADD
#
# The OWNER_TAKING fakes still mirror the proven
# `ILexSenseFactory.Create(DotNetGuid.Parse(s_guid), new_entry)` idiom already
# used by `Lib/categories.py._walk_lex_entry_closure` for the owned
# entry->sense leg. Every fake below REJECTS the wrong arity/shape for its own
# signature so a walk that still calls the old uniform `Create(guid, owner)`
# against an OWNER_PLUS_TYPE/UNOWNED_THEN_ADD factory fails loudly (RED)
# instead of silently doing the wrong thing.
# ============================================================================

class _FakeExampleFactory:
    """OWNER_TAKING: `Create(Guid, ILexSense owner)`."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "ExamplesOS"):
            raise TypeError(
                "ILexExampleSentenceFactory.Create(guid, owner) expects "
                f"owner to be an ILexSense (ExamplesOS); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_ex = _FakeExample(guid)
        new_ex.TranslationsOC = _FakeOwningCollection()
        new_ex.DoNotPublishInRC = _FakeOwningCollection()
        new_ex.PublishIn = _FakeOwningCollection()
        owner.ExamplesOS.Add(new_ex)
        return new_ex


class _FakeTranslationFactory:
    """OWNER_PLUS_TYPE: `ICmTranslationFactory` has NO `(guid, owner)`
    overload -- only `Create(ILexExampleSentence owner, ICmPossibility
    translationType)` / `Create(owner, translationType, Guid)`. The type
    MUST be resolved and supplied up front; there is no create-then-set-type
    path. Rejects the old (guid, owner) shape (arg 1 must duck-type an
    owning example, i.e. carry `TranslationsOC`) and rejects a missing/None
    `translationType` (ValueError) -- the walk must resolve `TypeRA` via
    `references.decide_reference`/`apply_reference` BEFORE calling Create,
    not after."""

    def __init__(self):
        self.create_calls = []

    def Create(self, owner, translation_type, guid=None):
        if not hasattr(owner, "TranslationsOC"):
            raise TypeError(
                "ICmTranslationFactory.Create(owner, translationType[, guid]) "
                f"expects owner to be an ILexExampleSentence (TranslationsOC); "
                f"got {owner!r} -- looks like the old (guid, owner) shape"
            )
        if translation_type is None:
            raise ValueError(
                "ICmTranslationFactory.Create requires a non-None "
                "translationType (TypeRA) resolved BEFORE create -- there is "
                "no overload that creates a translation and sets its type "
                "afterward"
            )
        self.create_calls.append((owner, translation_type, guid))
        new_tr = _FakeTranslation(
            guid if guid is not None else "generated-tr-guid",
            type_ra=translation_type,
        )
        owner.TranslationsOC.Add(new_tr)
        return new_tr


class _FakePronunciationFactory:
    """UNOWNED_THEN_ADD: `ILexPronunciationFactory` has only `Create()` /
    `Create(Guid)` -- no owner parameter at all. Passing an extra owner
    positional (the old uniform `Create(guid, owner)` shape) is rejected by
    plain Python arity checking (this fake takes exactly one argument besides
    `self`). The created object is UNOWNED; the caller must separately do
    `entry.PronunciationsOS.Add(obj)`."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid):
        self.create_calls.append(guid)
        return _FakePronunciation(guid)


class _FakeEtymologyFactory:
    """UNOWNED_THEN_ADD: `ILexEtymologyFactory` has only `Create()` /
    `Create(Guid)` -- no owner parameter. Same arity rejection as
    `_FakePronunciationFactory`; the created object is UNOWNED and the caller
    must separately do `entry.EtymologyOS.Add(obj)`."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid):
        self.create_calls.append(guid)
        new_e = _FakeEtymology(guid)
        new_e.LanguageRS = _FakeOwningCollection()
        return new_e


class _FakeSenseFactory:
    """OWNER_TAKING: `Create(Guid, ILexSense owner)` (sub-senses)."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "SensesOS"):
            raise TypeError(
                "ILexSenseFactory.Create(guid, owner) expects owner to be "
                f"an ILexSense (SensesOS); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_s = _NewSense(guid)
        owner.SensesOS.Add(new_s)
        return new_s


# ============================================================================
# Sync-ops + project/context fakes -- mirrors the production
# `context.source_handle.Senses.GetSyncableProperties(src_sense)` /
# `target.Senses.ApplySyncableProperties(new_sense, sprops, ws_map=ws_map)`
# pattern already exercised throughout `Lib/categories.py`.
# ============================================================================

class _FakeSyncOps:
    """Records every GetSyncableProperties/ApplySyncableProperties call so a
    test can assert content actually flowed end-to-end (the `{"_marker":
    guid}` sentinel stands in for the real multi-WS props dict)."""

    def __init__(self):
        self.get_calls = []
        self.apply_calls = []

    def GetSyncableProperties(self, obj):
        self.get_calls.append(obj)
        return {"_marker": getattr(obj, "Guid", None)}

    def ApplySyncableProperties(self, obj, props, ws_map=None):
        self.apply_calls.append((obj, props, ws_map))


class _FakeLangProject:
    def __init__(self, translation_tags=None, languages=None, publication_types=None):
        self.TranslationTagsOA = (
            translation_tags if translation_tags is not None else _FakeTargetList()
        )

        class _LexDb:
            pass

        lex_db = _LexDb()
        lex_db.LanguagesOA = languages if languages is not None else _FakeTargetList()
        lex_db.PublicationTypesOA = (
            publication_types if publication_types is not None else _FakeTargetList()
        )
        self.LexDbOA = lex_db


class _FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project
        self.DefaultAnalWs = WS_EN


class _FakeProject:
    """Fake FLExProject-shaped handle: `Cache.LangProject...` for
    `references.REFERENCE_FIELD_MAP`'s `target_list_path` lambdas, the
    per-class sync-ops namespaces (`Examples`, `Translations`,
    `Pronunciations`, `Etymology`, `Senses`), and the owned-child factories
    exposed via `GetService` (the LCM service-locator idiom)."""

    def __init__(self, translation_tags=None, languages=None, publication_types=None):
        self.Cache = _FakeCache(
            _FakeLangProject(translation_tags, languages, publication_types)
        )
        self.Examples = _FakeSyncOps()
        self.Translations = _FakeSyncOps()
        self.Pronunciations = _FakeSyncOps()
        self.Etymology = _FakeSyncOps()
        self.Senses = _FakeSyncOps()

        self._factories = {
            "ILexExampleSentenceFactory": _FakeExampleFactory(),
            "ICmTranslationFactory": _FakeTranslationFactory(),
            "ILexPronunciationFactory": _FakePronunciationFactory(),
            "ILexEtymologyFactory": _FakeEtymologyFactory(),
            "ILexSenseFactory": _FakeSenseFactory(),
        }
        self.requested_services = []

    def GetService(self, name):
        self.requested_services.append(name)
        return self._factories[name]


class _FakeContext:
    """Mirrors the real `RunContext`-shaped object `_walk_lex_entry_closure`
    threads through -- `context.source_handle`, `context.target_handle`,
    `context._ws_map` -- the `ctx` parameter `walk_owned_children` receives."""

    def __init__(self, source_handle, target_handle, ws_map=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = ws_map or {}


_TAG = "tag-owned-walk"


# ============================================================================
# Case 1 -- Sense.ExamplesOS (ordered) + each example's TranslationsOC +
# example ref fields DoNotPublishInRC/PublishIn
# ============================================================================

def test_examples_reproduced_ordered_with_translations_and_publication_refs():
    type_guid = "type-guid-1"
    pub_guid = "pub-guid-1"
    target_type_item = _FakePossibility(type_guid, name="Free")
    target_pub_item = _FakePossibility(pub_guid, name="Main Dictionary")
    source_type_item = _FakePossibility(type_guid, name="Free")
    source_pub_item = _FakePossibility(pub_guid, name="Main Dictionary")

    tr1 = _FakeTranslation("tr-1", text="the free translation", type_ra=source_type_item)
    ex1 = _FakeExample(
        "ex-1", text="first example", translations=(tr1,),
        publish_in=(source_pub_item,),
    )
    tr2 = _FakeTranslation("tr-2", text="second translation")
    ex2 = _FakeExample("ex-2", text="second example", translations=(tr2,))

    src_sense = _FakeSourceSense("src-sense-1", gloss="water", examples=(ex1, ex2))
    new_sense = _NewSense()

    source_handle = _FakeProject()
    target_handle = _FakeProject(
        translation_tags=_FakeTargetList([target_type_item]),
        publication_types=_FakeTargetList([target_pub_item]),
    )
    ctx = _FakeContext(source_handle, target_handle)
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(src_sense, new_sense, ctx, _TAG, resolver_cache, dropped)

    # Ordering preserved (FR-009 "Guarantees"): new_sense.ExamplesOS mirrors
    # src_sense.ExamplesOS's order exactly.
    assert [e.Guid for e in new_sense.ExamplesOS] == ["ex-1", "ex-2"]

    new_ex1 = new_sense.ExamplesOS[0]
    # Content copied via GetSyncableProperties/ApplySyncableProperties.
    assert (new_ex1, {"_marker": "ex-1"}) in [
        (obj, props) for obj, props, _ws in target_handle.Examples.apply_calls
    ]
    # The example's own TranslationsOC reproduced, GUID preserved, TypeRA
    # resolved via the resolver BEFORE create (LINK against the matching
    # target translation-tag item) and passed straight into
    # `ICmTranslationFactory.Create(owner, translationType, guid)` --
    # never set afterward via `setattr` on an already-created translation
    # (there is no such overload).
    assert len(new_ex1.TranslationsOC) == 1
    assert new_ex1.TranslationsOC[0].Guid == "tr-1"
    assert new_ex1.TranslationsOC[0].TypeRA is target_type_item
    # DoNotPublishInRC/PublishIn routed through the resolver.
    assert target_pub_item in list(new_ex1.PublishIn)


# ============================================================================
# Case 2 -- Entry.PronunciationsOS (ordered)
# ============================================================================

def test_pronunciations_reproduced_under_entry_ordered():
    pron1 = _FakePronunciation("pron-1", form="foo")
    pron2 = _FakePronunciation("pron-2", form="bar")
    src_entry = _FakeSourceEntry("src-entry-1", pronunciations=(pron1, pron2))
    new_entry = _NewEntry()

    source_handle = _FakeProject()
    target_handle = _FakeProject()
    ctx = _FakeContext(source_handle, target_handle)
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(src_entry, new_entry, ctx, _TAG, resolver_cache, dropped)

    # `ILexPronunciationFactory.Create(guid)` returns an UNOWNED object --
    # the walk itself must then do `new_entry.PronunciationsOS.Add(new_p)`
    # (no factory overload takes an owner). Ordering + GUIDs preserved.
    assert [p.Guid for p in new_entry.PronunciationsOS] == ["pron-1", "pron-2"]


# ============================================================================
# Case 3 -- Entry.EtymologyOS with LanguageRS resolved (seq)
# ============================================================================

def test_etymology_reproduced_under_entry_with_language_rs_resolved():
    lang_guid = "lang-guid-1"
    target_lang_item = _FakePossibility(lang_guid, name="Ejagham")
    source_lang_item = _FakePossibility(lang_guid, name="Ejagham")

    etym1 = _FakeEtymology("etym-1", form="proto-form", language_rs=(source_lang_item,))
    src_entry = _FakeSourceEntry("src-entry-2", etymologies=(etym1,))
    new_entry = _NewEntry()

    source_handle = _FakeProject()
    target_handle = _FakeProject(languages=_FakeTargetList([target_lang_item]))
    ctx = _FakeContext(source_handle, target_handle)
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(src_entry, new_entry, ctx, _TAG, resolver_cache, dropped)

    # `ILexEtymologyFactory.Create(guid)` returns an UNOWNED object -- the
    # walk itself must then do `new_entry.EtymologyOS.Add(new_e)` (no
    # factory overload takes an owner). GUID preserved, LanguageRS resolved.
    assert len(new_entry.EtymologyOS) == 1
    new_etym = new_entry.EtymologyOS[0]
    assert new_etym.Guid == "etym-1"
    assert list(new_etym.LanguageRS) == [target_lang_item]


# ============================================================================
# Case 4 -- Sense.SensesOS (recurse): sub-sense reproduced through the full
# sense-copy path, ordering preserved, sub-sense's own ref fields resolve.
# ============================================================================

def test_recursive_sub_senses_reproduced_ordered_with_own_ref_fields_resolved():
    type_guid = "subsense-type-guid"
    target_type_item = _FakePossibility(type_guid, name="Idiom")
    source_type_item = _FakePossibility(type_guid, name="Idiom")

    sub1 = _FakeSourceSense("sub-1", gloss="sub one", sense_type=source_type_item)
    sub2 = _FakeSourceSense("sub-2", gloss="sub two")
    src_sense = _FakeSourceSense("src-sense-2", gloss="parent", sub_senses=(sub1, sub2))
    new_sense = _NewSense()

    source_handle = _FakeProject()
    target_handle = _FakeProject(
        # SenseTypeRA resolves via `lp.LexDbOA.SenseTypesOA` per
        # REFERENCE_FIELD_MAP -- reuse the same LangProject fake shape,
        # attaching the extra list the sub-sense's own reference-field pass
        # needs (SenseTypesOA is not one of this test file's `_FakeLangProject`
        # constructor args, so it is attached directly here).
    )
    target_handle.Cache.LangProject.LexDbOA.SenseTypesOA = _FakeTargetList(
        [target_type_item]
    )
    ctx = _FakeContext(source_handle, target_handle)
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(src_sense, new_sense, ctx, _TAG, resolver_cache, dropped)

    # Ordering preserved through the recursive sub-sense leg.
    assert [s.Guid for s in new_sense.SensesOS] == ["sub-1", "sub-2"]
    new_sub1 = new_sense.SensesOS[0]
    # The sub-sense got the SAME reference treatment a top-level sense gets
    # (SenseTypeRA resolved via the resolver, LINK to the matching target item).
    assert new_sub1.SenseTypeRA is target_type_item


# ============================================================================
# Case 5 -- FR-009: anything unreproducible appends exactly one
# DroppedItemRecord, never silent.
# ============================================================================

def test_unresolvable_example_publish_in_appends_exactly_one_dropped_record():
    """FR-009 dropped-record coverage, deliberately routed through
    Example.PublishIn (OWNER_TAKING -- `ILexExampleSentenceFactory.Create`
    is unaffected by this cycle's owner-shape strengthening) rather than
    Etymology.LanguageRS as in an earlier revision of this test: once
    `_FakeEtymologyFactory`/`_FakeTranslationFactory` model their REAL
    (non-uniform) `Create` signatures, etymology creation itself now fails
    before `LanguageRS` resolution is ever attempted -- see
    `test_etymology_reproduced_under_entry_with_language_rs_resolved` and
    `test_pronunciations_reproduced_under_entry_ordered` for that
    (deliberately RED) create-failure coverage. This test instead keeps
    exercising the "target list absent" REPORT_DROPPED branch
    (contracts/reference-resolver.md) end-to-end on a still-succeeding
    create path, so FR-009's never-silent guarantee stays proven GREEN
    independent of the owner-shape bug."""
    source_pub_item = _FakePossibility("pub-guid-missing", name="Unknown Publication")
    ex1 = _FakeExample(
        "ex-3", text="undropped example", publish_in=(source_pub_item,)
    )
    src_sense = _FakeSourceSense("src-sense-3", gloss="drop-test", examples=(ex1,))
    new_sense = _NewSense()

    source_handle = _FakeProject()
    # `publication_types=None` here resolves through `_FakeLangProject`'s own
    # default (`_FakeTargetList()`, empty-but-present) -- to model "target
    # list ABSENT" (not merely empty) we explicitly null out
    # PublicationTypesOA after construction, matching `decide_reference`'s
    # REPORT_DROPPED "target list absent" branch (contracts/
    # reference-resolver.md).
    target_handle = _FakeProject()
    target_handle.Cache.LangProject.LexDbOA.PublicationTypesOA = None
    ctx = _FakeContext(source_handle, target_handle)
    resolver_cache: dict = {}
    dropped: list = []

    owned.walk_owned_children(src_sense, new_sense, ctx, _TAG, resolver_cache, dropped)

    assert len(dropped) == 1
    record = dropped[0]
    assert isinstance(record, DroppedItemRecord)
    assert record.field_name == "PublishIn"
    assert record.item_guid == "pub-guid-missing"
    assert record.reason  # non-empty per DroppedItemRecord.__post_init__
