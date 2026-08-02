"""
Shared pytest fixtures. Tests in this suite are split into two kinds:

1. PURE UNIT TESTS (no DB, no Ollama needed) — test_syntax_validator.py,
   test_permission_enforcer.py, test_router.py. These run anywhere,
   including CI, with zero setup.

2. INTEGRATION TESTS (need Postgres running) — test_semantic_validator.py,
   test_cost_estimator.py, test_graph_flow.py, failure_modes/. These
   assume `docker-compose up -d postgres` has been run and the sample
   DB has been seeded. They're marked with the `integration` marker so
   you can skip them when Postgres isn't available:
       pytest -m "not integration"
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires a running Postgres instance")
