"""
Execution & Safety Agent (validation half — actual execution lives in
sandbox_executor.py, called separately after this passes). Runs the
four-stage validation pipeline in order, short-circuiting on first
failure so we don't waste a DB round-trip on cost estimation for SQL
that's already known to be unsafe.
"""
import logging

from app.safety.cost_estimator import estimate_cost
from app.safety.permission_enforcer import check_permissions
from app.safety.semantic_validator import validate_semantics
from app.safety.syntax_validator import validate_syntax

logger = logging.getLogger(__name__)


def run_safety_agent(sql: str) -> dict:
    """
    Returns:
        {"is_safe": bool, "error": str | None, "estimated_rows": int | None}
    """
    syntax_result = validate_syntax(sql)
    if not syntax_result.is_valid:
        return {"is_safe": False, "error": f"Syntax error: {syntax_result.error_message}", "estimated_rows": None}

    permission_result = check_permissions(sql)
    if not permission_result.is_allowed:
        return {"is_safe": False, "error": f"Permission denied: {permission_result.error_message}", "estimated_rows": None}

    semantic_result = validate_semantics(sql)
    if not semantic_result.is_valid:
        return {"is_safe": False, "error": f"Semantic error: {semantic_result.error_message}", "estimated_rows": None}

    cost_result = estimate_cost(sql)
    if not cost_result.is_acceptable:
        return {
            "is_safe": False,
            "error": f"Cost limit exceeded: {cost_result.error_message}",
            "estimated_rows": cost_result.estimated_rows,
        }

    return {"is_safe": True, "error": None, "estimated_rows": cost_result.estimated_rows}
