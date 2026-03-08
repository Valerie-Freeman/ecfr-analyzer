from fastapi import APIRouter, HTTPException
from api.database import get_conn
from api.models import AgencySummary, ChangeEntry, AgencyDetail, PipelineStatus

router = APIRouter(prefix="/api")


@router.get("/agencies", response_model=list[AgencySummary])
def list_agencies():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.slug, a.name, a.short_name,
                       w.word_count, c.checksum, c.computed_at
                FROM agencies a
                LEFT JOIN word_counts w ON a.slug = w.agency_slug
                    AND w.computed_at = (SELECT MAX(computed_at) FROM word_counts)
                LEFT JOIN checksums c ON a.slug = c.agency_slug
                    AND c.computed_at = (SELECT MAX(computed_at) FROM checksums)
                ORDER BY a.name
            """)
            rows = cur.fetchall()

    return [
        AgencySummary(
            slug=row[0],
            name=row[1],
            short_name=row[2],
            word_count=row[3],
            checksum=row[4],
            computed_at=row[5],
        )
        for row in rows
    ]

@router.get("/agencies/{slug}", response_model=AgencyDetail)
def get_agency(slug: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.slug, a.name, a.short_name,
                       w.word_count, c.checksum, c.computed_at
                FROM agencies a
                LEFT JOIN word_counts w ON a.slug = w.agency_slug
                    AND w.computed_at = (SELECT MAX(computed_at) FROM word_counts)
                LEFT JOIN checksums c ON a.slug = c.agency_slug
                    AND c.computed_at = (SELECT MAX(computed_at) FROM checksums)
                WHERE a.slug = %s
            """, (slug,))
            row = cur.fetchone()
            if not row:
                 raise HTTPException(status_code=404, detail="Agency not found")

            # two most recent checksums for change detection
            cur.execute("""
                SELECT checksum, data_date FROM checksums
                WHERE agency_slug = %s
                ORDER BY computed_at DESC LIMIT 2
            """, (slug,))
            recent_checksums = cur.fetchall()

            # two most recent word counts for delta
            cur.execute("""
                SELECT word_count, data_date FROM word_counts
                WHERE agency_slug = %s
                ORDER BY computed_at DESC LIMIT 2
            """, (slug,))
            recent_word_counts = cur.fetchall()

            cur.execute("""
                SELECT period, substantive, non_substantive, removals
                FROM change_history
                WHERE agency_slug = %s
                ORDER BY period
            """, (slug,))
            history_rows = cur.fetchall()

    # compare current vs previous in Python
    checksum_changed = None
    current_data_date = None
    previous_data_date = None
    if len(recent_checksums) >= 2:
        checksum_changed = recent_checksums[0][0] != recent_checksums[1][0]
        current_data_date = recent_checksums[0][1]
        previous_data_date = recent_checksums[1][1]

    word_count_change = None
    if len(recent_word_counts) >= 2:
        word_count_change = recent_word_counts[0][0] - recent_word_counts[1][0]

    return AgencyDetail(
        slug=row[0],
        name=row[1],
        short_name=row[2],
        word_count=row[3],
        checksum=row[4],
        computed_at=row[5],
        checksum_changed=checksum_changed,
        word_count_change=word_count_change,
        current_data_date=current_data_date,
        previous_data_date=previous_data_date,
        change_history=[
            ChangeEntry(
                period=r[0],
                substantive=r[1],
                non_substantive=r[2],
                removals=r[3],
            )
            for r in history_rows
        ],
    )

@router.get("/pipeline/status", response_model=PipelineStatus)
def get_pipeline_status():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(last_fetched_at) FROM pipeline_metadata")
            last_run_at = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM pipeline_metadata")
            titles_processed = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT agency_slug) FROM word_counts")
            agencies_with_metrics = cur.fetchone()[0]

    return PipelineStatus(
        last_run_at=last_run_at,
        titles_processed=titles_processed,
        agencies_with_metrics=agencies_with_metrics,
    )