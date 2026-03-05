from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.database import create_tables

@asynccontextmanager
async def lifespan(app):
    create_tables()
    yield

app = FastAPI(title="eCFR Analyzer", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}