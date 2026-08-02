"""
FAILURE MODE: a query that passes safety checks but turns out to run
too long (e.g. planner underestimated cost, or an expensive function
call). Expected behavior: statement_timeout cancels it cleanly and
execute_safely returns a clear error, not a hung connection.
"""
import pytest

from app.safety.sandbox_executor import execute_safely

pytestmark = pytest.mark.integration


def test_slow_query_is_cancelled_by_timeout():
    # pg_sleep(seconds) deliberately runs longer than a very short
    # timeout we pass in, to deterministically trigger cancellation
    # without depending on real table size / data volume.
    from app.config import settings

    original_timeout = settings.query_timeout_seconds
    try:
        settings.query_timeout_seconds = 1  # 1 second, well under pg_sleep(5)
        result = execute_safely("SELECT pg_sleep(5), 1 AS x")
        assert result.success is False
        assert "timeout" in (result.error_message or "").lower()
    finally:
        settings.query_timeout_seconds = original_timeout
