"""
The single state object that flows through all 5 agent nodes in the
LangGraph state machine. Each node reads what it needs and writes its
own output field(s) — nothing gets deleted, so the full history of a
request is inspectable at the end (useful for debugging + the cost
tracker's per_agent breakdown).
"""
from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # --- Input ---
    question: str

    # --- Schema Understanding Agent output ---
    schema_chunks: list[dict]
    schema_context: str  # formatted string for prompts

    # --- Query Planning Agent output ---
    plan: dict  # parsed JSON plan, see prompts/planning_prompt.py

    # --- SQL Generation Agent output ---
    sql: str
    routing_model: str
    routing_reason: str

    # --- Safety Agent output ---
    is_safe: bool
    safety_error: Optional[str]
    estimated_rows: Optional[int]

    # --- Execution output ---
    execution_success: bool
    result_rows: list[dict]
    row_count: int
    truncated: bool
    execution_error: Optional[str]

    # --- Explanation Agent output ---
    summary: str
    follow_up_questions: list[str]

    # --- Control flow / bookkeeping ---
    retry_count: int
    error_history: list[str]
    needs_clarification: bool
    final_status: str  # "success" | "clarification_needed" | "failed"

    # --- Cost tracking ---
    cost_records: list[dict]
