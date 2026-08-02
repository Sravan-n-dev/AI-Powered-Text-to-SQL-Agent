"""
FAILURE MODE: SQL generation keeps failing safety checks even after
retries (e.g. the model keeps hallucinating the same wrong column no
matter how the error is rephrased). Expected behavior: after
settings.max_sql_retries attempts, the graph routes to the
clarification terminal node instead of looping forever or crashing.
"""
from app.config import settings
from app.graph.nodes import route_after_safety


def test_routes_to_retry_when_attempts_remain():
    state = {"is_safe": False, "retry_count": 0}
    assert route_after_safety(state) == "retry"


def test_routes_to_clarify_when_retries_exhausted():
    state = {"is_safe": False, "retry_count": settings.max_sql_retries}
    assert route_after_safety(state) == "clarify"


def test_routes_to_execute_when_safe():
    state = {"is_safe": True, "retry_count": 0}
    assert route_after_safety(state) == "execute"


def test_clarification_node_never_raises():
    from app.graph.nodes import clarification_node

    state = {"retry_count": 3, "error_history": ["Unknown table: foo"]}
    result = clarification_node(state)
    assert result["final_status"] == "clarification_needed"
    assert "foo" in result["summary"] or "Unknown table" in result["summary"]
