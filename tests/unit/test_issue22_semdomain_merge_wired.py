"""Issue #22: SEMANTIC_DOMAINS Merge executor is wired.

The Preview plans a Merge for each diverged semantic domain; before this, the
UPDATE executor had no ops accessor for the category, so every planned merge
was a no-op. Pure checks; no LCM host required.
"""
from __future__ import annotations

import gramtrans.Lib.transfer as transfer
from gramtrans.Lib.models import GrammarCategory


def test_semantic_domains_has_update_accessor():
    assert transfer._OPS_ACCESSOR_FOR_CATEGORY[GrammarCategory.SEMANTIC_DOMAINS] == "SemanticDomains"


def test_questions_is_not_compared_or_written():
    # QuestionsOS is not writable by the base ApplySyncableProperties.
    assert "Questions" in transfer._UPDATE_UNWRITABLE_KEYS[GrammarCategory.SEMANTIC_DOMAINS]
