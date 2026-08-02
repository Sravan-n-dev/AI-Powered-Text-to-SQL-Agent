from app.safety.syntax_validator import validate_syntax


def test_valid_simple_select():
    result = validate_syntax("SELECT id, name FROM customers WHERE id = 1")
    assert result.is_valid is True
    assert result.error_message is None


def test_valid_join_query():
    sql = """
        SELECT c.customer_id, SUM(oi.quantity * oi.unit_price) AS total
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
        JOIN order_items oi ON oi.order_id = o.order_id
        GROUP BY c.customer_id
    """
    result = validate_syntax(sql)
    assert result.is_valid is True


def test_empty_sql_is_invalid():
    result = validate_syntax("")
    assert result.is_valid is False
    assert "Empty" in result.error_message


def test_whitespace_only_sql_is_invalid():
    result = validate_syntax("   \n\t  ")
    assert result.is_valid is False


def test_malformed_sql_is_invalid():
    result = validate_syntax("SELEC id FROM WHERE")
    assert result.is_valid is False
    assert result.error_message is not None


def test_unbalanced_parens_is_invalid():
    result = validate_syntax("SELECT * FROM orders WHERE (id = 1")
    assert result.is_valid is False
