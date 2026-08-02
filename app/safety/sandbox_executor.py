"""
Layer 5 of the safety pipeline: actually run the query, but only after
it has passed syntax, semantic, permission, and cost checks. Runs
inside a READ ONLY transaction with a statement timeout, and ALWAYS
rolls back regardless of outcome (belt-and-suspenders even though a
SELECT never writes anything).

Row results are capped defensively (LIMIT-wrapped) even if the LLM
forgot to add a LIMIT, so a runaway query that slipped past cost
estimation still can't flood the response payload.
"""
from dataclasses import dataclass, field

import psycopg2

from app.config import settings
from app.db.connection import read_only_cursor

DEFAULT_ROW_CAP = 1000


@dataclass
class ExecutionResult:
    success: bool
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error_message: str | None = None


def execute_safely(sql: str, row_cap: int = DEFAULT_ROW_CAP) -> ExecutionResult:
    # Defensive row cap: wrap in a subquery with LIMIT so even a query
    # that already has no LIMIT of its own can't return unbounded rows,
    # regardless of what the cost estimator predicted.
    capped_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS _subquery LIMIT {row_cap + 1}"

    try:
        with read_only_cursor(timeout_seconds=settings.query_timeout_seconds) as cur:
            cur.execute(capped_sql)
            rows = cur.fetchall()
    except psycopg2.errors.QueryCanceled:
        return ExecutionResult(
            success=False,
            error_message=(
                f"Query exceeded the {settings.query_timeout_seconds}s timeout and was "
                f"cancelled. Try narrowing the date range or adding more filters."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(success=False, error_message=str(exc))

    truncated = len(rows) > row_cap
    if truncated:
        rows = rows[:row_cap]

    return ExecutionResult(
        success=True,
        rows=[dict(r) for r in rows],
        row_count=len(rows),
        truncated=truncated,
    )
