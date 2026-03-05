from collections import defaultdict
from unittest.mock import patch, Mock
from api.pipeline import _add_cfr_refs, process_title_content


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


def _make_xml(*chapters):
    """Build minimal eCFR-shaped XML for testing. Each chapter is (roman, text)."""
    divs = ""
    for roman, text in chapters:
        divs += f'<DIV3 TYPE="CHAPTER" N="{roman}"><P>{text}</P></DIV3>'
    return f"<ECFR><DIV1 TYPE='TITLE'>{divs}</DIV1></ECFR>"


def _mock_get(xml_text):
    """Create a mock httpx.get that returns the given XML."""
    mock_response = Mock()
    mock_response.text = xml_text
    mock_response.raise_for_status = Mock()
    return Mock(return_value=mock_response)


class TestProcessTitleContent:
    # Single chapter mapped to one agency returns correct word count and text
    def test_single_chapter_single_agency(self):
        xml = _make_xml(("I", "hello world foo bar"))
        agency_map = {(1, "I"): ["test-agency"]}

        with patch("api.pipeline.httpx.get", _mock_get(xml)):
            results = process_title_content(1, "2026-01-01", agency_map)

        assert "test-agency" in results
        assert results["test-agency"]["word_count"] == 4

    # Chapter with no matching agency produces no results
    def test_unmatched_chapter_skipped(self):
        xml = _make_xml(("V", "some regulation text"))
        agency_map = {}  # no agencies mapped

        with patch("api.pipeline.httpx.get", _mock_get(xml)):
            results = process_title_content(1, "2026-01-01", agency_map)

        assert results == {}

    # Two chapters mapping to the same agency aggregate word counts
    def test_multiple_chapters_same_agency(self):
        xml = _make_xml(("I", "one two three"), ("II", "four five"))
        agency_map = {(1, "I"): ["epa"], (1, "II"): ["epa"]}

        with patch("api.pipeline.httpx.get", _mock_get(xml)):
            results = process_title_content(1, "2026-01-01", agency_map)

        assert results["epa"]["word_count"] == 5
        assert "one two three" in results["epa"]["text"]
        assert "four five" in results["epa"]["text"]

    # DIV3 elements with TYPE other than CHAPTER are ignored
    def test_non_chapter_div3_ignored(self):
        xml = '<ECFR><DIV1 TYPE="TITLE">'
        xml += '<DIV3 TYPE="APPENDIX" N="A"><P>ignore this</P></DIV3>'
        xml += '<DIV3 TYPE="CHAPTER" N="I"><P>keep this</P></DIV3>'
        xml += "</DIV1></ECFR>"
        agency_map = {(1, "I"): ["test-agency"]}

        with patch("api.pipeline.httpx.get", _mock_get(xml)):
            results = process_title_content(1, "2026-01-01", agency_map)

        assert results["test-agency"]["word_count"] == 2
        assert "ignore" not in results["test-agency"]["text"]

    # Chapter shared by two agencies gives both the same word count and text
    def test_chapter_shared_by_multiple_agencies(self):
        xml = _make_xml(("III", "shared regulation text here"))
        agency_map = {(1, "III"): ["agency-a", "agency-b"]}

        with patch("api.pipeline.httpx.get", _mock_get(xml)):
            results = process_title_content(1, "2026-01-01", agency_map)

        assert results["agency-a"]["word_count"] == 4
        assert results["agency-b"]["word_count"] == 4
        assert results["agency-a"]["text"] == results["agency-b"]["text"]
