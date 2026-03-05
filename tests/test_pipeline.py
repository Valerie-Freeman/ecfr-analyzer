from collections import defaultdict
from api.pipeline import _add_cfr_refs


class TestAddCfrRefs:
    # Standard chapter ref creates a (title, chapter) -> [slug] entry
    def test_chapter_ref_added_to_map(self):
        agency_map = defaultdict(list)
        refs = [{"title": 40, "chapter": "I"}]
        _add_cfr_refs(agency_map, "epa", refs)
        assert agency_map[(40, "I")] == ["epa"]

    # Refs with "subtitle" instead of "chapter" are skipped
    def test_subtitle_ref_skipped(self):
        agency_map = defaultdict(list)
        refs = [{"title": 7, "subtitle": "A"}]
        _add_cfr_refs(agency_map, "office-of-secretary", refs)
        assert len(agency_map) == 0

    # Two agencies can share the same (title, chapter) key
    def test_multiple_agencies_same_chapter(self):
        agency_map = defaultdict(list)
        _add_cfr_refs(agency_map, "agency-a", [{"title": 10, "chapter": "II"}])
        _add_cfr_refs(agency_map, "agency-b", [{"title": 10, "chapter": "II"}])
        assert agency_map[(10, "II")] == ["agency-a", "agency-b"]

    # When an agency has both subtitle and chapter refs, only chapters are added
    def test_mixed_refs_only_chapters_added(self):
        agency_map = defaultdict(list)
        refs = [
            {"title": 32, "subtitle": "A"},
            {"title": 2, "chapter": "XI"},
            {"title": 5, "chapter": "XXVI"},
        ]
        _add_cfr_refs(agency_map, "defense", refs)
        assert len(agency_map) == 2
        assert "defense" in agency_map[(2, "XI")]
        assert "defense" in agency_map[(5, "XXVI")]

    # Empty refs list produces no mapping entries
    def test_empty_refs_no_change(self):
        agency_map = defaultdict(list)
        _add_cfr_refs(agency_map, "empty-agency", [])
        assert len(agency_map) == 0
