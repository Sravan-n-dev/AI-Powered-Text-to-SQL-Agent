"""
Query Planning Agent. Calls the LLM once to turn (question + schema)
into a structured JSON plan — no SQL yet. This decomposition step is
what handles multi-step questions like "total revenue by category for
repeat customers": identify cohort -> filter -> join -> aggregate -> group.
"""
import json
import logging

from app.config import settings
from app.llm.ollama_client import chat
from app.llm.prompts.planning_prompt import PLANNING_SYSTEM_PROMPT, build_planning_user_prompt

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """
    Local models sometimes wrap JSON in markdown fences or add stray
    text despite instructions. This strips common wrappers before
    parsing, and raises a clear error if it still can't be parsed
    (the caller/graph decides whether to retry).
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


def run_planning_agent(question: str, schema_context: str) -> dict:
    """
    Returns {"plan": {...}, "cost_record": {...}}
    Raises json.JSONDecodeError if the model's output truly isn't
    parseable JSON after cleanup — the graph node catches this and
    routes to a retry/clarification path rather than crashing.
    """
    messages = [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": build_planning_user_prompt(question, schema_context)},
    ]
    response = chat(model=settings.ollama_sql_model, messages=messages, temperature=0.1)
    plan = _extract_json(response["content"])

    cost_record = {
        "agent": "planning_agent",
        "model": response["model"],
        "prompt_tokens": response["prompt_tokens"],
        "completion_tokens": response["completion_tokens"],
        "latency_seconds": response["latency_seconds"],
    }
    return {"plan": plan, "cost_record": cost_record}
