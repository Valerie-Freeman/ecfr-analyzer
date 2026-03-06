import hashlib
from collections import defaultdict
from unittest.mock import patch, Mock, MagicMock, call
from api.pipeline import _add_cfr_refs, _find_nodes, process_title_content, process_title_versions, run_pipeline


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
    mock_response.content = xml_text.encode("utf-8")
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


# --- Step 5: Pipeline orchestration tests ---

class TestChecksumConsistency:
    """Checksums must be deterministic and sensitive to any text change."""

    def test_same_text_same_checksum(self):
        text = "federal regulation text"
        hash1 = hashlib.sha256(text.encode()).hexdigest()
        hash2 = hashlib.sha256(text.encode()).hexdigest()
        assert hash1 == hash2

    def test_different_text_different_checksum(self):
        hash1 = hashlib.sha256("version one".encode()).hexdigest()
        hash2 = hashlib.sha256("version two".encode()).hexdigest()
        assert hash1 != hash2

    def test_checksum_is_64_char_hex(self):
        result = hashlib.sha256("test".encode()).hexdigest()
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


def _mock_conn():
    """Create a mock database connection with cursor context manager."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn, mock_cursor


class TestRunPipelineAggregation:
    """run_pipeline merges partial results from multiple titles correctly."""

    def _run_with_mocks(self, title_metadata, content_by_title, versions_by_title,
                        stored_metadata=None, full_refresh=True):
        """Run run_pipeline with all external calls mocked."""
        agency_map = defaultdict(list)

        mock_conn, mock_cursor = _mock_conn()
        # stored metadata query returns empty by default (first run)
        mock_cursor.fetchall.return_value = [
            (t, d) for t, d in (stored_metadata or {}).items()
        ]

        def mock_content(title_number, date, amap):
            return content_by_title.get(title_number, {})

        def mock_versions(title_number, date, amap):
            return versions_by_title.get(title_number, {})

        with patch("api.pipeline.fetch_agencies", return_value=agency_map), \
             patch("api.pipeline.fetch_title_metadata", return_value=title_metadata), \
             patch("api.pipeline.process_title_content", side_effect=mock_content), \
             patch("api.pipeline.process_title_versions", side_effect=mock_versions), \
             patch("api.pipeline.get_conn", return_value=mock_conn):
            run_pipeline(full_refresh=full_refresh)

        return mock_cursor

    def test_word_counts_summed_across_titles(self):
        """Agency spanning two titles gets combined word count."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
            2: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
        }
        content_by_title = {
            1: {"epa": {"word_count": 100, "text": "title one text"}},
            2: {"epa": {"word_count": 200, "text": "title two text"}},
        }

        cursor = self._run_with_mocks(title_metadata, content_by_title, {})

        # find the word_counts INSERT for epa
        word_count_inserts = [
            c for c in cursor.execute.call_args_list
            if c[0][0].strip().startswith("INSERT INTO word_counts")
        ]
        assert len(word_count_inserts) == 1
        assert word_count_inserts[0][0][1] == ("epa", 300)

    def test_checksums_computed_from_combined_text(self):
        """Checksum reflects text from all titles, not just one."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
            2: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
        }
        content_by_title = {
            1: {"epa": {"word_count": 10, "text": "part one"}},
            2: {"epa": {"word_count": 10, "text": "part two"}},
        }

        cursor = self._run_with_mocks(title_metadata, content_by_title, {})

        expected_checksum = hashlib.sha256("part onepart two".encode()).hexdigest()
        checksum_inserts = [
            c for c in cursor.execute.call_args_list
            if c[0][0].strip().startswith("INSERT INTO checksums")
        ]
        assert len(checksum_inserts) == 1
        assert checksum_inserts[0][0][1] == ("epa", expected_checksum)

    def test_change_history_merged_across_titles(self):
        """Same agency + period from different titles sums counts."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
            2: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
        }
        versions_by_title = {
            1: {"epa": {"2024-03": {"substantive": 3, "non_substantive": 1, "removals": 0}}},
            2: {"epa": {"2024-03": {"substantive": 2, "non_substantive": 0, "removals": 1}}},
        }

        cursor = self._run_with_mocks(title_metadata, {}, versions_by_title)

        history_inserts = [
            c for c in cursor.execute.call_args_list
            if c[0][0].strip().startswith("INSERT INTO change_history")
        ]
        assert len(history_inserts) == 1
        # (slug, period, substantive, non_substantive, removals)
        assert history_inserts[0][0][1] == ("epa", "2024-03", 5, 1, 1)

    def test_old_data_deleted_before_insert(self):
        """DELETE runs for all three metric tables before any INSERTs."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
        }
        content_by_title = {
            1: {"epa": {"word_count": 50, "text": "some text"}},
        }

        cursor = self._run_with_mocks(title_metadata, content_by_title, {})

        executed_sql = [c[0][0].strip() for c in cursor.execute.call_args_list]
        delete_indices = [i for i, sql in enumerate(executed_sql) if sql.startswith("DELETE")]
        insert_indices = [i for i, sql in enumerate(executed_sql) if sql.startswith("INSERT")]

        # all DELETEs happen before any INSERTs
        assert max(delete_indices) < min(insert_indices)


class TestRunPipelineIncrementalRefresh:
    """Incremental refresh skips processing when nothing has changed."""

    def test_skips_when_nothing_changed(self):
        """No titles processed when all latest_amended_on dates match."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2025-06-15"},
        }
        stored = {1: "2025-06-15"}

        mock_conn, mock_cursor = _mock_conn()
        mock_cursor.fetchall.return_value = [(1, "2025-06-15")]

        mock_content = Mock()

        with patch("api.pipeline.fetch_agencies", return_value=defaultdict(list)), \
             patch("api.pipeline.fetch_title_metadata", return_value=title_metadata), \
             patch("api.pipeline.process_title_content", mock_content), \
             patch("api.pipeline.process_title_versions", Mock()), \
             patch("api.pipeline.get_conn", return_value=mock_conn):
            run_pipeline(full_refresh=False)

        mock_content.assert_not_called()

    def test_processes_when_title_changed(self):
        """Titles processed when latest_amended_on differs from stored."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2026-01-01"},
        }

        mock_conn, mock_cursor = _mock_conn()
        mock_cursor.fetchall.return_value = [(1, "2025-06-15")]

        mock_content = Mock(return_value={})

        with patch("api.pipeline.fetch_agencies", return_value=defaultdict(list)), \
             patch("api.pipeline.fetch_title_metadata", return_value=title_metadata), \
             patch("api.pipeline.process_title_content", mock_content), \
             patch("api.pipeline.process_title_versions", Mock(return_value={})), \
             patch("api.pipeline.get_conn", return_value=mock_conn):
            run_pipeline(full_refresh=False)

        mock_content.assert_called_once()

    def test_full_refresh_bypasses_check(self):
        """full_refresh=True processes even when nothing has changed."""
        title_metadata = {
            1: {"up_to_date_as_of": "2026-01-01", "latest_amended_on": "2025-06-15"},
        }

        mock_conn, mock_cursor = _mock_conn()
        mock_cursor.fetchall.return_value = [(1, "2025-06-15")]

        mock_content = Mock(return_value={})

        with patch("api.pipeline.fetch_agencies", return_value=defaultdict(list)), \
             patch("api.pipeline.fetch_title_metadata", return_value=title_metadata), \
             patch("api.pipeline.process_title_content", mock_content), \
             patch("api.pipeline.process_title_versions", Mock(return_value={})), \
             patch("api.pipeline.get_conn", return_value=mock_conn):
            run_pipeline(full_refresh=True)

        mock_content.assert_called_once()
