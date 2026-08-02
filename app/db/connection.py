"""
Connection to the TARGET database — the one the agent generates and
executes SQL against. In this project it's the same physical Postgres
instance as the vector store, but conceptually treat it as separate:
in production these would likely be different databases entirely.
"""
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from app.config import settings

logger = logging.getLogger(__name__)


def get_raw_connection():
    """
    Returns a plain psycopg2 connection. We use raw psycopg2 (rather than
    only SQLAlchemy) for the execution/safety layer because we need
    fine-grained control over transaction mode (READ ONLY) and statement
    timeouts, which is more explicit this way.
    """
    return psycopg2.connect(settings.database_url)


@contextmanager
def read_only_cursor(timeout_seconds: int | None = None):
    """
    Context manager that yields a cursor running inside a READ ONLY
    transaction with an optional statement timeout. Always rolls back
    at the end — even for pure SELECTs — as an extra safety net so a
    bug elsewhere can never accidentally persist a write.

    Usage:
        with read_only_cursor(timeout_seconds=10) as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    """
    conn = get_raw_connection()
    timeout_seconds = timeout_seconds or settings.query_timeout_seconds
    try:
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SET statement_timeout = {int(timeout_seconds * 1000)}")
        yield cur
    finally:
        # Always rollback: never persist anything from this path, ever.
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        conn.close()


def get_schema_metadata() -> list[dict]:
    """
    Introspects the target database and returns a flat list of dicts,
    one per column, describing the full schema:
        table_name, column_name, data_type, is_nullable,
        is_primary_key, foreign_key_ref (or None)

    This is the raw material the Schema Understanding Agent turns into
    natural-language descriptions for embedding.
    """
    query = """
        SELECT
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_name = c.table_name
                    AND kcu.column_name = c.column_name
            ) AS is_primary_key,
            (
                SELECT ccu.table_name || '.' || ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = c.table_name
                    AND kcu.column_name = c.column_name
                LIMIT 1
            ) AS foreign_key_ref
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        ORDER BY c.table_name, c.ordinal_position;
    """
    with read_only_cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return [dict(row) for row in rows]
