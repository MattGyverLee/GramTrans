"""T098: the field that recorded which document admits a natural key, and was
read by nothing.

WHAT WAS WRONG. `census.NaturalKeyDefinition.roster_source` records the document
that admits a class to gate-failing duplicate detection. It had a DEFAULT,
`"roster_extension_038"`, which six of the seven definitions inherited; the
seventh (`WfiWordform`) overrode it with the other spelling,
`"natural_key_identity_roster_035"`. Two writers disagreeing about the same
question, and `roster_source` was READ nowhere in `src/` or `tests/` -- so the
disagreement could not be noticed and the field could not fire anything.

Then 035 admitted all six on 2026-08-19
(`specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`, 9
entries, with the admission evidence under the top-level `live_confirmation_038`
key). From that day the six inherited values were factually wrong, and nothing
in the tree could say so.

WHAT WAS *NOT* WRONG, and this is the correction T098's filing needs. The
designed tripwire is `roster_admitted_classes`, which READS 035's roster at run
time and is quoted in the filing from its own docstring ("become gate-failing
the moment 035 merges them, with no edit here"). It fired exactly as designed:
all six classes are admitted today with no edit, which
`test_the_designed_tripwire_did_fire` measures against the live document. It was
never `roster_source` that granted admission -- `roster_source` is the code's
record of WHY it believes what it believes, and the defect is that a stale
belief was unfalsifiable.

THE FIX. The default is gone (a definition must state its provenance),
`roster_source` is validated against a two-member vocabulary at construction,
and `roster_source_disagreements` checks every claim against both documents with
`verify_roster_sources` raising before a census opens a project.
"""

from __future__ import annotations

import pytest


# The pre-fix table, verbatim in the respect that matters: the six classes 035
# had not yet admitted when it was written, each carrying the inherited default.
_PRE_FIX_CLAIMS = {
    "PhPhoneme": "roster_extension_038",
    "PhNCSegments": "roster_extension_038",
    "PhNCFeatures": "roster_extension_038",
    "PartOfSpeech": "roster_extension_038",
    "MoMorphType": "roster_extension_038",
    "LexEntryInflType": "roster_extension_038",
    "WfiWordform": "natural_key_identity_roster_035",
}


class TestTheDesignedTripwireDidFire:
    """Before blaming the mechanism, check whether it worked. It did."""

    def test_035_has_admitted_all_nine_including_038s_six(self):
        from gramtrans.Lib import census

        admitted = census.roster_admitted_classes()
        assert len(admitted) == 9
        for name in ("PhPhoneme", "PhNCSegments", "PhNCFeatures",
                     "PartOfSpeech", "MoMorphType", "LexEntryInflType"):
            assert name in admitted, name

    def test_every_definition_the_census_can_key_is_admitted(self):
        """The consequence that matters: `duplicates.roster_admitted` is True
        for all seven, so a duplicate on any of them can FAIL the gate. That is
        what T028 asked 035 for and it arrived without an edit here."""
        from gramtrans.Lib import census

        admitted = census.roster_admitted_classes()
        assert set(census.NATURAL_KEY_DEFINITIONS) <= admitted

    def test_the_proposal_is_not_emptied_when_a_proposal_lands(self):
        """Which is why provenance cannot be inferred from one document. 038's
        extension still lists all six -- it is the proposal RECORD -- so a class
        legitimately appears in both files at once."""
        from gramtrans.Lib import census

        proposed = census.roster_extension_proposed_classes()
        assert len(proposed) == 6
        assert proposed <= census.roster_admitted_classes()


