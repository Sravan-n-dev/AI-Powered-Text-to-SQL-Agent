"""
FAILURE MODE: the question doesn't clearly map to one interpretation
("top customers" -- by revenue? by order count? by recency?). This
isn't something a validator can catch (the SQL might be perfectly
valid, safe, and cheap) -- it's a PLANNING quality issue.

Expected behavior: the Planning Agent is instructed to pick the most
reasonable interpretation AND explain its choice in "reasoning", so
the ambiguity is at least surfaced rather than silently guessed. This
test checks that the planning prompt contract requires a reasoning
field for exactly this reason.
"""
from app.llm.prompts.planning_prompt import PLANNING_SYSTEM_PROMPT


def test_planning_prompt_requires_reasoning_field():
    """
    Documents the design decision rather than testing live model output
    (which needs Ollama running and is non-deterministic). The contract
    itself is the guardrail: reasoning must always be requested.
    """
    assert '"reasoning"' in PLANNING_SYSTEM_PROMPT
    assert "ambiguous" in PLANNING_SYSTEM_PROMPT.lower()


def test_ambiguous_plan_example_structure():
    """
    Example of what a resolved-but-ambiguous plan should look like for
    "top customers" -- picking revenue as the metric and saying so.
    This is a documentation-style test: it doesn't call the LLM, it
    pins down what a CORRECT resolution looks like so a human reviewer
    (or a future eval script) has a concrete target to compare against.
    """
    example_plan = {
        "tables": ["customers", "orders", "order_items"],
        "aggregations": [{"function": "SUM", "column": "order_items.quantity", "alias": "total_revenue"}],
        "order_by": [{"column": "total_revenue", "direction": "DESC"}],
        "limit": 10,
        "reasoning": "Interpreted 'top customers' as ranked by total revenue, "
                      "since no metric was specified.",
    }
    assert "reasoning" in example_plan
    assert example_plan["order_by"][0]["direction"] == "DESC"
