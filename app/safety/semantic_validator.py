"""
Layer 2 of the safety pipeline: even if the SQL is syntactically valid,
does it reference real tables/columns? RAG reduces hallucination but
doesn't eliminate it — this is the hard backstop.

We use sqlglot's expression tree (not regex) to pull out every table
and column reference, then check them against the actual live schema
metadata (fetched fresh, not cached, so this also catches drift if the
schema changed since the last index rebuild).
"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from app.db.connection import get_schema_metadata


@dataclass
class SemanticValidationResult:
    is_valid: bool
    unknown_tables: list[str] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    error_message: str | None = None


def _build_schema_lookup() -> tuple[set[str], dict[str, set[str]]]:
    """Returns (all_table_names, {table_name: {column_names}})."""
    metadata = get_schema_metadata()
    tables: set[str] = set()
    columns_by_table: dict[str, set[str]] = {}
    for row in metadata:
        tables.add(row["table_name"])
        columns_by_table.setdefault(row["table_name"], set()).add(row["column_name"])
    return tables, columns_by_table


def validate_semantics(sql: str) -> SemanticValidationResult:
    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except Exception as exc:  # noqa: BLE001
        return SemanticValidationResult(
            is_valid=False, error_message=f"Could not parse SQL for semantic check: {exc}"
        )

    known_tables, known_columns_by_table = _build_schema_lookup()

    referenced_tables = {t.name for t in parsed.find_all(exp.Table) if t.name}
    unknown_tables = sorted(t for t in referenced_tables if t not in known_tables)

    # Collect SELECT-list aliases (e.g. `SUM(x) AS total_spend`) so
    # references to them elsewhere in the query (ORDER BY, HAVING) aren't
    # incorrectly flagged as unknown columns -- they're query-level names,
    # not real table columns, and won't exist in the schema.
    select_aliases = {a.alias for a in parsed.find_all(exp.Alias) if a.alias}

    # Build the union of valid columns across all referenced (and known)
    # tables in this query — we don't try to resolve which specific
    # table a column belongs to when the query has multiple joined
    # tables (that requires full alias resolution); instead we accept
    # a column name if it exists in ANY of the tables actually used in
    # the query. This intentionally trades a little precision for
    # avoiding false positives on legitimate multi-table queries.
    valid_columns_in_query: set[str] = set()
    for t in referenced_tables:
        valid_columns_in_query |= known_columns_by_table.get(t, set())
    valid_columns_in_query |= select_aliases

    unknown_columns = []
    for col in parsed.find_all(exp.Column):
        col_name = col.name
        if not col_name or col_name == "*":
            continue
        if col_name not in valid_columns_in_query:
            unknown_columns.append(col_name)
    unknown_columns = sorted(set(unknown_columns))

    is_valid = not unknown_tables and not unknown_columns
    error_message = None
    if not is_valid:
        parts = []
        if unknown_tables:
            parts.append(f"Unknown table(s): {', '.join(unknown_tables)}")
        if unknown_columns:
            parts.append(f"Unknown column(s): {', '.join(unknown_columns)}")
        error_message = "; ".join(parts)

    return SemanticValidationResult(
        is_valid=is_valid,
        unknown_tables=unknown_tables,
        unknown_columns=unknown_columns,
        error_message=error_message,
    )