class TestTheFieldNowHasAReader:
    """THE TEST THAT WOULD HAVE CAUGHT T098, and it is a measurement: run the
    new check over the OLD values and count what it reports."""

    def test_the_pre_fix_claims_would_have_reported_six_disagreements(
            self, monkeypatch):
        from gramtrans.Lib import census

        stale = {
            name: census.NaturalKeyDefinition(
                definition.object_class,
                definition.property_name,
                definition.ws_scope,
                definition.description,
                roster_source=_PRE_FIX_CLAIMS[name],
            )
            for name, definition in census.NATURAL_KEY_DEFINITIONS.items()
        }
        monkeypatch.setattr(census, "NATURAL_KEY_DEFINITIONS", stale)
        disagreements = census.roster_source_disagreements()
        assert len(disagreements) == 6, disagreements
        assert all("stale (T098)" in line for line in disagreements)
        # `WfiWordform` was already right and must not be reported.
        assert not any("WfiWordform" in line for line in disagreements)
        with pytest.raises(census.CensusError, match="disagree with the roster"):
            census.verify_roster_sources()

    def test_the_current_claims_agree_with_both_documents(self):
        from gramtrans.Lib import census

        assert census.roster_source_disagreements() == ()
        census.verify_roster_sources()

    def test_a_claim_of_admission_for_an_unadmitted_class_also_fires(
            self, monkeypatch):
        """THE OTHER DIRECTION, and the one with no other detector in the tree.
        A definition claiming 035 admission for a class 035 does not admit is
        what a roster REMOVAL looks like from in here: the census would believe
        that class's duplicates can fail the gate while
        `roster_admitted_classes` quietly marks them advisory."""
        from gramtrans.Lib import census

        invented = dict(census.NATURAL_KEY_DEFINITIONS)
        invented["MoStemName"] = census.NaturalKeyDefinition(
            "MoStemName", "Name", census.WS_SCOPE_ANALYSIS,
            "Name (default analysis alt)",
            roster_source=census.ROSTER_SOURCE_035,
        )
        monkeypatch.setattr(census, "NATURAL_KEY_DEFINITIONS", invented)
        disagreements = census.roster_source_disagreements()
        assert len(disagreements) == 1
        assert "MoStemName" in disagreements[0]
        assert "does not admit it" in disagreements[0]

    def test_a_class_no_document_accounts_for_fires_too(self, monkeypatch):
        from gramtrans.Lib import census

        invented = dict(census.NATURAL_KEY_DEFINITIONS)
        invented["MoStemName"] = census.NaturalKeyDefinition(
            "MoStemName", "Name", census.WS_SCOPE_ANALYSIS,
            "Name (default analysis alt)",
            roster_source=census.ROSTER_SOURCE_038_PROPOSAL,
        )
        monkeypatch.setattr(census, "NATURAL_KEY_DEFINITIONS", invented)
        disagreements = census.roster_source_disagreements()
        assert len(disagreements) == 1
        assert "does not propose it either" in disagreements[0]


class TestTheFieldCannotBeAcquiredByOmission:

    def test_roster_source_has_no_default(self):
        """The default is what let six entries make a provenance claim nobody
        chose. A definition must now say which document admits it."""
        import dataclasses

        from gramtrans.Lib import census

        field = {
            f.name: f
            for f in dataclasses.fields(census.NaturalKeyDefinition)
        }["roster_source"]
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING
        with pytest.raises(TypeError):
            census.NaturalKeyDefinition(
                "PhPhoneme", "Name", census.WS_SCOPE_VERNACULAR, "Name")

    def test_a_third_spelling_is_refused_at_construction(self):
        """A typo in this field used to be checked against nothing. The
        vocabulary is two members and it is enumerated."""
        from gramtrans.Lib import census

        with pytest.raises(census.CensusError, match="outside"):
            census.NaturalKeyDefinition(
                "PhPhoneme", "Name", census.WS_SCOPE_VERNACULAR, "Name",
                roster_source="roster_035")

    def test_every_definition_names_one_of_the_two_documents(self):
        from gramtrans.Lib import census

        for name, definition in census.NATURAL_KEY_DEFINITIONS.items():
            assert definition.roster_source in census.ROSTER_SOURCES, name
