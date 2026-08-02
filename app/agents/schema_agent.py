"""
Schema Understanding Agent. Does NOT call the LLM — this step is pure
retrieval (RAG), which is faster, free, and deterministic. The schema
INDEX itself (embedding all tables/columns) was already built ahead of
time by scripts/index_schema.py; this agent just queries it.
"""
import logging

from app.rag.retriever import format_schema_context, retrieve_relevant_schema

logger = logging.getLogger(__name__)


def run_schema_agent(question: str, top_k: int = 10) -> dict:
    """
    Returns {"schema_chunks": [...], "schema_context": "formatted string"}
    """
    chunks = retrieve_relevant_schema(question, top_k=top_k)
    if not chunks:
        logger.warning(
            "No schema chunks retrieved for question: %s. "
            "Did you run scripts/index_schema.py?",
            question,
        )
    context = format_schema_context(chunks)
    return {"schema_chunks": chunks, "schema_context": context}
