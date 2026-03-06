import hashlib
import xml.etree.ElementTree as ET

import httpx
from collections import defaultdict
from api.database import get_conn

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


def process_title_content(title_number, date, agency_map):
    """Fetch XML for a title, parse chapters, compute word counts per agency.

    Returns {agency_slug: {"word_count": int, "text": str}} with partial
    results for this title. The caller aggregates across titles, computes
    checksums from the combined text, and writes to the database.
    """
    response = httpx.get(
        f"{ECFR_BASE_URL}/api/versioner/v1/full/{date}/title-{title_number}.xml",
        timeout=120.0,
    )
    response.raise_for_status()

    # parses the xml to an element tree
    root = ET.fromstring(response.text)
    results = defaultdict(lambda: {"word_count": 0, "text": ""})

    # find all DIV3 elements in the tree
    for div3 in root.iter("DIV3"):
        # ensure the DIV3 is a chapter
        if div3.get("TYPE") != "CHAPTER":
            continue
        chapter = div3.get("N")
        if not chapter:
            continue
        
        # collect all text from the chapter and everything nested inside into one string
        text = " ".join(div3.itertext())
        # the key for the agency_map - which agencies own this chapter
        key = (title_number, chapter)

        # find the agencies that own the chapter using the agency_map dict
        # increment the word count and concatenate the chapter text for each returned agency
        for slug in agency_map.get(key, []):
            results[slug]["word_count"] += len(text.split())
            results[slug]["text"] += text

    return dict(results)

def process_title_versions(title_number, date, agency_map):
    """Fetch version history for a title, map to agencies, categorize changes.

    Returns {agency_slug: {period: {substantive: N, non_substantive: N, removals: N}}}.
    """
    part_map = fetch_titles_structure(title_number, date)

    response = httpx.get(f"{ECFR_BASE_URL}/api/versioner/v1/versions/title-{title_number}.json")
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
