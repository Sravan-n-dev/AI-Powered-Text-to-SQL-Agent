"""
NOTE: In this implementation, schema descriptions are generated with
simple Python templates (see app/rag/schema_indexer.py), not an LLM
call — it's faster, free, deterministic, and perfectly adequate for
embedding/retrieval purposes.

This file is kept as an extension point: if you later want richer,
LLM-generated table descriptions (e.g. inferring business meaning from
naming conventions), you'd add that prompt here and call it from
schema_indexer.py's _describe_column/_describe_table functions.
"""

SCHEMA_DESCRIPTION_SYSTEM_PROMPT = """You are documenting a database schema.
Given a table name and its columns, write ONE concise sentence describing
what this table likely represents in the business domain. Do not invent
specifics not implied by the names."""


def build_schema_description_prompt(table_name: str, column_names: list[str]) -> str:
    return f"Table: {table_name}\nColumns: {', '.join(column_names)}\n\nDescribe this table in one sentence."
