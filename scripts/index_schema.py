"""
Initializes the pgvector store (creates tables/extension if missing)
and builds the schema embedding index from whatever is currently in
the target database's `public` schema.

Run this:
  - Once, right after seeding the sample DB.
  - Again any time the target schema changes.

Usage:
    python scripts/index_schema.py
"""
from app.db.vector_store import init_vector_store
from app.rag.schema_indexer import build_and_store_schema_index


def main():
    print("Initializing vector store (pgvector extension + tables)...")
    init_vector_store()

    print("Building schema index (this calls Ollama's embedding model "
          "once per column — may take a minute)...")
    count = build_and_store_schema_index()

    print(f"✅ Done. Indexed {count} schema embeddings.")
    print("   You can now call POST /ask on the running API.")


if __name__ == "__main__":
    main()
