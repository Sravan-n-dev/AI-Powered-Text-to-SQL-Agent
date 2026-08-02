"""
Thin wrapper around Ollama's HTTP API. Ollama exposes:
    POST /api/generate  -> text completion
    POST /api/chat       -> chat-style completion
    POST /api/embeddings -> embedding vectors

We use /api/chat for agent calls (cleaner message-history handling) and
/api/embeddings for the RAG pieces.

All calls are wrapped with tenacity retries because local model loading
can occasionally be slow/flaky on first call (cold start).
"""
import logging
import time

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> dict:
    """
    Calls Ollama's /api/chat endpoint.

    Returns a dict: {"content": str, "prompt_tokens": int, "completion_tokens": int,
                      "latency_seconds": float, "model": str}

    Raises OllamaError if the server can't be reached after retries — the
    caller (an agent) should catch this and decide how to degrade.
    """
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    start = time.monotonic()
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(
            f"Could not reach Ollama at {url}. Is the Ollama container running "
            f"and has the model '{model}' been pulled? (docker exec t2sql-ollama "
            f"ollama pull {model})"
        ) from exc

    data = resp.json()
    latency = time.monotonic() - start

    return {
        "content": data.get("message", {}).get("content", ""),
        # Ollama reports these when available; default to 0 if missing.
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "latency_seconds": round(latency, 3),
        "model": model,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def embed(text: str, model: str | None = None) -> list[float]:
    """
    Calls Ollama's /api/embeddings endpoint. Returns a list of floats.
    """
    model = model or settings.ollama_embed_model
    url = f"{settings.ollama_base_url}/api/embeddings"
    try:
        resp = requests.post(url, json={"model": model, "prompt": text}, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(
            f"Could not reach Ollama at {url} for embeddings. Is the model "
            f"'{model}' pulled? (docker exec t2sql-ollama ollama pull {model})"
        ) from exc

    data = resp.json()
    embedding = data.get("embedding")
    if not embedding:
        raise OllamaError(f"Ollama returned no embedding for model '{model}'.")
    return embedding


def health_check() -> bool:
    """Returns True if Ollama is reachable at all (used by /health endpoint)."""
    try:
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False
