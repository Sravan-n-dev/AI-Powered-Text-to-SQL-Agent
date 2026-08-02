"""
Layer 3 of the safety pipeline: is this a read-only query?

We check the PARSED statement type (via sqlglot), not a regex on raw
text — regex matching for "DELETE" can be trivially defeated by
comments, whitespace tricks, or the word appearing inside a string
literal. Checking the actual expression type is robust to all of that.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# Statement types we allow. Everything else is rejected by default
# (allow-list, not a block-list — much safer).
ALLOWED_STATEMENT_TYPES = (exp.Select,)

BLOCKED_KEYWORDS_HINT = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "MERGE", "CALL", "EXECUTE",
)


@dataclass
class PermissionResult:
    is_allowed: bool
    error_message: str | None = None


def check_permissions(sql: str) -> PermissionResult:
    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        return PermissionResult(is_allowed=False, error_message=f"Could not parse SQL: {exc}")

    if not isinstance(parsed, ALLOWED_STATEMENT_TYPES):
        stmt_type = type(parsed).__name__
        return PermissionResult(
            is_allowed=False,
            error_message=(
                f"Only read-only SELECT queries are permitted. "
                f"This statement was parsed as '{stmt_type}', which is blocked."
            ),
        )

    # Defense in depth: also reject if any write-type node appears
    # ANYWHERE nested inside the tree (catches CTEs that wrap a write,
    # e.g. `WITH x AS (DELETE ...) SELECT * FROM x` on engines that
    # allow writable CTEs). find_all() is sqlglot's documented,
    # version-stable way to walk the whole expression tree.
    write_node_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)
    for write_type in write_node_types:
        found = next(parsed.find_all(write_type), None)
        if found is not None:
            return PermissionResult(
                is_allowed=False,
                error_message=(
                    f"Write operation ({write_type.__name__}) detected "
                    f"nested inside the query. Blocked."
                ),
            )

    return PermissionResult(is_allowed=True)
