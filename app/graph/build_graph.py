"""
Wires the 5 agent nodes into a LangGraph StateGraph.

Flow:
    schema -> planning -> sql_generation -> safety
        safety passes         -> execution -> explanation -> END
        safety fails, retry   -> increment_retry -> sql_generation (loop)
        safety fails, exhausted -> clarification -> END
        execution fails, retry   -> increment_retry -> sql_generation (loop)
        execution fails, exhausted -> clarification -> END

The retry loop reuses the SAME sql_generation node on the way back
around, with the prior error now present in error_history so the next
attempt's prompt includes it (see nodes.sql_generation_node).
"""
from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    clarification_node,
    execution_node,
    explanation_node,
    increment_retry_node,
    planning_node,
    route_after_execution,
    route_after_safety,
    safety_node,
    schema_node,
    sql_generation_node,
)
from app.graph.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("schema", schema_node)
    graph.add_node("planning", planning_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("safety", safety_node)
    graph.add_node("increment_retry", increment_retry_node)
    graph.add_node("execution", execution_node)
    graph.add_node("explanation", explanation_node)
    graph.add_node("clarification", clarification_node)

    graph.set_entry_point("schema")

    graph.add_edge("schema", "planning")
    graph.add_edge("planning", "sql_generation")
    graph.add_edge("sql_generation", "safety")

    graph.add_conditional_edges(
        "safety",
        route_after_safety,
        {
            "execute": "execution",
            "retry": "increment_retry",
            "clarify": "clarification",
        },
    )

    graph.add_conditional_edges(
        "execution",
        route_after_execution,
        {
            "explain": "explanation",
            "retry": "increment_retry",
            "clarify": "clarification",
        },
    )

    # Retry loop always goes back to SQL generation, which will now see
    # the latest error in error_history and try to self-correct.
    graph.add_edge("increment_retry", "sql_generation")

    graph.add_edge("explanation", END)
    graph.add_edge("clarification", END)

    return graph.compile()


# Compiled once at import time; reused across requests (stateless graph
# definition — per-request data lives in the AgentState passed to .invoke()).
compiled_graph = build_graph()


def run_pipeline(question: str) -> AgentState:
    """
    Convenience entrypoint: runs the full pipeline for one question and
    returns the final state.
    """
    initial_state: AgentState = {
        "question": question,
        "retry_count": 0,
        "error_history": [],
        "cost_records": [],
        "needs_clarification": False,
    }
    final_state = compiled_graph.invoke(initial_state)
    return final_state
