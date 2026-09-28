"""AgentCore Platform v1.0"""

# Node contract: extend FunctionNode; execute(state) -> dict; return only changed keys;
# return AgentStatus enum constants. Formats output + S-3 domain output check.

from __future__ import annotations

import json
import re

from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from framework.schemas.agent_status import AgentStatus

from shared.utils.audit_logger import emit_trace_event

# S-3 credential / secret patterns to block in output (ported from legacy agent.py).
_CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("bearer_token", re.compile(r"Bearer [a-zA-Z0-9._\-]{20,}")),
    ("jwt", re.compile(r"eyJ[a-zA-Z0-9._\-]+\.[a-zA-Z0-9._\-]+")),
    ("aws_key", re.compile(r"AKIA[A-Z0-9]{16}")),
    ("generic_secret", re.compile(r"(?:key|secret|token|password)\s*=\s*[a-f0-9]{32,}", re.I)),
    (
        "db_url",
        re.compile(r"(?:postgresql|mongodb\+srv|mysql)://" r"[^\s:]+:[^\s@]+@"),
    ),
]


class PostProcessNode(FunctionNode):
    """Format the answer + citations into a structured response for CMN-C1-128."""

    required_trust_level = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        answer = state.get("answer") or ""
        citations = state.get("citations") or []

        payload = {
            "answer": answer,
            "citations": citations,
            "source_count": len(citations),
        }
        formatted_output = json.dumps(payload, ensure_ascii=False, indent=2)

        emit_trace_event(
            "output_formatted",
            {"answer_len": len(answer), "citation_count": len(citations)},
            state,
        )

        return {
            "formatted_output": formatted_output,
            "result": answer,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain hook: scan produced output strings for credential/secret patterns.

        Contract (FunctionNode 1.0.0): receive the execute() result dict, RETURN it;
        MAY raise to block output (RuntimeError → converted to status:error by __call__).
        """
        for key, value in result.items():
            if not isinstance(value, str):
                continue
            for name, pattern in _CREDENTIAL_PATTERNS:
                if pattern.search(value):
                    raise RuntimeError(
                        f"PostProcessNode S-3: credential pattern '{name}' detected "
                        f"in result['{key}'] — blocking output"
                    )
        return result
