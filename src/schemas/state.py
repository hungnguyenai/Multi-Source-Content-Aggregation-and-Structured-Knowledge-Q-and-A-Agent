"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict — never Pydantic BaseModel.
# LangGraph checkpoints use msgpack serialization; Pydantic objects cause
# silent corruption. Extend AgentState with agent-specific flat fields only.
# Do NOT add credentials, secrets, or Pydantic models.

from typing import Optional

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """State for CMN-C1-128 Multi-Source Content Aggregation & Knowledge Q&A Agent.

    Inherited fields from AgentState (do not re-declare):
      user_input, status, session_id, node_history, error_log,
      validated_input, trace_id, correlation_id, schema_version,
      response_metadata, trust_level, formatted_output, result

    The user's question arrives in AgentState.user_input.
    Agent-specific fields below are all flat, msgpack-safe primitives.
    """

    # Set by caller: list of {source_type, source_uri, metadata} descriptors.
    source_configs: Optional[list[dict[str, str | int | float | bool | None]]]

    # Set by pre_process: validated routing entries (mirrors source_configs + route_index).
    routing_plan: Optional[list[dict[str, str | int | float | bool | None]]]

    # Set by pre_process: extracted text chunks
    # {text, source_type, source_uri, chunk_index, metadata}.
    ingested_chunks: Optional[list[dict[str, str | int | float | bool | None]]]

    # Set by main: top-k chunks {text, source_type, source_uri, score}.
    retrieved_chunks: Optional[list[dict[str, str | int | float | bool | None]]]

    # Set by main: synthesised answer string.
    answer: Optional[str]

    # Set by main: [{source_uri, source_type, excerpt}].
    citations: Optional[list[dict[str, str]]]
