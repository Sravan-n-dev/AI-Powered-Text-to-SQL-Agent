from app.config import settings
from app.llm.router import route, score_plan_complexity


def test_simple_single_table_plan_scores_low():
    plan = {"tables": ["customers"], "filters": [{"column": "country", "operator": "=", "value": "USA"}]}
    assert score_plan_complexity(plan) <= 2


def test_simple_plan_routes_to_small_model():
    plan = {"tables": ["customers"], "filters": []}
    decision = route(plan)
    assert decision.model == settings.ollama_sql_model


def test_multi_join_with_aggregation_scores_high():
    plan = {
        "tables": ["customers", "orders", "order_items", "products"],
        "aggregations": [{"function": "SUM", "column": "order_items.quantity"}],
        "has_subquery": True,
    }
    assert score_plan_complexity(plan) >= 3


def test_complex_plan_routes_to_larger_model():
    plan = {
        "tables": ["customers", "orders", "order_items", "products"],
        "aggregations": [{"function": "SUM", "column": "order_items.quantity"}],
        "has_subquery": True,
    }
    decision = route(plan)
    assert decision.model == settings.ollama_complex_model


def test_many_filters_bump_score():
    plan = {
        "tables": ["orders"],
        "filters": [
            {"column": "status", "operator": "=", "value": "completed"},
            {"column": "order_date", "operator": ">=", "value": "2026-01-01"},
            {"column": "order_date", "operator": "<=", "value": "2026-03-31"},
        ],
    }
    assert score_plan_complexity(plan) >= 1
