"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus enum constants — never plain strings

from __future__ import annotations

import json
from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from framework.schemas.agent_status import AgentStatus

from shared.utils.audit_logger import emit_trace_event

# Allowed source types (Cat 1, config-driven via constructor; constant is the default).
_ALLOWED_SOURCE_TYPES = ["video", "pdf", "web", "audio", "doc"]

# source_type → stub extractor label. Production swaps each for a real extractor
# (Whisper/MinerU/trafilatura/python-docx) injected via config — no code change here.
_STUB_EXTRACTORS = {
    "video": "YouTube Data API or Whisper ASR",
    "pdf": "MinerU layout-aware extraction (DRAFT-730)",
    "web": "HTTP fetch + HTML extraction",
    "audio": "Whisper or cloud ASR",
    "doc": "python-docx/openpyxl/python-pptx",
}


class PreProcessNode(FunctionNode):
    """Validate sources + ingest content for CMN-C1-128.

    Ports the legacy SourceRouterNode (source-type validation → routing_plan) and
    ContentIngestionNode (per-type stub extraction → ingested_chunks) into the
    pre_process slot. Sets validated_input from the user's question.
    """

    required_trust_level = TrustLevel.ANONYMOUS

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__()
        cfg = config or {}
        self._allowed = cfg.get("allowed_source_types", _ALLOWED_SOURCE_TYPES)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "") or ""
        query, source_configs = raw, state.get("source_configs") or []
        try:
            envelope = json.loads(raw)
            if isinstance(envelope, dict) and "query" in envelope:
                query = envelope.get("query", "") or ""
                source_configs = envelope.get("source_configs") or source_configs
        except (json.JSONDecodeError, TypeError):
            pass

        if not query.strip():
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": state.get("error_log", []) + ["PreProcessNode: empty user_input"],
            }
        if not source_configs:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": state.get("error_log", [])
                + ["PreProcessNode: source_configs is empty — at least one source required"],
            }

        # ── Route: validate each source_type ──────────────────────────────────
        routing_plan: list[dict[str, Any]] = []
        for idx, sc in enumerate(source_configs):
            source_type = sc.get("source_type", "")
            if source_type not in self._allowed:
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": state.get("error_log", [])
                    + [f"PreProcessNode: invalid source_type '{source_type}' at index {idx}; allowed={self._allowed}"],
                }
            routing_plan.append(
                {
                    "source_type": source_type,
                    "source_uri": sc.get("source_uri", ""),
                    "metadata": sc.get("metadata", {}),
                    "route_index": idx,
                }
            )

        # ── Ingest: per-type stub extraction ──────────────────────────────────
        ingested_chunks: list[dict[str, Any]] = []
        for route in routing_plan:
            stype = route["source_type"]
            uri = route["source_uri"]
            ingested_chunks.append(
                {
                    "text": (
                        f"[{stype.upper()}_STUB] Extracted content from: {uri}. "
                        f"Production implementation uses {_STUB_EXTRACTORS.get(stype, 'a configured extractor')}."
                    ),
                    "source_type": stype,
                    "source_uri": uri,
                    "chunk_index": 0,
                    "metadata": route.get("metadata", {}),
                }
            )

        emit_trace_event(
            "sources_ingested",
            {"source_count": len(routing_plan), "chunk_count": len(ingested_chunks)},
            state,
        )

        return {
            "validated_input": query.strip(),
            "routing_plan": routing_plan,
            "ingested_chunks": ingested_chunks,
            "status": AgentStatus.SUCCESS.value,
        }
