"""
pgvector-backed storage for two things:
  1. `schema_embeddings` — one row per table/column description, used
     by the Schema Understanding Agent for RAG retrieval.
  2. `query_examples`    — one row per successfully executed
     (question, sql) pair, used as few-shot examples for SQL generation.

We use raw SQL rather than an ORM here because pgvector's similarity
operators (`<=>` for cosine distance) aren't first-class in SQLAlchemy
without extra setup, and being explicit is clearer for a project like
this anyway.
"""
import json
import logging

from app.db.connection import get_raw_connection

logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dimensional vectors.
EMBEDDING_DIM = 768


def init_vector_store() -> None:
    """
    Creates the pgvector extension (if missing) and the two tables this
    project needs. Safe to call repeatedly — uses IF NOT EXISTS.
    """
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS schema_embeddings (
                    id SERIAL PRIMARY KEY,
                    table_name TEXT NOT NULL,
                    column_name TEXT,
                    description TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}) NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            # IVFFlat index for fast approximate nearest-neighbor search.
            # Only useful once you have enough rows (100+); harmless before that.
            cur.execute("""
                CREATE INDEX IF NOT EXISTS schema_embeddings_ivfflat
                ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 10);
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS query_examples (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    sql_query TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}) NOT NULL,
                    was_successful BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS query_examples_ivfflat
                ON query_examples USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 10);
            """)
        conn.commit()
        logger.info("Vector store initialized (schema_embeddings, query_examples).")
    finally:
        conn.close()


def clear_schema_embeddings() -> None:
    """Wipes schema embeddings so a re-index starts fresh (schema may have changed)."""
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE schema_embeddings RESTART IDENTITY;")
        conn.commit()
    finally:
        conn.close()


def insert_schema_embedding(
    table_name: str,
    column_name: str | None,
    description: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> None:
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schema_embeddings
                    (table_name, column_name, description, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (table_name, column_name, description, embedding, json.dumps(metadata or {})),
            )
        conn.commit()
    finally:
        conn.close()


def search_schema_embeddings(query_embedding: list[float], top_k: int = 8) -> list[dict]:
    """
    Returns the top_k most similar schema chunks to the query embedding,
    ordered by cosine distance (smaller = more similar).
    """
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name, description, metadata,
                       embedding <=> %s::vector AS distance
                FROM schema_embeddings
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_embedding, top_k),
            )
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()


def insert_query_example(question: str, sql_query: str, embedding: list[float]) -> None:
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_examples (question, sql_query, embedding)
                VALUES (%s, %s, %s)
                """,
                (question, sql_query, embedding),
            )
        conn.commit()
    finally:
        conn.close()


def search_query_examples(query_embedding: list[float], top_k: int = 3) -> list[dict]:
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT question, sql_query, embedding <=> %s::vector AS distance
                FROM query_examples
                WHERE was_successful = TRUE
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_embedding, top_k),
            )
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()
