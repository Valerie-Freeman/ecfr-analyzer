import hashlib
import logging
import tempfile
import xml.etree.ElementTree as ET

import httpx
from collections import defaultdict
from api.database import get_conn

logger = logging.getLogger(__name__)

ECFR_BASE_URL = "https://www.ecfr.gov"

def _add_cfr_refs(agency_map, slug, cfr_references):
    """Add an agency's cfr_references to the (title, chapter) -> [slugs] mapping."""
    for ref in cfr_references:
        # ~10 agencies use "subtitle" instead of "chapter". Skipping these
        # means those agencies won't get word counts/checksums. Fixable by
        # mapping subtitles to chapters via the structure endpoint.
        if "chapter" not in ref:
            continue
        key = (ref["title"], ref["chapter"])
        agency_map[key].append(slug)

def fetch_agencies():
    """Fetch all agencies, upsert into DB, return {(title, chapter): [slugs]} mapping."""
    response = httpx.get(f"{ECFR_BASE_URL}/api/admin/v1/agencies.json")
    response.raise_for_status()
    data = response.json()

    # flatten agencies and build (title, chapter) -> [slugs] mapping
    agencies = []
    agency_map = defaultdict(list)

    for agency in data["agencies"]:
        agencies.append({
            "name": agency["name"],
            "short_name": agency["short_name"],
            "slug": agency["slug"],
            "parent_slug": None
        })
        _add_cfr_refs(agency_map, agency["slug"], agency.get("cfr_references", []))

        for child in agency["children"]:
            agencies.append({
                "name": child["name"],
                "short_name": child["short_name"],
                "slug": child["slug"],
                "parent_slug": agency["slug"]
            })
            _add_cfr_refs(agency_map, child["slug"], child.get("cfr_references", []))

    # upsert into database
    with get_conn() as conn:
        with conn.cursor() as cur:
            for a in agencies:
                cur.execute("""
                    INSERT INTO agencies (name, slug, short_name, parent_slug)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE
                    SET name = EXCLUDED.name,
                        short_name = EXCLUDED.short_name,
                        parent_slug = EXCLUDED.parent_slug
                """, (a["name"], a["slug"], a["short_name"], a["parent_slug"]))
        conn.commit()

    return agency_map


def fetch_title_metadata():
    """Fetch metadata for all CFR titles. Returns {title_number: {latest_amended_on, up_to_date_as_of}}."""
    response = httpx.get(f"{ECFR_BASE_URL}/api/versioner/v1/titles.json")
    response.raise_for_status()
    data = response.json()

    titles = {}
    for title in data["titles"]:
        # reserved titles have no content, skip them
        if title.get("reserved"):
            continue
        titles[title["number"]] = {
            "latest_amended_on": title["latest_amended_on"],
            "up_to_date_as_of": title["up_to_date_as_of"],
        }
    return titles

def _find_nodes(parent_node, target_type):
    """Recursively find all descendant nodes matching target_type."""
    nodes = []
    for child in parent_node.get("children", []):
        if child["type"] == target_type:
            nodes.append(child)
        else:
            nodes.extend(_find_nodes(child, target_type))
    return nodes 

def fetch_titles_structure(title_number, date):
    """Fetch title structure and build {part_identifier: chapter_identifier} mapping."""
    response = httpx.get(f"{ECFR_BASE_URL}/api/versioner/v1/structure/{date}/title-{title_number}.json")
    response.raise_for_status()
    data = response.json()

    chapters_nodes = _find_nodes(data, "chapter")

    part_map = {}

    for chapter in chapters_nodes:
        part_nodes = _find_nodes(chapter, "part")
        for part in part_nodes:
            part_map[part["identifier"]] = chapter["identifier"]

    return part_map


def process_title_content(title_number, date, agency_map, agency_hashers):
    """Fetch XML for a title, parse chapters, compute word counts per agency.

    Returns {agency_slug: word_count}. Updates agency_hashers in-place so
    text is hashed per-chapter and never accumulated in memory. Uses iterparse
    and a temp file so large titles don't blow up memory on Render.
    """
    response = httpx.get(
        f"{ECFR_BASE_URL}/api/versioner/v1/full/{date}/title-{title_number}.xml",
        timeout=120.0,
    )
    response.raise_for_status()

    results = defaultdict(int)

    # Write XML to a temp file and free response from memory, then
    # stream-parse from disk. This keeps memory bounded: the XML bytes
    # live on disk, and iterparse only builds one chapter's tree at a time.
    with tempfile.TemporaryFile() as tmp:
        tmp.write(response.content)
        del response
        tmp.seek(0)

        for event, elem in ET.iterparse(tmp, events=("end",)):
            if elem.tag != "DIV3":
                continue
            if elem.get("TYPE") != "CHAPTER":
                elem.clear()
                continue
            chapter = elem.get("N")
            if not chapter:
                elem.clear()
                continue

            text = " ".join(elem.itertext())
            key = (title_number, chapter)

            for slug in agency_map.get(key, []):
                results[slug] += len(text.split())
                agency_hashers[slug].update(text.encode())

            elem.clear()

    return dict(results)

