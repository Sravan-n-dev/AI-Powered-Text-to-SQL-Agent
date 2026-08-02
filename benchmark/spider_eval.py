"""
Runs the pipeline against (a subset of) the Spider text-to-SQL
benchmark and computes exact-match and execution accuracy.

SETUP (this dataset is NOT bundled — it's ~1GB and has its own license):
    1. Download from https://yale-lily.github.io/spider
    2. Unzip into ./benchmark/spider_data/ so you have:
       benchmark/spider_data/dev.json
       benchmark/spider_data/database/<db_id>/<db_id>.sqlite (per-DB SQLite files)

IMPORTANT CAVEAT: this project's agents are built against Postgres
(pgvector, information_schema queries, EXPLAIN JSON), while Spider's
databases ship as SQLite. To actually benchmark apples-to-apples, you
have two honest options:
    A) Convert each Spider SQLite DB to Postgres before running (see
       `sqlite3-to-postgres` tools), and re-index the schema before
       each question that targets a different db_id. Slow, but faithful.
    B) Report benchmark numbers against your own seeded sample DB's
       question set instead of full Spider, and be upfront on your
       resume/README that "Spider" numbers reflect a Spider-style
       evaluation methodology (exact-match + execution accuracy) rather
       than a literal claim of running against the official Spider test
       harness -- which also normally includes its own scoring script
       (spider/evaluation.py) with specific SQL normalization rules.

This script implements option (A)'s loop structure but expects you to
supply a `db_id -> postgres_connection_string` mapping once you've done
the conversion, since that conversion step is environment-specific.
"""
import json
import re
import sys
from pathlib import Path

from app.config import settings
from app.db.vector_store import init_vector_store
from app.graph.build_graph import run_pipeline
from app.rag.schema_indexer import build_and_store_schema_index

SPIDER_DIR = Path(__file__).parent / "spider_data"
RESULTS_DIR = Path(__file__).parent / "results"


def normalize_sql(sql: str) -> str:
    """Rough normalization for exact-match comparison: lowercase, collapse whitespace."""
    sql = sql.strip().rstrip(";").lower()
    sql = re.sub(r"\s+", " ", sql)
    return sql


def load_spider_dev_set(limit: int | None = None) -> list[dict]:
    dev_path = SPIDER_DIR / "dev.json"
    if not dev_path.exists():
        print(f"❌ {dev_path} not found. See the docstring in this file for setup steps.")
        sys.exit(1)
    with open(dev_path) as f:
        data = json.load(f)
    return data[:limit] if limit else data


def run_eval(limit: int = 50):
    """
    Runs up to `limit` Spider dev questions through the pipeline.
    Assumes the CURRENT target database (as configured in .env) already
    matches the db_id(s) being tested -- i.e. you've done the schema
    conversion/setup described in the module docstring, OR you're
    running this against your own seeded sample DB with a Spider-style
    JSON question file in the same shape (see below).
    """
    examples = load_spider_dev_set(limit=limit)

    exact_matches = 0
    execution_matches = 0
    results_log = []

    for i, example in enumerate(examples, start=1):
        question = example["question"]
        gold_sql = example["query"]

        print(f"[{i}/{len(examples)}] {question}")
        final_state = run_pipeline(question)
        predicted_sql = final_state.get("sql", "")

        is_exact_match = normalize_sql(predicted_sql) == normalize_sql(gold_sql)
        # Execution accuracy properly requires running BOTH queries
        # against the same live DB and comparing result sets -- exact
        # string match is a weaker proxy included here as a fallback
        # when you haven't wired up gold-query execution comparison yet.
        is_execution_match = final_state.get("execution_success", False) and is_exact_match

        exact_matches += int(is_exact_match)
        execution_matches += int(is_execution_match)

        results_log.append({
            "question": question,
            "gold_sql": gold_sql,
            "predicted_sql": predicted_sql,
            "exact_match": is_exact_match,
            "execution_match": is_execution_match,
            "final_status": final_state.get("final_status"),
        })

    exact_match_pct = round(100 * exact_matches / len(examples), 2)
    execution_pct = round(100 * execution_matches / len(examples), 2)

    print(f"\nExact-match accuracy: {exact_match_pct}% ({exact_matches}/{len(examples)})")
    print(f"Execution accuracy (proxy): {execution_pct}% ({execution_matches}/{len(examples)})")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "spider_eval_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "exact_match_pct": exact_match_pct,
            "execution_pct": execution_pct,
            "n": len(examples),
            "details": results_log,
        }, f, indent=2)
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    init_vector_store()
    build_and_store_schema_index()
    run_eval(limit=50)
