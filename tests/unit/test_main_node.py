# CMN-C1-128 — Unit Tests: MainNode (retrieval + LLM synthesis, LLM=None fallback)

from framework.schemas.agent_status import AgentStatus
from src.nodes.main_node import MainNode


def _chunk(text, uri, stype="web"):
    return {"text": text, "source_type": stype, "source_uri": uri, "chunk_index": 0, "metadata": {}}


def _state(**kw):
    base = {
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "node_history": [],
        "error_log": [],
        "validated_input": "what is the refund policy",
        "ingested_chunks": [],
    }
    base.update(kw)
    return base


class TestMainNode:
    def test_empty_ingested_chunks_returns_error(self):
        result = MainNode(llm=None).execute(_state(ingested_chunks=[]))
        assert result["status"] == AgentStatus.ERROR

    def test_fallback_synthesis_without_llm(self):
        chunks = [_chunk("The refund policy allows returns within 30 days", "u1")]
        result = MainNode(llm=None).execute(_state(ingested_chunks=chunks))
        assert result["status"] == AgentStatus.SUCCESS
        assert result["answer"]  # non-empty fallback answer
        assert result["result"] == result["answer"]
        assert len(result["citations"]) == 1
        assert result["citations"][0]["source_uri"] == "u1"

    def test_retrieval_ranks_by_keyword_overlap(self):
        chunks = [
            _chunk("totally unrelated content about weather", "low"),
            _chunk("the refund policy and refund window details", "high"),
        ]
        result = MainNode(llm=None).execute(
            _state(validated_input="refund policy", ingested_chunks=chunks)
        )
        assert result["status"] == AgentStatus.SUCCESS
        # Highest keyword-overlap chunk ranked first
        assert result["retrieved_chunks"][0]["source_uri"] == "high"
        assert result["retrieved_chunks"][0]["score"] >= result["retrieved_chunks"][1]["score"]

    def test_top_k_config_limits_retrieved(self):
        chunks = [_chunk(f"refund policy detail {i} extra words here", f"u{i}") for i in range(8)]
        node = MainNode(llm=None, config={"top_k": 3})
        result = node.execute(_state(ingested_chunks=chunks))
        assert len(result["retrieved_chunks"]) == 3

    def test_citations_deduplicated_by_uri(self):
        chunks = [_chunk("refund policy a", "same"), _chunk("refund policy b", "same")]
        result = MainNode(llm=None).execute(_state(ingested_chunks=chunks))
        assert len(result["citations"]) == 1
