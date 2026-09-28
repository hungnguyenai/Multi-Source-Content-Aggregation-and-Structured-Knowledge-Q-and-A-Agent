# CMN-C1-128 — Unit Tests: PreProcessNode (source validation + content ingestion)

from framework.schemas.agent_status import AgentStatus
from src.nodes.pre_process_node import PreProcessNode


def _state(**kw):
    base = {
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "source_configs": [],
    }
    base.update(kw)
    return base


_SRC = [{"source_type": "web", "source_uri": "https://example.com/a", "metadata": {}}]


class TestPreProcessNode:
    def test_empty_user_input_returns_error(self):
        result = PreProcessNode().execute(_state(user_input="", source_configs=_SRC))
        assert result["status"] == AgentStatus.ERROR

    def test_empty_source_configs_returns_error(self):
        result = PreProcessNode().execute(_state(user_input="What is X?", source_configs=[]))
        assert result["status"] == AgentStatus.ERROR
        assert any("source_configs" in e for e in result["error_log"])

    def test_invalid_source_type_returns_error(self):
        bad = [{"source_type": "spreadsheet", "source_uri": "f.xlsx", "metadata": {}}]
        result = PreProcessNode().execute(_state(user_input="Q?", source_configs=bad))
        assert result["status"] == AgentStatus.ERROR
        assert any("invalid source_type" in e for e in result["error_log"])

    def test_valid_sources_produce_routing_plan_and_chunks(self):
        result = PreProcessNode().execute(_state(user_input="What is X?", source_configs=_SRC))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["validated_input"] == "What is X?"
        assert len(result["routing_plan"]) == 1
        assert result["routing_plan"][0]["source_type"] == "web"
        assert len(result["ingested_chunks"]) == 1
        assert result["ingested_chunks"][0]["source_uri"] == "https://example.com/a"

    def test_multiple_sources_all_ingested(self):
        srcs = [
            {"source_type": "web", "source_uri": "u1", "metadata": {}},
            {"source_type": "pdf", "source_uri": "u2", "metadata": {}},
            {"source_type": "video", "source_uri": "u3", "metadata": {}},
        ]
        result = PreProcessNode().execute(_state(user_input="Q?", source_configs=srcs))
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["ingested_chunks"]) == 3

    def test_allowed_types_config_override_restricts(self):
        node = PreProcessNode({"allowed_source_types": ["web"]})
        result = node.execute(_state(
            user_input="Q?",
            source_configs=[{"source_type": "pdf", "source_uri": "u", "metadata": {}}],
        ))
        assert result["status"] == AgentStatus.ERROR
