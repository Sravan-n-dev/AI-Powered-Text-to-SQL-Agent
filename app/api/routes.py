import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import AskRequest, AskResponse, HealthResponse, SchemaRefreshResponse
from app.db.connection import get_raw_connection
from app.graph.build_graph import run_pipeline
from app.llm.cost_tracker import HYPOTHETICAL_PRICING
from app.llm.ollama_client import health_check as ollama_health_check
from app.rag.schema_indexer import build_and_store_schema_index

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    db_ok = True
    try:
        conn = get_raw_connection()
        conn.close()
    except Exception:  # noqa: BLE001
        db_ok = False

    return HealthResponse(database=db_ok, ollama=ollama_health_check())


@router.post("/schema/refresh", response_model=SchemaRefreshResponse)
def schema_refresh():
    """
    Re-indexes the target database's schema into the vector store.
    Call this once at setup, and again any time the schema changes.
    """
    try:
        count = build_and_store_schema_index()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Schema refresh failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SchemaRefreshResponse(status="ok", embeddings_created=count)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    """
    Runs the full 5-agent pipeline for a natural language question.
    """
    try:
        final_state = run_pipeline(request.question)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline crashed unexpectedly")
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {exc}") from exc

    status = final_state.get("final_status", "failed")

    # Build a simple cost summary from the accumulated per-agent records.
    cost_records = final_state.get("cost_records", [])
    total_prompt = sum(r.get("prompt_tokens", 0) for r in cost_records)
    total_completion = sum(r.get("completion_tokens", 0) for r in cost_records)
    provider = "gpt-4o-mini"
    rates = HYPOTHETICAL_PRICING[provider]
    hypothetical_cost = round(
        (total_prompt / 1_000_000) * rates["input"] + (total_completion / 1_000_000) * rates["output"],
        6,
    )
    cost_summary = {
        "num_llm_calls": len(cost_records),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "actual_cost_usd": 0.0,
        "hypothetical_cost_usd": hypothetical_cost,
        "hypothetical_provider": provider,
        "per_agent": cost_records,
    }

    return AskResponse(
        status=status,
        question=request.question,
        sql=final_state.get("sql"),
        row_count=final_state.get("row_count"),
        rows_preview=(final_state.get("result_rows") or [])[:20],
        truncated=final_state.get("truncated"),
        summary=final_state.get("summary"),
        follow_up_questions=final_state.get("follow_up_questions"),
        retry_count=final_state.get("retry_count", 0),
        routing_model=final_state.get("routing_model"),
        routing_reason=final_state.get("routing_reason"),
        cost_summary=cost_summary,
        error=final_state.get("execution_error") or final_state.get("safety_error"),
    )
