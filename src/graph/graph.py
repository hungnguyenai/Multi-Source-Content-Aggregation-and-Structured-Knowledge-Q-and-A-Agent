"""AgentCore Platform v1.0"""

# CMN-C1-128 — Multi-Source Content Aggregation & Structured Knowledge Q&A Agent
#
# Cat 1 — single generic capability, standard 3-slot fixed pipeline.
#   Parent  : AgentBaseGraph (outer graph).
#   Pipeline: START → initialize → pre_process → main → {route} → post_process → finalize → END
#   Slots   : pre_process — validate sources + ingest content
#             main        — keyword-overlap retrieval + LLM answer synthesis
#             post_process — format answer + citations + S-3 output check
#
# framework.* imports are unchanged; agent-local imports use the src. prefix.
# add_edges() / route() are NOT overridden — backbone wiring belongs to the framework.

from framework.graph.agent_base_graph import AgentBaseGraph
from src.nodes.pre_process_node import PreProcessNode
from src.nodes.main_node import MainNode
from src.nodes.post_process_node import PostProcessNode
from src.schemas.state import State


class MultiSourceKnowledgeQAAgent(AgentBaseGraph):
    """Cat 1 outer graph for CMN-C1-128.

    Class name matches config/agent.yaml `class:`. All domain configuration
    (allowed_source_types, top_k, …) is injected via config — no domain
    assumptions are hard-coded (Cat 1 purity).
    """

    @property
    def name(self) -> str:
        return "cmn_c1_128"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        cfg = getattr(self, "config", None) or {}
        # LLM injection: in CI / unit tests there is no LLM, so llm is None and
        # MainNode uses its deterministic fallback path. In production the platform
        # injects the real client at runtime (server.py compile path provisions
        # secrets; the LLM client is supplied via graph config) — it is NOT declared
        # in config/agent.yaml. `cfg.get("llm")` therefore returns None here by design.
        llm = cfg.get("llm")

        self._nodes["pre_process"] = PreProcessNode(cfg)
        self._nodes["main"] = MainNode(llm, cfg)
        self._nodes["post_process"] = PostProcessNode()
