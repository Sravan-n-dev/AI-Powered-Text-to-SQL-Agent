from app.safety.permission_enforcer import check_permissions


def test_select_is_allowed():
    result = check_permissions("SELECT * FROM customers")
    assert result.is_allowed is True


def test_select_with_join_is_allowed():
    sql = "SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.customer_id"
    result = check_permissions(sql)
    assert result.is_allowed is True


def test_delete_is_blocked():
    result = check_permissions("DELETE FROM customers WHERE id = 1")
    assert result.is_allowed is False
    assert "read-only" in result.error_message.lower() or "blocked" in result.error_message.lower()


def test_drop_table_is_blocked():
    result = check_permissions("DROP TABLE customers")
    assert result.is_allowed is False


def test_update_is_blocked():
    result = check_permissions("UPDATE customers SET email = 'x' WHERE id = 1")
    assert result.is_allowed is False


def test_truncate_is_blocked():
    result = check_permissions("TRUNCATE TABLE orders")
    assert result.is_allowed is False


def test_insert_is_blocked():
    result = check_permissions("INSERT INTO customers (name) VALUES ('x')")
    assert result.is_allowed is False


def test_alter_is_blocked():
    result = check_permissions("ALTER TABLE customers ADD COLUMN x TEXT")
    assert result.is_allowed is False


def test_select_disguised_with_comment_trick_still_blocked():
    """
    Regression test for the exact failure mode regex-based checks miss:
    a DELETE hidden by comments/whitespace. Because we check the parsed
    statement TYPE, not raw text, this is safe regardless of formatting.
    """
    sql = "DELETE /* not a select, trust me */ FROM customers WHERE id = 1"
    result = check_permissions(sql)
    assert result.is_allowed is False
