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

