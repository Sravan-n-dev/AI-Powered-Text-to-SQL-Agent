"""
Turns raw database schema (tables/columns/FKs) into embedded, searchable
chunks. This is what the Schema Understanding Agent runs once at startup
(or whenever the schema changes) — it is NOT called on every question.

Design choice: we embed at the COLUMN level (one row per column, with
the table's other columns listed as context) rather than one giant
embedding per table. Column-level embedding gives more precise
retrieval when a question mentions a specific attribute (e.g. "email")
without needing to pull in every table that merely contains it.
"""
import logging
from collections import defaultdict

from app.db.connection import get_schema_metadata
from app.db.vector_store import clear_schema_embeddings, insert_schema_embedding
from app.rag.embeddings import get_embedding

logger = logging.getLogger(__name__)


def _describe_column(table_name: str, column: dict, sibling_columns: list[str]) -> str:
    """
    Builds a natural-language description of a single column for embedding.
    Deliberately template-based (not LLM-generated) — it's fast, free,
    deterministic, and good enough for retrieval; save the LLM calls for
    steps that actually need reasoning.
    """
    parts = [
        f"Table '{table_name}', column '{column['column_name']}' "
        f"of type {column['data_type']}."
    ]
    if column["is_primary_key"]:
        parts.append("This is the primary key.")
    if column["foreign_key_ref"]:
        parts.append(f"This is a foreign key referencing {column['foreign_key_ref']}.")
    if column["is_nullable"] == "NO":
        parts.append("This column is required (NOT NULL).")
    other_cols = [c for c in sibling_columns if c != column["column_name"]]
    if other_cols:
        parts.append(f"Other columns in this table: {', '.join(other_cols)}.")
    return " ".join(parts)


def build_and_store_schema_index() -> int:
    """
    Full pipeline: introspect -> describe -> embed -> store.
    Returns the number of embeddings created. Safe to re-run any time
    the schema changes — it wipes and rebuilds from scratch.
    """
    metadata = get_schema_metadata()
    if not metadata:
        logger.warning(
            "No tables found in the public schema. Did you run "
            "scripts/seed_sample_db.py yet?"
        )
        return 0

    # Group columns by table so each description can list its siblings.
    by_table: dict[str, list[dict]] = defaultdict(list)
    for row in metadata:
        by_table[row["table_name"]].append(row)

    clear_schema_embeddings()

    count = 0
    for table_name, columns in by_table.items():
        sibling_names = [c["column_name"] for c in columns]

        # One embedding per column.
        for column in columns:
            description = _describe_column(table_name, column, sibling_names)
            embedding = get_embedding(description)
            insert_schema_embedding(
                table_name=table_name,
                column_name=column["column_name"],
                description=description,
                embedding=embedding,
                metadata={
                    "data_type": column["data_type"],
                    "is_primary_key": column["is_primary_key"],
                    "foreign_key_ref": column["foreign_key_ref"],
                },
            )
            count += 1

        # One additional table-level summary embedding, useful when the
        # question names the table/entity itself (e.g. "customers")
        # rather than a specific column.
        table_summary = (
            f"Table '{table_name}' with columns: {', '.join(sibling_names)}."
        )
        table_embedding = get_embedding(table_summary)
        insert_schema_embedding(
            table_name=table_name,
            column_name=None,
            description=table_summary,
            embedding=table_embedding,
            metadata={"is_table_summary": True},
        )
        count += 1

    logger.info("Indexed %d schema embeddings across %d tables.", count, len(by_table))
    return count
