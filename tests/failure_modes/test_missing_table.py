"""
FAILURE MODE: the model generates SQL referencing a table that doesn't
exist (either hallucinated, or the schema changed since the last index
rebuild). Expected behavior: semantic_validator catches it and the
safety agent reports a clear, specific error — the query never reaches
execution.
"""
import pytest

from app.agents.safety_agent import run_safety_agent

pytestmark = pytest.mark.integration


def test_missing_table_is_caught_before_execution():
    sql = "SELECT * FROM invoices_that_do_not_exist"
    result = run_safety_agent(sql)
    assert result["is_safe"] is False
    assert "invoices_that_do_not_exist" in result["error"]
