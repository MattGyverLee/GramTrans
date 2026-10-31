# Cycle 4 live probe: PR #158 (head d88dc4a) fallback relocation

Verdict: ruling 1 PASS, ruling 2 PASS, ruling 3 PASS. Dedup collapse CONFIRMED (3 relocated -> 1).
run: live (FLEXLIBS_REQUIRE_LIVE=1), flexicon = D:\Github\_Projects\_LEX\flexicon\flexicon, gramtrans from worktree D:/Github/_Projects/_LEX/GramTrans-verify-c4p/src.
Projects written: GT-Probe-158-Src, GT-Probe-158-Tgt only (both restored from Target 2026-07-06 0218.fwbackup).
Scripts: C:/Users/thoua/AppData/Local/Temp/claude/d--Github--Projects--LEX-GramTrans/a4b3675b-75d5-49d4-bc74-ed22d8e86ae3/scratchpad/probe158/ (step1-4.py)

## Fixture
Both projects: vern [etu], anal [en]; de/fr absent from store in both (Exists and ExistsInStore False).
Src: WritingSystems.Create("de", is_vernacular=False) and Create("fr", is_vernacular=True) -> seeding via API worked.
Target ends with anal [en], de/fr still absent.
Objects: two DomainTypesOA possibilities (same kind as the 42 test) referenced from one sense (ThesaurusItemsRC) of a new stem entry.
- item1 8b871cb1-a760-43c2-8abb-9723b506cd48: Name "Probe-Name-DE", Abbreviation "Probe-Abb-DE", Description "Probe-Desc-DE", all in de only.
- item2 f01dcc94-44dc-48e4-b7a6-7b8e0e46a7db: Name "Probe-Name-FR" in fr (vernacular) only.
Transfer: full_run.run_full_transfer, STEMS only, Move; 1 action, 1 succeeded.

## Read-back from GT-Probe-158-Tgt (re-opened read-only)
Target default analysis WS = en (handle 999000001). Sense ThesaurusItemsRC holds both items.
- item1 Name (en): 'Probe-Name-DE'  [only alt: en]
- item1 Abbreviation (en): 'Probe-Abb-DE'
- item1 Description (en): 'Probe-Desc-DE\n\n[GT-Tag]: GT|GT-20261031-024544|GT-Probe-158-Src|2026-10-31T02:45:44' (the tag is residue, appended by apply_residue)
- item2 Name: EMPTY (no alts, get_String None). item2 Abbreviation empty. item2 Description is only the residue tag line.

## Report records (report.dropped_items) -- 2 total
1. reason="relocated: Name text from source writing system 'de' written into target default analysis writing system 'en' (no source writing system present in target)" | owner_guid=3fef8d6f-46e6-4b69-8eab-8d37ae0e5905 | owner_label='probe sense' | owner_kind=LexSense | field_name=ThesaurusItemsRC | item_guid=8b871cb1-a760-43c2-8abb-9723b506cd48 | item_name='Probe-Name-DE' | severity=info
2. reason="source writing system 'fr' absent in target" | owner_guid=3fef8d6f-46e6-4b69-8eab-8d37ae0e5905 | owner_label='probe sense' | field_name=ThesaurusItemsRC | item_guid=f01dcc94-44dc-48e4-b7a6-7b8e0e46a7db | item_name='Probe-Name-FR' | severity=info

## Rulings
1. Single "relocated:" record instead of per-WS drops: PASS (no "absent in target" drop for item1 in any form).
2. Vernacular source WS skips fallback, keeps drop, field empty: PASS (record 2; Name empty).
3. Relocation lands in explicitly resolved target default analysis WS: PASS (en; exact strings above).

## KEY QUESTION: dedup collapse
Re-ran with apply_reference wrapped to capture the RAW pre-dedup `dropped` output: references.py emits THREE relocated records for item1 (Name, Abbreviation, Description), identical (owner_guid, field_name, item_guid). The report keeps ONE (the Name one). The Abbreviation and Description relocated records are lost to dedup (key excludes reason; field_name is ThesaurusItemsRC for all three).
Consequence: the report states only "Name" was relocated although Abbreviation and Description were too. In this probe no real drop disappeared (item2's drop is a different item_guid). Not exercised: a mixed item where Name relocates but a different field has a genuine drop (e.g. a vernacular-only Abbreviation) -- by key it would collapse the same way, and the first-record-wins rule could hide the real drop behind an "info" relocated record. Recommend including the item field (or reason) in the key, or aggregating fields into one relocated reason.
