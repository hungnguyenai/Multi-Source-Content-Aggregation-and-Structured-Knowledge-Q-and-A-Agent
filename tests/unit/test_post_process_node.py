# CMN-C1-128 — Unit Tests: PostProcessNode (output formatting + S-3 credential gate)

import json

import pytest

from framework.schemas.agent_status import AgentStatus
from src.nodes.post_process_node import PostProcessNode


def _state(**kw):
    base = {
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "answer": "Returns are accepted within 30 days.",
        "citations": [{"source_uri": "u1", "source_type": "web", "excerpt": "refund policy"}],
    }
    base.update(kw)
    return base


class TestPostProcessNode:
    def test_formats_answer_and_citations(self):
        result = PostProcessNode().execute(_state())
        assert result["status"] == AgentStatus.SUCCESS
        assert result["result"] == "Returns are accepted within 30 days."
        payload = json.loads(result["formatted_output"])
        assert payload["answer"] == "Returns are accepted within 30 days."
        assert payload["source_count"] == 1

    def test_s3_gate_passes_clean_output(self):
        node = PostProcessNode()
        clean = {"result": "a normal answer", "formatted_output": "{}"}
        assert node._extra_security_gate_output(clean) == clean

    def test_s3_gate_blocks_credential_leak(self):
        node = PostProcessNode()
        leaked = {"result": "here is the key sk-abcdefghijklmnopqrstuvwxyz123456"}
        with pytest.raises(RuntimeError):
            node._extra_security_gate_output(leaked)

    def test_s3_gate_blocks_jwt_leak(self):
        node = PostProcessNode()
        leaked = {"formatted_output": "token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload"}
        with pytest.raises(RuntimeError):
            node._extra_security_gate_output(leaked)