def process_title_versions(title_number, date, agency_map):
    """Fetch version history for a title, map to agencies, categorize changes.

    Returns {agency_slug: {period: {substantive: N, non_substantive: N, removals: N}}}.
    """
    part_map = fetch_titles_structure(title_number, date)

    response = httpx.get(f"{ECFR_BASE_URL}/api/versioner/v1/versions/title-{title_number}.json", timeout=120.0)
    response.raise_for_status()
    data = response.json()

    results = defaultdict(lambda: defaultdict(lambda: {"substantive": 0, "non_substantive": 0, "removals": 0}))

    for entry in data["content_versions"]:
        chapter = part_map.get(entry["part"])
        if not chapter:
            continue

        slugs = agency_map.get((title_number, chapter), [])
        if not slugs:
            continue

        period = entry["amendment_date"][:7]

        for slug in slugs:
            if entry["removed"]:
                results[slug][period]["removals"] += 1
            elif entry["substantive"]:
                results[slug][period]["substantive"] += 1
            else:
                results[slug][period]["non_substantive"] += 1

    return dict(results)

def run_pipeline(full_refresh=False, seed_date=None):
    """Fetch all CFR titles, compute per-agency word counts, checksums, and change history.

    Skips processing when no titles have been amended since the last run,
    unless full_refresh=True. Results are appended (not replaced) for
    word_counts and checksums to preserve history for change detection.

    seed_date: optional date string (e.g. "2026-01-01") to fetch historical
    data instead of the latest. Used on first startup to seed baseline data
    for change detection comparison.
    """
    logger.info("Pipeline started (full_refresh=%s)", full_refresh)
    agency_map = fetch_agencies()
    logger.info("Fetched %d agency-chapter mappings", len(agency_map))
    title_metadata = fetch_title_metadata()
    logger.info("Found %d active titles to process", len(title_metadata))

    # check what we've already processed to skip unchanged titles
    stored_metadata = {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title_number, latest_amended_on FROM pipeline_metadata")
            for row in cur.fetchall():
                stored_metadata[row[0]] = row[1]

    # compare the fetched title_metadata to the stored meta_data in the database. If ANY titles have a different latest_amended on, continue, otherwise nothing's changed so skip pipeline
    if not full_refresh:
        has_changes = any(
            stored_metadata.get(t) != dates["latest_amended_on"]
            for t, dates in title_metadata.items()
        )
        if not has_changes:
            return

    agency_word_counts = defaultdict(int)
    agency_hashers = defaultdict(hashlib.sha256)
    agency_history = defaultdict(lambda: defaultdict(lambda: {"substantive": 0, "non_substantive": 0, "removals": 0}))

    # process data for each title and build per-agency dicts, track process for logging with i = current title being processed
    for i, (title_number, title_dates) in enumerate(title_metadata.items(), 1):
        logger.info("Processing title %d (%d/%d)", title_number, i, len(title_metadata))

        # title content for word count; hashers are updated inside the function
        content_date = seed_date or title_dates["up_to_date_as_of"]
        title_content = process_title_content(title_number, content_date, agency_map, agency_hashers)

        for slug, word_count in title_content.items():
            agency_word_counts[slug] += word_count

        # title versions for change history per agency
        title_versions = process_title_versions(title_number, title_dates["up_to_date_as_of"], agency_map)

        for slug, period_history in title_versions.items():
            for period, change_counts in period_history.items():
                agency_history[slug][period]["substantive"] += change_counts["substantive"]
                agency_history[slug][period]["non_substantive"] += change_counts["non_substantive"]
                agency_history[slug][period]["removals"] += change_counts["removals"]

    # data_date records what eCFR date this data represents, not when the
    # pipeline ran (that's computed_at). When seed_date is provided, all titles
    # use that date. Otherwise, titles may have different up_to_date_as_of
    # dates; we use the max since word counts are aggregated across titles.
    data_date = seed_date or max(d["up_to_date_as_of"] for d in title_metadata.values())

    # write all computed metrics to the database in a single transaction
    with get_conn() as conn:
        with conn.cursor() as cur:
            # change_history is a full replace (aggregated totals, not point-in-time snapshots)
            cur.execute("DELETE FROM change_history")

            for slug, word_count in agency_word_counts.items():
                cur.execute(
                    "INSERT INTO word_counts (agency_slug, word_count, data_date) VALUES (%s, %s, %s)",
                    (slug, word_count, data_date),
                )
                cur.execute(
                    "INSERT INTO checksums (agency_slug, checksum, data_date) VALUES (%s, %s, %s)",
                    (slug, agency_hashers[slug].hexdigest(), data_date),
                )

            for slug, periods in agency_history.items():
                for period, counts in periods.items():
                    cur.execute(
                        """INSERT INTO change_history
                           (agency_slug, period, substantive, non_substantive, removals)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (slug, period, counts["substantive"], counts["non_substantive"], counts["removals"]),
                    )

            # record what we processed so incremental refresh knows what's current
            for title_number, title_dates in title_metadata.items():
                cur.execute(
                    """INSERT INTO pipeline_metadata (title_number, latest_amended_on, last_fetched_at)
                       VALUES (%s, %s, NOW())
                       ON CONFLICT (title_number) DO UPDATE
                       SET latest_amended_on = EXCLUDED.latest_amended_on,
                           last_fetched_at = NOW()""",
                    (title_number, title_dates["latest_amended_on"]),
                )

        conn.commit()
    logger.info("Pipeline complete: %d agencies with metrics", len(agency_word_counts))
