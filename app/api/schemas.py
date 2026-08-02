from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, examples=["What was total revenue by category last quarter?"])


class AskResponse(BaseModel):
    status: str  # "success" | "clarification_needed" | "failed"
    question: str
    sql: str | None = None
    row_count: int | None = None
    rows_preview: list[dict] | None = None
    truncated: bool | None = None
    summary: str | None = None
    follow_up_questions: list[str] | None = None
    retry_count: int = 0
    routing_model: str | None = None
    routing_reason: str | None = None
    cost_summary: dict | None = None
    error: str | None = None


class SchemaRefreshResponse(BaseModel):
    status: str
    embeddings_created: int


class HealthResponse(BaseModel):
    api: bool = True
    database: bool
    ollama: bool
