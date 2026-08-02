"""
Routes each SQL generation call to a cheaper or heavier local model
based on estimated query complexity. This is the local-only analogue
of "route simple prompts to GPT-4o-mini, complex ones to GPT-4o" — the
same idea, just applied to Ollama model sizes instead of API tiers.

Complexity signal comes from the Query Planning Agent's structured
plan (see app/graph/state.py -> QueryPlan), not from the raw question,
because the plan is what actually determines how hard the SQL is to
write correctly.
"""
from dataclasses import dataclass

from app.config import settings


@dataclass
class RoutingDecision:
    model: str
    reason: str
    complexity_score: int


def score_plan_complexity(plan: dict) -> int:
    """
    Very simple, explainable heuristic — deliberately not a black box,
    since "why did you route here" needs to be answerable in an interview.

    Score components:
      +1 per table joined beyond the first
      +2 if any aggregation function is used
      +2 if a subquery / nested filter is present
      +1 if window functions are needed (ranking, running totals, etc.)
      +1 if more than 2 filter conditions are present
    """
    score = 0
    tables = plan.get("tables", [])
    score += max(0, len(tables) - 1)

    if plan.get("aggregations"):
        score += 2

    if plan.get("has_subquery"):
        score += 2

    if plan.get("needs_window_function"):
        score += 1

    filters = plan.get("filters", [])
    if len(filters) > 2:
        score += 1

    return score


def route(plan: dict) -> RoutingDecision:
    """
    score 0-2  -> small/fast model (qwen2.5-coder:3b)
    score 3+   -> heavier model (qwen2.5-coder:7b), better at multi-join
                  reasoning, at the cost of latency.

    Threshold of 3 is a deliberate, tunable choice — log actual
    (score, success/failure) pairs in production and adjust it based
    on real accuracy data rather than leaving it as a guess forever.
    """
    score = score_plan_complexity(plan)
    if score <= 2:
        return RoutingDecision(
            model=settings.ollama_sql_model,
            reason=f"complexity score {score} <= 2: single/simple join, no heavy aggregation",
            complexity_score=score,
        )
    return RoutingDecision(
        model=settings.ollama_complex_model,
        reason=f"complexity score {score} >= 3: multi-join or aggregation/subquery present",
        complexity_score=score,
    )
