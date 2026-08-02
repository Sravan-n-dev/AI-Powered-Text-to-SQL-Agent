"""
Requires: docker-compose up -d postgres  AND  python scripts/seed_sample_db.py
"""
import pytest

from app.safety.cost_estimator import estimate_cost

pytestmark = pytest.mark.integration


def test_small_query_is_acceptable():
    result = estimate_cost("SELECT * FROM customers LIMIT 10")
    assert result.is_acceptable is True


def test_tiny_max_rows_threshold_rejects_query():
    # Force a threshold of 0 to prove the rejection path works, without
    # needing a genuinely huge table in the small sample dataset.
    result = estimate_cost("SELECT * FROM customers", max_rows=0)
    assert result.is_acceptable is False
    assert "exceeds the safety limit" in result.error_message


def test_invalid_sql_returns_error_not_crash():
    result = estimate_cost("SELECT * FROM this_table_does_not_exist")
    assert result.is_acceptable is False
    assert result.error_message is not None
