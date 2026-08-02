"""
Prompt template for the Query Planning Agent. Its job: turn a question
+ retrieved schema into a structured JSON plan, NOT SQL yet. Forcing
JSON output here is what lets the router (router.py) score complexity
programmatically instead of guessing from free text.
"""

PLANNING_SYSTEM_PROMPT = """You are a query planning assistant. You do NOT write SQL.
You break a natural language question into a structured JSON plan using
ONLY the schema information provided to you. Never invent tables or
columns that are not in the provided schema.

Respond with ONLY a JSON object (no markdown fences, no commentary) in
exactly this shape:

{
  "tables": ["table1", "table2"],
  "joins": [{"left": "table1.col", "right": "table2.col"}],
  "filters": [{"column": "table.col", "operator": "=", "value": "..."}],
  "aggregations": [{"function": "SUM", "column": "table.col", "alias": "total"}],
  "group_by": ["table.col"],
  "order_by": [{"column": "total", "direction": "DESC"}],
  "limit": 10,
  "has_subquery": false,
  "needs_window_function": false,
  "reasoning": "one sentence explaining the approach"
}

Omit keys that don't apply (e.g. no aggregations -> omit "aggregations" or use []).
If the question is ambiguous (e.g. "top customers" without specifying by what metric),
pick the most reasonable interpretation and say so in "reasoning".
"""


def build_planning_user_prompt(question: str, schema_context: str) -> str:
    return f"""Available schema (retrieved as relevant to this question):
{schema_context}

User question: {question}

Produce the JSON plan now."""
