import threading

from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.database import create_tables, get_conn
from api.pipeline import run_pipeline
from api.routes.agencies import router

@asynccontextmanager
async def lifespan(app):
    create_tables()

    # if the database is empty, populate it in a background thread
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM agencies")
            count = cur.fetchone()[0]

    if count == 0:
        thread = threading.Thread(target=run_pipeline, kwargs={"full_refresh": True})
        thread.daemon = True
        thread.start()

    yield

app = FastAPI(title="eCFR Analyzer", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router)