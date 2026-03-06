from collections import defaultdict
from unittest.mock import patch, Mock
from api.pipeline import _add_cfr_refs, _find_nodes, process_title_content, process_title_versions


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


class TestFindNodes:
    # Finds direct children matching the target type
    def test_finds_direct_children(self):
        tree = {
            "type": "title",
            "children": [
                {"type": "chapter", "identifier": "I"},
                {"type": "chapter", "identifier": "II"},
            ]
        }
        result = _find_nodes(tree, "chapter")
        assert len(result) == 2
        assert result[0]["identifier"] == "I"
        assert result[1]["identifier"] == "II"

    # Finds nodes nested inside intermediate nodes (e.g., parts inside subchapters)
    def test_finds_nested_through_intermediate(self):
        tree = {
            "type": "chapter",
            "identifier": "I",
            "children": [
                {
                    "type": "subchapter",
                    "identifier": "A",
                    "children": [
                        {"type": "part", "identifier": "1"},
                        {"type": "part", "identifier": "2"},
                    ]
                }
            ]
        }
        result = _find_nodes(tree, "part")
        assert len(result) == 2
        assert result[0]["identifier"] == "1"

    # Returns empty list when no nodes match
    def test_no_matches_returns_empty(self):
        tree = {
            "type": "title",
            "children": [
                {"type": "chapter", "identifier": "I"},
            ]
        }
        result = _find_nodes(tree, "part")
        assert result == []

    # Handles nodes with no children key
    def test_no_children_key(self):
        tree = {"type": "part", "identifier": "1"}
        result = _find_nodes(tree, "section")
        assert result == []


def _make_version(part, date, substantive=True, removed=False):
    """Build a minimal version entry for testing."""
    return {
        "part": part,
        "amendment_date": date,
        "substantive": substantive,
        "removed": removed,
        "identifier": "1.1",
        "name": "test section",
        "title": "1",
        "type": "section",
    }


def _mock_json_get(json_data):
    """Create a mock httpx.get that returns the given JSON."""
    mock_response = Mock()
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = Mock()
    return Mock(return_value=mock_response)


class TestProcessTitleVersions:
    # Helper: structure JSON with one chapter containing two parts
    STRUCTURE = {
        "type": "title",
        "identifier": "1",
        "children": [
            {
                "type": "chapter",
                "identifier": "I",
                "children": [
                    {"type": "part", "identifier": "1"},
                    {"type": "part", "identifier": "2"},
                ]
            }
        ]
    }

    def _run(self, versions, agency_map, structure=None):
        """Run process_title_versions with mocked HTTP calls."""
        struct = structure or self.STRUCTURE
        versions_json = {"content_versions": versions}

        # process_title_versions makes two httpx.get calls:
        # 1. fetch_titles_structure (structure endpoint)
        # 2. versions endpoint
        mock = Mock()
        struct_response = Mock()
        struct_response.json.return_value = struct
        struct_response.raise_for_status = Mock()

        versions_response = Mock()
        versions_response.json.return_value = versions_json
        versions_response.raise_for_status = Mock()

        mock.side_effect = [struct_response, versions_response]

        with patch("api.pipeline.httpx.get", mock):
            return process_title_versions(1, "2026-01-01", agency_map)

    # Substantive change increments the substantive counter
    def test_substantive_change(self):
        versions = [_make_version("1", "2024-03-15", substantive=True, removed=False)]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result["epa"]["2024-03"]["substantive"] == 1
        assert result["epa"]["2024-03"]["removals"] == 0
        assert result["epa"]["2024-03"]["non_substantive"] == 0

    # Non-substantive change increments non_substantive counter
    def test_non_substantive_change(self):
        versions = [_make_version("1", "2024-06-01", substantive=False, removed=False)]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result["epa"]["2024-06"]["non_substantive"] == 1
        assert result["epa"]["2024-06"]["substantive"] == 0

    # Removal increments removals counter
    def test_removal(self):
        versions = [_make_version("2", "2024-01-10", substantive=False, removed=True)]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result["epa"]["2024-01"]["removals"] == 1

    # Entry that is both removed and substantive counts as removal, not substantive
    def test_removed_takes_priority_over_substantive(self):
        versions = [_make_version("1", "2024-03-15", substantive=True, removed=True)]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result["epa"]["2024-03"]["removals"] == 1
        assert result["epa"]["2024-03"]["substantive"] == 0

    # Multiple entries in the same month aggregate correctly
    def test_aggregation_same_period(self):
        versions = [
            _make_version("1", "2024-03-01", substantive=True, removed=False),
            _make_version("1", "2024-03-15", substantive=True, removed=False),
            _make_version("2", "2024-03-20", substantive=False, removed=True),
        ]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result["epa"]["2024-03"]["substantive"] == 2
        assert result["epa"]["2024-03"]["removals"] == 1

    # Entries in different months produce separate period keys
    def test_different_periods_separate(self):
        versions = [
            _make_version("1", "2024-01-15", substantive=True, removed=False),
            _make_version("1", "2024-06-15", substantive=True, removed=False),
        ]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert "2024-01" in result["epa"]
        assert "2024-06" in result["epa"]

    # Versions for a part not in the structure are skipped
    def test_unmapped_part_skipped(self):
        versions = [_make_version("999", "2024-03-15", substantive=True, removed=False)]
        agency_map = {(1, "I"): ["epa"]}

        result = self._run(versions, agency_map)
        assert result == {}

    # Chapter with no agency mapping produces no results
    def test_unmapped_chapter_skipped(self):
        versions = [_make_version("1", "2024-03-15", substantive=True, removed=False)]
        agency_map = {}  # no agencies mapped

        result = self._run(versions, agency_map)
        assert result == {}
