"""
Tracks token usage and latency per agent call. Actual cost is $0 since
everything runs on local Ollama, but we compute a HYPOTHETICAL cost
against known cloud pricing so we can honestly say "here's what this
would have cost on a paid API" — this is what makes a resume line like
"$0.12 -> $0.03/query" defensible rather than made up.

Pricing below is illustrative (per 1M tokens) and should be refreshed
against current provider pricing pages before quoting it anywhere
external — providers change prices often.
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# USD per 1,000,000 tokens. Update these periodically from provider docs.
HYPOTHETICAL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-haiku": {"input": 0.80, "output": 4.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

LOG_PATH = Path("cost_tracker.jsonl")


@dataclass
class UsageRecord:
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    timestamp: float = field(default_factory=time.time)

    def hypothetical_cost(self, provider: str = "gpt-4o-mini") -> float:
        rates = HYPOTHETICAL_PRICING.get(provider)
        if not rates:
            return 0.0
        cost = (
            (self.prompt_tokens / 1_000_000) * rates["input"]
            + (self.completion_tokens / 1_000_000) * rates["output"]
        )
        return round(cost, 6)


class CostTracker:
    """
    In-memory tracker for a single request's lifecycle (all 5 agent
    calls for one question), plus append-only JSONL logging to disk
    for later aggregate analysis (e.g. "average cost per query type").
    """

    def __init__(self):
        self.records: list[UsageRecord] = []

    def record(
        self,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
    ) -> UsageRecord:
        rec = UsageRecord(
            agent=agent,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_seconds=latency_seconds,
        )
        self.records.append(rec)
        self._append_to_log(rec)
        return rec

    def _append_to_log(self, rec: UsageRecord) -> None:
        try:
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps(asdict(rec)) + "\n")
        except OSError as exc:  # noqa: BLE001
            logger.warning("Could not write cost log: %s", exc)

    def summary(self, provider: str = "gpt-4o-mini") -> dict:
        total_prompt = sum(r.prompt_tokens for r in self.records)
        total_completion = sum(r.completion_tokens for r in self.records)
        total_latency = sum(r.latency_seconds for r in self.records)
        total_hypothetical_cost = sum(r.hypothetical_cost(provider) for r in self.records)
        return {
            "num_calls": len(self.records),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_latency_seconds": round(total_latency, 3),
            "actual_cost_usd": 0.0,  # always $0 — local inference
            "hypothetical_cloud_cost_usd": total_hypothetical_cost,
            "hypothetical_provider": provider,
            "per_agent": [asdict(r) for r in self.records],
        }
