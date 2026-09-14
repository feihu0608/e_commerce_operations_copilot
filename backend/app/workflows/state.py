"""Serializable LangGraph state and non-serialized runtime dependencies."""

from dataclasses import dataclass
import operator
from typing import Annotated, Any, Callable, Literal, Protocol, TypedDict


class ModelGateway(Protocol):
    async def chat(self, system: str, user: str, model: str | None = None) -> str: ...


class GenerationState(TypedDict, total=False):
    task_id: int
    attempt_id: int
    product_id: int
    workflow_kind: Literal["diagnosis", "creative", "strategy", "review"]
    provider_mode: Literal["mock", "live"]
    input_snapshot: dict[str, Any]
    prompt_version: str
    schema_version: str
    evidence_refs: list[str]
    system_prompt: str
    user_prompt: str
    raw_output: str
    candidate: dict[str, Any] | None
    validation_errors: list[str]
    repair_count: int
    max_repairs: int
    output_revision_id: str | None
    workflow_status: Literal["running", "succeeded", "failed"]
    node_trace: Annotated[list[str], operator.add]


@dataclass(frozen=True)
class WorkflowContext:
    gateway: ModelGateway
    persist: Callable[[GenerationState], str]
