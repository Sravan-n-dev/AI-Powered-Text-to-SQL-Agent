"""
Requires: docker-compose up -d postgres  AND  python scripts/seed_sample_db.py
have both been run first (see README).
"""
import pytest

from app.safety.semantic_validator import validate_semantics

pytestmark = pytest.mark.integration


def test_valid_table_and_columns_pass():
    result = validate_semantics("SELECT customer_id, email FROM customers")
    assert result.is_valid is True


def test_unknown_table_is_rejected():
    result = validate_semantics("SELECT * FROM nonexistent_table")
    assert result.is_valid is False
    assert "nonexistent_table" in result.unknown_tables


def test_unknown_column_is_rejected():
    result = validate_semantics("SELECT made_up_column FROM customers")
    assert result.is_valid is False
    assert "made_up_column" in result.unknown_columns


def test_valid_multi_table_join_passes():
    sql = """
        SELECT c.customer_id, o.order_id
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
    """
    result = validate_semantics(sql)
    assert result.is_valid is True
