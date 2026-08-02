"""
SQL Generation Agent. Takes the plan + schema + few-shot examples and
writes actual SQL. Uses the model router to pick a small or larger
local model based on plan complexity. On retries, the prior validation
error is appended to the prompt so the model can self-correct.
"""
import json
import logging
import re

from app.llm.ollama_client import chat
from app.llm.prompts.sql_gen_prompt import SQL_GEN_SYSTEM_PROMPT, build_sql_gen_user_prompt
from app.llm.router import route
from app.rag.query_example_store import format_few_shot_examples, get_few_shot_examples

logger = logging.getLogger(__name__)


def _clean_sql(text: str) -> str:
    """Strips markdown fences and stray commentary the model might add despite instructions."""
    text = text.strip()
    # Strip ```sql ... ``` or ``` ... ``` fences if present.
    fence_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    return text.strip().rstrip(";").strip()


def run_sql_generation_agent(
    question: str,
    schema_context: str,
    plan: dict,
    prior_error: str | None = None,
) -> dict:
    """
    Returns {"sql": str, "routing_model": str, "routing_reason": str, "cost_record": {...}}
    """
    routing_decision = route(plan)

    few_shot = get_few_shot_examples(question, top_k=3)
    few_shot_text = format_few_shot_examples(few_shot)

    messages = [
        {"role": "system", "content": SQL_GEN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_sql_gen_user_prompt(
                question=question,
                schema_context=schema_context,
                plan_json=json.dumps(plan, indent=2),
                few_shot_examples=few_shot_text,
                prior_error=prior_error,
            ),
        },
    ]

    response = chat(model=routing_decision.model, messages=messages, temperature=0.0)
    sql = _clean_sql(response["content"])

    cost_record = {
        "agent": "sql_generation_agent",
        "model": response["model"],
        "prompt_tokens": response["prompt_tokens"],
        "completion_tokens": response["completion_tokens"],
        "latency_seconds": response["latency_seconds"],
    }

    return {
        "sql": sql,
        "routing_model": routing_decision.model,
        "routing_reason": routing_decision.reason,
        "cost_record": cost_record,
    }
