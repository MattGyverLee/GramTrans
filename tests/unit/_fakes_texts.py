"""Shared duck-typed fakes for the Feature 026 texts-wordforms offline suite.

No flexicon / LCM host needed. These model the flexicon Operations accessor
surface (`project.Texts`, `project.Segments`, `project.WfiAnalyses`, ...) closely
enough to exercise the pure plan/apply logic of `Lib/texts.py` and
`Lib/wordforms.py` with fakes, per the plan's offline unit gate (T037).

The shapes match what the code under test actually reads:
- WS objects expose ``.Id`` and ``.Handle`` (and ``.IsVernacular``).
- multi-WS string fields are ``{ws_handle: text}`` dicts (``references._multistring_dict``
  reads ``._data``).
- referent objects (genre / POS / sense / MSA) expose ``.Guid``.
"""
from __future__ import annotations


# --------------------------------------------------------------------------
# Writing systems
# --------------------------------------------------------------------------

class FakeWS:
    def __init__(self, ws_id, handle, is_vernacular=False):
        self.Id = ws_id
        self.Handle = handle
        self.IsVernacular = is_vernacular


class FakeWSOps:
    def __init__(self, ws_list):
        self._ws = list(ws_list)

    def GetAll(self):
        return list(self._ws)


# --------------------------------------------------------------------------
# Possibility-shaped referents (genre / POS / sense / MSA / morph / allomorph)
# --------------------------------------------------------------------------

class FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})


class FakePossibility:
    """Duck-typed possibility / referenced object with a GUID and Name."""

    def __init__(self, guid, name="", handle=100):
        self.Guid = guid
        self.guid = guid
        self.Name = FakeMultiString({handle: name} if name else {})
        self.Abbreviation = FakeMultiString({})
        self.IsProtected = False
        self.Owner = None
        self.OwningPossibility = None


