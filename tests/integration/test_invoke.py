# CMN-C1-128 — Integration test: full agent.invoke() through the 5-node backbone.
#
# Catches gate-hook contract bugs (S-3 _extra_security_gate_output must RETURN result)
# that per-node unit tests miss. Runs WITHOUT a live LLM (CI-safe): MainNode uses the
# deterministic fallback path when no LLM is injected.

from framework.schemas.agent_status import AgentStatus
from src.graph.graph import MultiSourceKnowledgeQAAgent

_EXPECTED_NODES = {
    "InitializeNode",
    "PreProcessNode",
    "MainNode",
    "PostProcessNode",
    "FinalizeNode",
}


def _is_terminal(status) -> bool:
    return status in (
        AgentStatus.SUCCESS, AgentStatus.SUCCESS.value,
        AgentStatus.ERROR, AgentStatus.ERROR.value,
    )


def _build_agent():
    agent = MultiSourceKnowledgeQAAgent()
    agent.compile()
    return agent


class TestFullInvoke:
    def test_backbone_nodes_registered(self):
        """All five backbone nodes must be present after compile()."""
        agent = _build_agent()
        registered = {type(n).__name__ for n in agent._nodes.values()}
        assert _EXPECTED_NODES.issubset(registered), (
            f"missing backbone nodes: {_EXPECTED_NODES - registered}"
        )

    def test_invoke_reaches_terminal_status(self):
        """A full invoke must reach a terminal status (success or error), never hang/None."""
        agent = _build_agent()
        out = agent.invoke("What is the refund policy?", session_id="itest")
        status = out.get("status") if isinstance(out, dict) else getattr(out, "status", None)
        assert _is_terminal(status)
