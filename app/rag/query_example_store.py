"""
The "continuous learning" piece: every successfully executed
(question, SQL) pair gets embedded and stored. Future similar
questions retrieve these as few-shot examples for SQL generation,
which is what the A/B test (few-shot vs zero-shot) measures the
benefit of.
"""
import logging

from app.db.vector_store import insert_query_example, search_query_examples
from app.rag.embeddings import get_embedding

logger = logging.getLogger(__name__)


def store_successful_query(question: str, sql_query: str) -> None:
    embedding = get_embedding(question)
    insert_query_example(question, sql_query, embedding)
    logger.info("Stored successful query example: %s", question[:80])


def get_few_shot_examples(question: str, top_k: int = 3) -> list[dict]:
    """
    Returns up to top_k similar past (question, sql) pairs to include
    as few-shot examples in the SQL generation prompt. Returns an empty
    list gracefully if the store is empty (e.g. very first query ever).
    """
    embedding = get_embedding(question)
    examples = search_query_examples(embedding, top_k=top_k)
    return examples


def format_few_shot_examples(examples: list[dict]) -> str:
    if not examples:
        return "(No past examples available yet.)"
    lines = []
    for i, ex in enumerate(examples, start=1):
        lines.append(f"Example {i}:")
        lines.append(f"Question: {ex['question']}")
        lines.append(f"SQL: {ex['sql_query']}")
        lines.append("")
    return "\n".join(lines)
