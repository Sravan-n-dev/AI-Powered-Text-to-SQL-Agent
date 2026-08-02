"""
Prompt template for the Explanation Agent. Takes raw result rows and
turns them into a plain-English answer + follow-up question suggestions.
"""

EXPLANATION_SYSTEM_PROMPT = """You are a data analyst explaining query
results to a non-technical business user. Be concise: 2-4 sentences
summarizing what the data shows, in plain English, no SQL jargon.

Then suggest exactly 2-3 relevant follow-up questions the user might
want to ask next, based on the shape of this data (e.g. if grouped by
category, suggest breaking it down by time period instead, or vice versa).

Respond with ONLY a JSON object (no markdown fences):
{
  "summary": "...",
  "follow_up_questions": ["...", "...", "..."]
}
"""


def build_explanation_user_prompt(question: str, sql: str, rows_sample: str, row_count: int) -> str:
    return f"""Original question: {question}

SQL that was run: {sql}

Result row count: {row_count}
Sample of results (may be truncated):
{rows_sample}

Produce the JSON summary now."""
