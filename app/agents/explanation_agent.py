"""
Explanation Agent. Takes execution results and produces a plain-English
summary + follow-up question suggestions. Only ever sees a SAMPLE of
rows (capped) to keep the prompt small and cheap, even if the result
set itself was large.
"""
import json
import logging

from app.config import settings
from app.llm.ollama_client import chat
from app.llm.prompts.explanation_prompt import (
    EXPLANATION_SYSTEM_PROMPT,
    build_explanation_user_prompt,
)

logger = logging.getLogger(__name__)

MAX_ROWS_IN_PROMPT = 20


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def run_explanation_agent(question: str, sql: str, rows: list[dict], row_count: int) -> dict:
    """
    Returns {"summary": str, "follow_up_questions": [...], "cost_record": {...}}
    Falls back to a generic templated summary if the model's JSON output
    can't be parsed — explanation is a nice-to-have, it should never
    crash the whole pipeline after a successful execution.
    """
    sample = rows[:MAX_ROWS_IN_PROMPT]
    rows_sample_text = json.dumps(sample, indent=2, default=str)

    messages = [
        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_explanation_user_prompt(question, sql, rows_sample_text, row_count),
        },
    ]

    response = chat(model=settings.ollama_sql_model, messages=messages, temperature=0.3)
    cost_record = {
        "agent": "explanation_agent",
        "model": response["model"],
        "prompt_tokens": response["prompt_tokens"],
        "completion_tokens": response["completion_tokens"],
        "latency_seconds": response["latency_seconds"],
    }

    try:
        parsed = _extract_json(response["content"])
        summary = parsed.get("summary", "")
        follow_ups = parsed.get("follow_up_questions", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Explanation agent returned unparseable JSON; using fallback summary.")
        summary = f"Query returned {row_count} row(s)."
        follow_ups = []

    return {"summary": summary, "follow_up_questions": follow_ups, "cost_record": cost_record}
