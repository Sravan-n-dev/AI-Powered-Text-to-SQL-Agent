"""
End-to-end test of the full 5-agent pipeline. Requires EVERYTHING
running: Postgres seeded + schema indexed + Ollama with models pulled.
This is the real "does it actually work" test — run it last, after all
the setup steps in the README.

    pytest tests/test_graph_flow.py -v -m integration
"""
import pytest

from app.graph.build_graph import run_pipeline

pytestmark = pytest.mark.integration


def test_simple_question_end_to_end():
    result = run_pipeline("How many customers are there?")
    assert result["final_status"] in ("success", "clarification_needed")
    if result["final_status"] == "success":
        assert result["execution_success"] is True
        assert result["sql"]
        assert "customers" in result["sql"].lower()


def test_join_question_end_to_end():
    result = run_pipeline("What is the total revenue by product category?")
    assert result["final_status"] in ("success", "clarification_needed")
    if result["final_status"] == "success":
        assert result["row_count"] >= 0
        assert result["summary"]


def test_unsafe_request_is_never_executed():
    """
    Even if phrased as a request to delete data, the pipeline must never
    produce or execute a write statement -- the Planning/SQL agents are
    only ever prompted to produce SELECT, and the safety pipeline is the
    backstop regardless.
    """
    result = run_pipeline("Delete all customers who haven't ordered anything")
    # Whatever SQL was generated (if any), it must have been blocked as
    # unsafe or never reached a successful write execution.
    assert result.get("execution_success") is not True or (
        result.get("sql", "").strip().upper().startswith("SELECT")
    )
