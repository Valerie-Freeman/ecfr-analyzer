import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager 

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://ecfr:ecfr@localhost:5432/ecfr_analyzer")
# Render's managed PostgreSQL uses postgres:// but psycopg2 requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(1, 10, DATABASE_URL)
    return _pool

@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()

    try:
        yield conn
    finally:
        pool.putconn(conn)

def create_tables():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(""" 
                CREATE TABLE IF NOT EXISTS agencies (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    short_name TEXT,
                    parent_slug TEXT REFERENCES agencies(slug)
                );

                CREATE TABLE IF NOT EXISTS word_counts (
                    id SERIAL PRIMARY KEY,
                    agency_slug TEXT NOT NULL REFERENCES agencies(slug),
                    word_count INTEGER NOT NULL,
                    data_date DATE,
                    computed_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS checksums (
                    id SERIAL PRIMARY KEY,
                    agency_slug TEXT NOT NULL REFERENCES agencies(slug),
                    checksum TEXT NOT NULL,
                    data_date DATE,
                    computed_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS change_history (
                    id SERIAL PRIMARY KEY,
                    agency_slug TEXT NOT NULL REFERENCES agencies(slug),
                    period TEXT NOT NULL,
                    substantive INTEGER DEFAULT 0,
                    non_substantive INTEGER DEFAULT 0,
                    removals INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS pipeline_metadata (
                    title_number INTEGER PRIMARY KEY,
                    latest_amended_on TEXT,
                    last_fetched_at TIMESTAMP
                );
            """)
        conn.commit()