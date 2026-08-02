"""
Prompt template for the SQL Generation Agent. Takes the structured plan
+ schema + few-shot examples (+ optionally a prior error for retries)
and produces PostgreSQL SQL.
"""

SQL_GEN_SYSTEM_PROMPT = """You are a PostgreSQL query writer. Given a structured
query plan, the real database schema, and example queries, write ONE
syntactically correct, read-only PostgreSQL SELECT statement.

Rules:
- Output ONLY the SQL query. No markdown fences, no explanation, no commentary.
- Only SELECT statements are allowed. Never write INSERT/UPDATE/DELETE/DROP/ALTER.
- Only use tables and columns that appear in the provided schema. Never invent names.
- Always include a LIMIT clause unless the plan clearly requires all rows for an aggregate.
- Use explicit JOIN ... ON syntax, never implicit comma joins.
- Alias aggregated columns clearly (e.g. SUM(x) AS total_x).
"""


def build_sql_gen_user_prompt(
    question: str,
    schema_context: str,
    plan_json: str,
    few_shot_examples: str,
    prior_error: str | None = None,
) -> str:
    retry_block = ""
    if prior_error:
        retry_block = f"""
IMPORTANT: A previous attempt at this query failed validation with this error:
{prior_error}
Fix the issue and produce a corrected query.
"""

    return f"""Database schema:
{schema_context}

Query plan:
{plan_json}

Similar past examples:
{few_shot_examples}

User question: {question}
{retry_block}
Write the PostgreSQL SELECT query now."""
