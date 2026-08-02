"""
Query-time retrieval: given a user's natural-language question, find the
most relevant schema chunks. This is called on EVERY question (unlike
schema_indexer, which only runs on setup/schema-change).
"""
import logging

from app.db.vector_store import search_schema_embeddings
from app.rag.embeddings import get_embedding

logger = logging.getLogger(__name__)


def retrieve_relevant_schema(question: str, top_k: int = 10) -> list[dict]:
    """
    Returns the top_k schema chunks (table/column descriptions) most
    similar to the question. This is the RAG step that prevents the SQL
    Generation Agent from hallucinating table/column names — it only
    ever sees schema that's real and retrieved, never invents it.
    """
    question_embedding = get_embedding(question)
    results = search_schema_embeddings(question_embedding, top_k=top_k)
    logger.debug("Retrieved %d schema chunks for question: %s", len(results), question)
    return results


def format_schema_context(chunks: list[dict]) -> str:
    """
    Formats retrieved chunks into a compact string suitable for
    inclusion in an LLM prompt. Groups by table for readability.
    """
    by_table: dict[str, list[str]] = {}
    for chunk in chunks:
        by_table.setdefault(chunk["table_name"], []).append(chunk["description"])

    lines = []
    for table, descriptions in by_table.items():
        lines.append(f"### {table}")
        for d in descriptions:
            lines.append(f"- {d}")
    return "\n".join(lines)
