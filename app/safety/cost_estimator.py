"""
Layer 4 of the safety pipeline: before actually running the query, ask
Postgres's planner how expensive it THINKS it will be, via EXPLAIN
(not EXPLAIN ANALYZE — we never want to execute an unvalidated query
during a cost check). Reject if the estimated row count crosses the
configured threshold (default 1,000,000 rows).

This is an estimate, not a guarantee — Postgres's planner can be wrong,
especially on tables it hasn't seen much data distribution for. That's
fine: it's a heuristic guard, not a hard proof, and it's paired with
the query_timeout_seconds statement timeout as a second line of defense.
"""
import json
from dataclasses import dataclass

from app.config import settings
from app.db.connection import get_raw_connection


@dataclass
class CostEstimateResult:
    is_acceptable: bool
    estimated_rows: int
    estimated_cost: float
    error_message: str | None = None


def estimate_cost(sql: str, max_rows: int | None = None) -> CostEstimateResult:
    max_rows = max_rows if max_rows is not None else settings.max_estimated_rows

    conn = get_raw_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cur:
            try:
                cur.execute(f"EXPLAIN (FORMAT JSON) {sql}")
            except Exception as exc:  # noqa: BLE001
                return CostEstimateResult(
                    is_acceptable=False,
                    estimated_rows=0,
                    estimated_cost=0.0,
                    error_message=f"EXPLAIN failed (query likely invalid): {exc}",
                )
            plan_json = cur.fetchone()[0]
        conn.rollback()
    finally:
        conn.close()

    # psycopg2 auto-parses the `json` type to a Python list/dict, but we
    # handle the string case too in case that behavior ever changes.
    if isinstance(plan_json, str):
        plan_json = json.loads(plan_json)

    # plan_json is a list containing one dict: [{"Plan": {...}}]
    root_plan = plan_json[0]["Plan"]
    estimated_rows = root_plan.get("Plan Rows", 0)
    estimated_cost = root_plan.get("Total Cost", 0.0)

    if estimated_rows > max_rows:
        return CostEstimateResult(
            is_acceptable=False,
            estimated_rows=estimated_rows,
            estimated_cost=estimated_cost,
            error_message=(
                f"Estimated {estimated_rows:,} rows exceeds the safety limit "
                f"of {max_rows:,}. Add a filter (WHERE/LIMIT) to narrow the query."
            ),
        )

    return CostEstimateResult(
        is_acceptable=True,
        estimated_rows=estimated_rows,
        estimated_cost=estimated_cost,
    )
