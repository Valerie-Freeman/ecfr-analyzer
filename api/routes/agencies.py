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
                LEFT JOIN checksums c ON a.slug = c.agency_slug
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
                LEFT JOIN checksums c ON a.slug = c.agency_slug
                WHERE a.slug = %s
            """, (slug,))
            row = cur.fetchone()
            if not row:
                 raise HTTPException(status_code=404, detail="Agency not found")

            cur.execute("""
                SELECT period, substantive, non_substantive, removals
                FROM change_history
                WHERE agency_slug = %s
                ORDER BY period
            """, (slug,))
            rows = cur.fetchall()
    
    # calculate net growth
    total_substantive = sum(r[1] for r in rows)
    total_removals = sum(r[3] for r in rows)
    total_changes = sum(r[1] + r[2] + r[3] for r in rows)
    net_growth = (total_substantive - total_removals) / total_changes if total_changes > 0 else None


    return AgencyDetail(
        slug=row[0],
        name=row[1],
        short_name=row[2],
        word_count=row[3],
        checksum=row[4],
        computed_at=row[5],
        change_history=[
            ChangeEntry(
                period=change_row[0],
                substantive=change_row[1],
                non_substantive=change_row[2],
                removals=change_row[3],
            )
            for change_row in rows
        ],
        net_growth_ratio=net_growth
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