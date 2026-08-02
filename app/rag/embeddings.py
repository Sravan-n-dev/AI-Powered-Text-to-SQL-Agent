"""
Single point of truth for turning text into vectors, so schema indexing
and query-time retrieval always use the identical embedding model
(mismatched models would silently break similarity search).
"""
from app.llm.ollama_client import embed as _ollama_embed


def get_embedding(text: str) -> list[float]:
    return _ollama_embed(text)
