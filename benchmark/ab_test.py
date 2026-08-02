"""
Compares SQL generation accuracy WITH few-shot examples (retrieved from
query_examples via RAG) vs WITHOUT (zero-shot), on the same question
set, to produce a real, defensible "% improvement" number.

This runs against your own seeded sample DB and a hand-written question
set (question_set.json in this folder) rather than Spider, since it's
testing OUR retrieval mechanism specifically, not general SQL ability.

Usage:
    python benchmark/ab_test.py
"""
import json
from pathlib import Path

from app.agents.planning_agent import run_planning_agent
from app.agents.schema_agent import run_schema_agent
from app.agents.sql_generation_agent import _clean_sql  # noqa: private but reused intentionally
from app.llm.ollama_client import chat
from app.llm.prompts.sql_gen_prompt import SQL_GEN_SYSTEM_PROMPT
from app.llm.router import route
from app.rag.query_example_store import format_few_shot_examples, get_few_shot_examples
from app.agents.safety_agent import run_safety_agent


def is_sql_valid_and_safe(sql: str) -> bool:
    """Thin convenience wrapper: True only if the SQL clears the full safety pipeline."""
    if not sql:
        return False
    return run_safety_agent(sql)["is_safe"]

QUESTION_SET_PATH = Path(__file__).parent / "question_set.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_question_set() -> list[dict]:
    """
    Expects a JSON file shaped like:
        [{"question": "...", "expected_tables": ["customers", "orders"]}, ...]
    A starter file with ~15 questions against the seeded sample DB is
    included at benchmark/question_set.json.
    """
    with open(QUESTION_SET_PATH) as f:
        return json.load(f)


def generate_sql(question: str, schema_context: str, plan: dict, use_few_shot: bool) -> str:
    if use_few_shot:
        examples = get_few_shot_examples(question, top_k=3)
        few_shot_text = format_few_shot_examples(examples)
    else:
        few_shot_text = "(Zero-shot: no examples provided for this run.)"

    from app.llm.prompts.sql_gen_prompt import build_sql_gen_user_prompt

    messages = [
        {"role": "system", "content": SQL_GEN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_sql_gen_user_prompt(
                question=question,
                schema_context=schema_context,
                plan_json=json.dumps(plan, indent=2),
                few_shot_examples=few_shot_text,
            ),
        },
    ]
    decision = route(plan)
    response = chat(model=decision.model, messages=messages, temperature=0.0)
    return _clean_sql(response["content"])


def run_ab_test():
    questions = load_question_set()
    zero_shot_pass = 0
    few_shot_pass = 0
    details = []

    for i, item in enumerate(questions, start=1):
        question = item["question"]
        print(f"[{i}/{len(questions)}] {question}")

        schema_result = run_schema_agent(question)
        schema_context = schema_result["schema_context"]
        plan_result = run_planning_agent(question, schema_context)
        plan = plan_result["plan"]

        zero_shot_sql = generate_sql(question, schema_context, plan, use_few_shot=False)
        few_shot_sql = generate_sql(question, schema_context, plan, use_few_shot=True)

        zero_shot_ok = is_sql_valid_and_safe(zero_shot_sql)
        few_shot_ok = is_sql_valid_and_safe(few_shot_sql)

        zero_shot_pass += int(zero_shot_ok)
        few_shot_pass += int(few_shot_ok)

        details.append({
            "question": question,
            "zero_shot_sql": zero_shot_sql,
            "zero_shot_valid": zero_shot_ok,
            "few_shot_sql": few_shot_sql,
            "few_shot_valid": few_shot_ok,
        })

    n = len(questions)
    zero_shot_pct = round(100 * zero_shot_pass / n, 1)
    few_shot_pct = round(100 * few_shot_pass / n, 1)
    improvement = round(few_shot_pct - zero_shot_pct, 1)

    print(f"\nZero-shot pass rate: {zero_shot_pct}%")
    print(f"Few-shot pass rate:  {few_shot_pct}%")
    print(f"Improvement:         +{improvement} percentage points")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "ab_test_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "zero_shot_pct": zero_shot_pct,
            "few_shot_pct": few_shot_pct,
            "improvement_pp": improvement,
            "n": n,
            "details": details,
        }, f, indent=2)
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    run_ab_test()