class FakeCmObject:
    """Generic source referent with just a GUID (sense/MSA/morph/allomorph)."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class FakePossibilityList:
    def __init__(self, items=()):
        self.PossibilitiesOS = list(items)
        self.ItemClsid = 7


_UNSET = object()


class FakeLangProject:
    def __init__(self, genre_list=None, pos_list=None, tag_list=_UNSET):
        self.GenreListOA = genre_list if genre_list is not None else FakePossibilityList()
        self.PartsOfSpeechOA = pos_list if pos_list is not None else FakePossibilityList()
        # Feature 026 US5 (text-markup tags): TextMarkupTagsOA is the tag
        # possibility list. Omitting `tag_list` gives an empty (present) list ->
        # CREATE; passing None models an absent target list -> REPORT_DROPPED.
        self.TextMarkupTagsOA = (
            FakePossibilityList() if tag_list is _UNSET else tag_list
        )


class FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project


# --------------------------------------------------------------------------
# Texts / paragraphs / segments
# --------------------------------------------------------------------------

class FakeText:
    def __init__(self, guid, name, abbreviation="", is_translated=None,
                 genres=(), paragraphs=(), source_text="", tags=()):
        self.guid = guid
        self.Guid = guid
        self.name = name
        self.abbreviation = abbreviation
        self.is_translated = is_translated
        self.genres = list(genres)
        self.paragraphs = list(paragraphs)
        self.source_text = source_text
        # Feature 026 US5: per-text ITextTag objects (text-markup tags).
        self.tags = list(tags)


class FakeTextTag:
    """Duck-typed ITextTag: a text-markup tag reference spanning segment(s).

    `TagRA` is the referenced possibility (in TextMarkupTagsOA); the begin/end
    segment refs and analysis indices locate the tagged span (single-segment in
    the fakes).
    """

    def __init__(self, guid, tag_ra=None, begin_seg=None, end_seg=None,
                 begin_idx=0, end_idx=0):
        self.guid = guid
        self.Guid = guid
        self.TagRA = tag_ra
        self.BeginSegmentRA = begin_seg
        self.EndSegmentRA = end_seg if end_seg is not None else begin_seg
        self.BeginAnalysisIndex = begin_idx
        self.EndAnalysisIndex = end_idx


class FakeParagraph:
    def __init__(self, guid, text_by_handle=None, segments=()):
        self.guid = guid
        self.Guid = guid
        self.text_by_handle = dict(text_by_handle or {})
        self.segments = list(segments)


class FakeSegment:
    def __init__(self, guid, baseline="", free=None, literal=None, notes=(),
                 wordforms=(), analyses_rs=()):
        self.guid = guid
        self.Guid = guid
        self.baseline = baseline
        self.free = dict(free or {})        # {handle: text}
        self.literal = dict(literal or {})  # {handle: text}
        self.note_objs = list(notes)        # str or objects with .Content
        self.wordforms = list(wordforms)
        self.analyses_rs = list(analyses_rs)
        # Target-side rebuilt alignment:
        self.AnalysesRS = _FakeSeq()


class _FakeSeq:
    def __init__(self):
        self.items = []

    @property
    def Count(self):
        return len(self.items)

    def Add(self, obj):
        self.items.append(obj)


# --------------------------------------------------------------------------
# Wordforms / analyses / morph bundles / evaluations
# --------------------------------------------------------------------------

class FakeEvaluation:
    def __init__(self, approves=True):
        self.Approves = approves


class FakeAnalysis:
    def __init__(self, guid, human_eval=None, category=None, morph_bundles=(),
                 glosses=(), class_name="WfiAnalysis"):
        self.guid = guid
        self.Guid = guid
        self.human_evaluation = human_eval
        self.CategoryRA = category
        self.morph_bundles = list(morph_bundles)
        self.glosses = list(glosses)
        self.ClassName = class_name

    def GetHumanEvaluation(self):
        return self.human_evaluation


class FakeGloss:
    def __init__(self, guid, forms=None, human_eval=None,
                 class_name="WfiGloss"):
        self.guid = guid
        self.Guid = guid
        self.forms = dict(forms or {})   # {handle: text}
        self.human_evaluation = human_eval
        self.ClassName = class_name

    def GetHumanEvaluation(self):
        return self.human_evaluation


class FakeMorphBundle:
    def __init__(self, guid, form=None, morph=None, msa=None, sense=None, infl_type=None):
        self.guid = guid
        self.Guid = guid
        self.form = dict(form or {})  # {handle: text}
        self.MorphRA = morph
        self.MsaRA = msa
        self.SenseRA = sense
        self.InflTypeRA = infl_type


class FakeWordform:
    def __init__(self, guid, form_by_handle=None, analyses=(), spelling=None,
                 class_name="WfiWordform"):
        self.guid = guid
        self.Guid = guid
        self.form_by_handle = dict(form_by_handle or {})
        self.analyses = list(analyses)
        self.spelling = spelling
        self.ClassName = class_name


# --------------------------------------------------------------------------
# Operations namespaces
# --------------------------------------------------------------------------

class FakeTextOps:
    def __init__(self, texts=(), created_sink=None):
        self._texts = list(texts)
        self.created = created_sink if created_sink is not None else []

    def GetAll(self):
        return list(self._texts)

    def GetName(self, t):
        return t.name

    def GetAbbreviation(self, t):
        return t.abbreviation

    def GetIsTranslated(self, t):
        return t.is_translated

    def GetSource(self, t):
        return t.source_text

    def GetGenre(self, t):
        return list(t.genres)

    def GetParagraphs(self, t):
        return list(t.paragraphs)

    def Find(self, title, wsHandle=None):
        for t in self._texts:
            if t.name == title:
                return t
        return None

    def Exists(self, name):
        target = (name or "").strip()
        return any(t.name == target for t in self._texts)

    def Create(self, name, genre=None):
        # Mirrors the real TextOperations.Create: raises when a text with
        # this name already exists (flexicon TextOperations.py:149-150) --
        # the Site-1 duplicate-name collision fixture exercises this guard.
        if self.Exists(name):
            raise ValueError(f"A text with the name '{name}' already exists.")
        t = FakeText(guid="tgt-" + name, name=name)
        self._texts.append(t)
        self.created.append(("text", name))
        return t

    def SetAbbreviation(self, t, value):
        t.abbreviation = value

    def SetIsTranslated(self, t, value):
        t.is_translated = value

    def SetGenre(self, t, genre):
        t.genres.append(genre)


class FakeParagraphOps:
    def __init__(self, created_sink=None):
        self.created = created_sink if created_sink is not None else []

    def GetAll(self, t):
        return list(getattr(t, "paragraphs", []))

    def GetText(self, p, wsHandle=None):
        return p.text_by_handle.get(wsHandle)

    def Create(self, text, content, wsHandle=None):
        p = FakeParagraph(guid="tgt-para", text_by_handle={wsHandle: content})
        text.paragraphs.append(p)
        self.created.append(("para", content))
        return p


class FakeSegmentOps:
    def __init__(self, created_sink=None):
        self.created = created_sink if created_sink is not None else []

    def GetAll(self, p):
        return list(getattr(p, "segments", []))

    def GetBaselineText(self, s):
        return s.baseline

    def GetFreeTranslation(self, s, wsHandle=None):
        return s.free.get(wsHandle)

    def GetLiteralTranslation(self, s, wsHandle=None):
        return s.literal.get(wsHandle)

    def GetNotes(self, s):
        return list(s.note_objs)

    def GetAnalyses(self, s):
        return list(getattr(s, "analyses_rs", []))

    def AppendSentence(self, p, text, wsHandle=None):
        seg = FakeSegment(guid="tgt-seg", baseline=text)
        p.segments.append(seg)
        return seg

    def SetFreeTranslation(self, s, text, wsHandle=None):
        s.free[wsHandle] = text

    def SetLiteralTranslation(self, s, text, wsHandle=None):
        s.literal[wsHandle] = text


class FakeWordformOps:
    def __init__(self, wordforms=()):
        self._wf = list(wordforms)
        self.created = []

    def GetForm(self, wf, wsHandle=None):
        return wf.form_by_handle.get(wsHandle)

    def GetSpellingStatus(self, wf):
        return wf.spelling

    def SetSpellingStatus(self, wf, status):
        wf.spelling = status

    def ApproveSpelling(self, wf):
        wf.spelling = "CORRECT"

    def Find(self, form, wsHandle=None):
        for wf in self._wf:
            if wf.form_by_handle.get(wsHandle) == form:
                return wf
        return None

    def Create(self, form, wsHandle=None):
        wf = FakeWordform(guid="tgt-wf-" + str(form), form_by_handle={wsHandle: form})
        self._wf.append(wf)
        self.created.append(form)
        return wf


class FakeWfiAnalysisOps:
    def __init__(self, project=None):
        self.project = project
        self.created = []

    def GetHumanEvaluation(self, a):
        return getattr(a, "human_evaluation", None)

    def GetOwningWordform(self, a):
        return getattr(a, "_owner_wordform", None)

    def GetCategory(self, a):
        return getattr(a, "CategoryRA", None)

    def GetMorphBundles(self, a):
        return list(getattr(a, "morph_bundles", []))

    def GetGlosses(self, a):
        # SC-005: target analyses expose their (created) glosses so the
        # structural-fingerprint dedup can recognise a re-Move.
        return list(getattr(a, "glosses", []))

    def GetAll(self, wordform):
        # SC-005: enumerate the analyses already on a target wordform.
        return list(getattr(wordform, "analyses", []))

    def Create(self, wordform):
        a = FakeAnalysis(guid="tgt-an")
        a.approved = None
        a._owner_wordform = wordform
        wordform.analyses.append(a)
        self.created.append(a)
        return a

    def ApproveAnalysis(self, a):
        a.approved = True

    def RejectAnalysis(self, a):
        a.approved = False

    def SetCategory(self, a, category):
        a.CategoryRA = category


class FakeMorphBundleOps:
    def __init__(self):
        self.created = []

    def GetAll(self, a):
        return list(getattr(a, "morph_bundles", []))

    def GetForm(self, b, wsHandle=None):
        # Source bundles carry `.form`; target bundles (created here) carry the
        # reproduced text in `.set_form` (via SetForm). Read either so the
        # SC-005 fingerprint can be reconstructed off a target bundle.
        val = b.form.get(wsHandle)
        if val is None:
            val = getattr(b, "set_form", {}).get(wsHandle)
        return val

    def GetMorph(self, b):
        return b.MorphRA

    def GetMSA(self, b):
        return b.MsaRA

    def GetSense(self, b):
        return b.SenseRA

    def GetInflType(self, b):
        return b.InflTypeRA

    def Create(self, a):
        b = FakeMorphBundle(guid="tgt-mb")
        b.set_form = {}
        b.wired = {}
        # Attach to the owning target analysis so GetMorphBundles(a) sees it
        # (SC-005 fingerprint reconstruction).
        bundles = getattr(a, "morph_bundles", None)
        if bundles is not None:
            bundles.append(b)
        self.created.append(b)
        return b

    def SetForm(self, b, text, wsHandle=None):
        b.set_form[wsHandle] = text

    def SetSense(self, b, sense):
        b.wired["sense"] = sense

    def SetMSA(self, b, msa):
        b.wired["msa"] = msa

    def SetMorphType(self, b, morph):
        b.wired["morph"] = morph

    def SetInflType(self, b, it):
        b.wired["infl_type"] = it


class FakeWfiGlossOps:
    def __init__(self):
        self.created = []

    def GetAll(self, a):
        return list(getattr(a, "glosses", []))

    def GetForm(self, g, wsHandle=None):
        # Source glosses carry `.forms`; target glosses (created here) carry the
        # reproduced text in `.set_form`. Read either for the SC-005 fingerprint.
        val = g.forms.get(wsHandle)
        if val is None:
            val = getattr(g, "set_form", {}).get(wsHandle)
        return val

    def GetHumanEvaluation(self, g):
        return getattr(g, "human_evaluation", None)

    def Create(self, a, form=None, wsHandle=None):
        # Mirrors the real WfiGlossOperations.Create(analysis, form, wsHandle=None):
        # the gloss form is required at creation.
        g = FakeGloss(guid="tgt-gloss")
        g.set_form = {}
        if form is not None:
            g.set_form[wsHandle] = form
        # Attach to the owning target analysis so GetGlosses(a) sees it
        # (SC-005 fingerprint reconstruction).
        glosses = getattr(a, "glosses", None)
        if glosses is not None:
            glosses.append(g)
        self.created.append(g)
        return g

    def SetForm(self, g, text, wsHandle=None):
        g.set_form[wsHandle] = text


class FakeTextTagOps:
    """Target-side seam for per-segment text-markup tag creation (US5).

    flexicon exposes NO ITextTag wrapper, so production reaches the raw LCM
    surface (StText.TagsOC + ITextTagFactory, [PROBE] R6/T039). This duck-typed
    op models the same Create contract for the offline gate."""

    def __init__(self):
        self.created = []

    def Create(self, text, tag_possibility, begin_seg, end_seg=None,
               begin_idx=0, end_idx=0):
        rec = FakeTextTag(
            guid="tgt-tag", tag_ra=tag_possibility,
            begin_seg=begin_seg, end_seg=end_seg or begin_seg,
            begin_idx=begin_idx, end_idx=end_idx,
        )
        self.created.append(rec)
        if hasattr(text, "target_tags"):
            text.target_tags.append(rec)
        return rec


class FakeAgent:
    def __init__(self, name, is_human=True):
        self.name = name
        self.is_human = is_human


class FakeAgentOps:
    def __init__(self, humans=()):
        self._humans = list(humans)
        self.created = []

    def GetHumanAgents(self):
        return list(self._humans)

    def FindByType(self, is_human):
        return [a for a in self._humans if a.is_human == is_human]

    def Create(self, name, wsHandle=None):
        a = FakeAgent(name)
        self.created.append(a)
        self._humans.append(a)
        return a

    def SetHuman(self, agent, person):
        agent.is_human = True

    def IsHuman(self, agent):
        return agent.is_human


class FakeProject:
    """A fake FLExProject exposing the operation accessors + WS/Cache surface."""

    def __init__(self, ws_list=(), texts=(), wordforms=(), agents=(),
                 lang_project=None, default_vern_id="vern", default_anal_id="en"):
        self.WritingSystems = FakeWSOps(ws_list)
        self._created = []
        self.Texts = FakeTextOps(texts, self._created)
        self.Paragraphs = FakeParagraphOps(self._created)
        self.Segments = FakeSegmentOps(self._created)
        self.Wordforms = FakeWordformOps(wordforms)
        self.Cache = FakeCache(lang_project or FakeLangProject())
        self.WfiAnalyses = FakeWfiAnalysisOps(self)
        self.WfiMorphBundles = FakeMorphBundleOps()
        self.WfiGlosses = FakeWfiGlossOps()
        self.TextTags = FakeTextTagOps()
        self.Agents = FakeAgentOps(agents)
        self._default_vern_id = default_vern_id
        self._default_anal_id = default_anal_id
        self._id2handle = {ws.Id: ws.Handle for ws in ws_list}

    def GetDefaultVernacularWS(self):
        return (self._default_vern_id, "Vernacular")

    def GetDefaultVernacularWSHandle(self):
        return self._id2handle.get(self._default_vern_id)

    def GetDefaultAnalysisWSHandle(self):
        return self._id2handle.get(self._default_anal_id)

    def Object(self, guid):
        return None


class FakeCtx:
    """Minimal run context: source_handle + _ws_map + _copy_set."""

    def __init__(self, source_handle=None, ws_map=None, copy_set=None):
        self.source_handle = source_handle
        self._ws_map = dict(ws_map or {})
        self._copy_set = dict(copy_set or {})
        self.run_id = "GT-20260712-000000"
