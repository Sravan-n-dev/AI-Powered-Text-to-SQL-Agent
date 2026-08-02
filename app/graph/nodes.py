"""
Each function here is a LangGraph "node": takes the full AgentState,
calls the corresponding agent, and returns a dict of the fields to
merge back into state. LangGraph merges returned dicts into state
automatically (shallow merge on top-level keys).

Keeping this as a thin adapter layer (rather than putting LangGraph
logic inside the agents themselves) means the agents stay independently
testable/importable without needing LangGraph installed at all.
"""
import logging

from app.agents.explanation_agent import run_explanation_agent
from app.agents.planning_agent import run_planning_agent
from app.agents.safety_agent import run_safety_agent
from app.agents.schema_agent import run_schema_agent
from app.agents.sql_generation_agent import run_sql_generation_agent
from app.config import settings
from app.graph.state import AgentState
from app.rag.query_example_store import store_successful_query
from app.safety.sandbox_executor import execute_safely

logger = logging.getLogger(__name__)


def schema_node(state: AgentState) -> dict:
    result = run_schema_agent(state["question"])
    return {"schema_chunks": result["schema_chunks"], "schema_context": result["schema_context"]}


def planning_node(state: AgentState) -> dict:
    try:
        result = run_planning_agent(state["question"], state["schema_context"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Planning agent failed: %s", exc)
        errors = state.get("error_history", []) + [f"Planning failed: {exc}"]
        return {"plan": {}, "error_history": errors, "needs_clarification": True}

    cost_records = state.get("cost_records", []) + [result["cost_record"]]
    return {"plan": result["plan"], "cost_records": cost_records}


def sql_generation_node(state: AgentState) -> dict:
    prior_error = None
    error_history = state.get("error_history", [])
    if error_history:
        prior_error = error_history[-1]

    try:
        result = run_sql_generation_agent(
            question=state["question"],
            schema_context=state["schema_context"],
            plan=state.get("plan", {}),
            prior_error=prior_error,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("SQL generation failed: %s", exc)
        errors = error_history + [f"SQL generation failed: {exc}"]
        return {"sql": "", "error_history": errors}

    cost_records = state.get("cost_records", []) + [result["cost_record"]]
    return {
        "sql": result["sql"],
        "routing_model": result["routing_model"],
        "routing_reason": result["routing_reason"],
        "cost_records": cost_records,
    }


def safety_node(state: AgentState) -> dict:
    sql = state.get("sql", "")
    if not sql:
        return {"is_safe": False, "safety_error": "No SQL was generated.", "estimated_rows": None}

    result = run_safety_agent(sql)
    return {
        "is_safe": result["is_safe"],
        "safety_error": result["error"],
        "estimated_rows": result["estimated_rows"],
    }


def route_after_safety(state: AgentState) -> str:
    """
    Conditional edge function. Decides where to go after the safety
    check:
      - passed              -> "execute"
      - failed, retries left -> "retry" (loop back to sql_generation)
      - failed, retries exhausted -> "clarify" (terminal, ask the user)
    """
    if state.get("is_safe"):
        return "execute"

    retry_count = state.get("retry_count", 0)
    if retry_count < settings.max_sql_retries:
        return "retry"
    return "clarify"


def increment_retry_node(state: AgentState) -> dict:
    """Bumps retry_count and appends the safety error to history before looping back."""
    error_history = state.get("error_history", []) + [state.get("safety_error", "Unknown safety failure")]
    return {
        "retry_count": state.get("retry_count", 0) + 1,
        "error_history": error_history,
    }


def execution_node(state: AgentState) -> dict:
    result = execute_safely(state["sql"])
    if result.success:
        # Feed the "continuous learning" loop: only store SQL we know
        # actually ran successfully.
        try:
            store_successful_query(state["question"], state["sql"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not store query example (non-fatal): %s", exc)

    return {
        "execution_success": result.success,
        "result_rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_error": result.error_message,
    }


def route_after_execution(state: AgentState) -> str:
    if state.get("execution_success"):
        return "explain"
    retry_count = state.get("retry_count", 0)
    if retry_count < settings.max_sql_retries:
        return "retry"
    return "clarify"


def explanation_node(state: AgentState) -> dict:
    try:
        result = run_explanation_agent(
            question=state["question"],
            sql=state["sql"],
            rows=state.get("result_rows", []),
            row_count=state.get("row_count", 0),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Explanation agent failed (non-fatal): %s", exc)
        return {
            "summary": f"Query returned {state.get('row_count', 0)} row(s).",
            "follow_up_questions": [],
            "final_status": "success",
        }

    cost_records = state.get("cost_records", []) + [result["cost_record"]]
    return {
        "summary": result["summary"],
        "follow_up_questions": result["follow_up_questions"],
        "cost_records": cost_records,
        "final_status": "success",
    }


def clarification_node(state: AgentState) -> dict:
    """
    Terminal node reached when retries are exhausted. Explains to the
    user what was attempted and why it failed, rather than silently
    giving up or crashing.
    """
    last_error = (state.get("error_history") or ["Unknown error"])[-1]
    return {
        "needs_clarification": True,
        "final_status": "clarification_needed",
        "summary": (
            f"I wasn't able to build a safe, valid query after "
            f"{state.get('retry_count', 0)} attempt(s). Last issue: {last_error}. "
            f"Could you rephrase the question or specify exact columns/tables you mean?"
        ),
        "follow_up_questions": [],
    }
