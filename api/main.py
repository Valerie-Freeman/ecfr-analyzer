import logging
import threading

from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.database import create_tables, get_conn
from api.pipeline import run_pipeline
from api.routes.agencies import router
from api.scheduler import start_scheduler, stop_scheduler

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_DATE = "2026-03-04"

def _run_pipeline_safe():
    try:
        # seed baseline data from an earlier date so change detection has
        # two data points to compare on the very first startup
        run_pipeline(full_refresh=True, seed_date=SEED_DATE)
        run_pipeline(full_refresh=True)
    except Exception:
        logger.exception("Pipeline failed")

@asynccontextmanager
async def lifespan(app):
    create_tables()

    # if the pipeline has never completed, run it in a background thread
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM pipeline_metadata")
            count = cur.fetchone()[0]

    if count == 0:
        thread = threading.Thread(target=_run_pipeline_safe)
        thread.daemon = True
        thread.start()

    # start the scheduler that runs run_pipeline(full_refresh=False) everyday at 2am
    start_scheduler()

    yield

    # stop the scheduler when the server stops
    stop_scheduler()

app = FastAPI(title="eCFR Analyzer", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router)

app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static")

@app.get("/{path:path}")
def serve_frontend(path: str):
    return HTMLResponse((STATIC_DIR / "index.html").read_text())
