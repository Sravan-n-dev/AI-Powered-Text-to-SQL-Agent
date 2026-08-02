"""
Layer 1 of the safety pipeline: does this even parse as valid SQL?
Uses sqlglot to parse against the Postgres dialect. This catches typos,
unbalanced parens, invalid keywords, etc. before we waste a DB round-trip.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot.errors import ParseError


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: str | None = None
    parsed_expression: object = None


def validate_syntax(sql: str) -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(is_valid=False, error_message="Empty SQL string.")

    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except ParseError as exc:
        return ValidationResult(is_valid=False, error_message=str(exc))

    if parsed is None:
        return ValidationResult(is_valid=False, error_message="SQL parsed to an empty statement.")

    return ValidationResult(is_valid=True, parsed_expression=parsed)
