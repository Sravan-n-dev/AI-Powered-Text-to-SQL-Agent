"""
FAILURE MODE: the model invents a plausible-sounding column that
doesn't actually exist on the table (e.g. "total_spent" on customers,
when that's actually a derived/aggregated value, not a real column).
"""
import pytest

from app.agents.safety_agent import run_safety_agent

pytestmark = pytest.mark.integration


def test_hallucinated_column_is_caught():
    sql = "SELECT customer_id, total_spent FROM customers"
    result = run_safety_agent(sql)
    assert result["is_safe"] is False
    assert "total_spent" in result["error"]


def test_real_column_passes():
    sql = "SELECT customer_id, email FROM customers LIMIT 5"
    result = run_safety_agent(sql)
    assert result["is_safe"] is True
