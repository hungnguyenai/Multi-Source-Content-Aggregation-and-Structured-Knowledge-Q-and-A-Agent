"""AgentCore Platform v1.0"""

# Node contract: extend FunctionNode; execute(state) -> dict; return only changed keys;
# return AgentStatus enum constants. Core capability for CMN-C1-128 (Cat 1).

from __future__ import annotations

import re
from typing import Any

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from framework.schemas.agent_status import AgentStatus

from shared.utils.audit_logger import emit_trace_event
from src.services.llm_factory import resolve_llm

_DEFAULT_TOP_K = 5
_MIN_CHUNK_LEN = 10
_MAX_CONTEXT_CHUNKS = 10

_SYNTHESIS_PROMPT = """You are a helpful knowledge assistant. Answer the user's question \
using ONLY the provided context. Cite the source for each key claim.

Context:
{context}

Question: {query}
"""


class MainNode(FunctionNode):
    """Retrieve relevant chunks + synthesise an answer for CMN-C1-128.

    Ports the legacy EmbeddingAndRetrievalNode (keyword-overlap top-k retrieval —
    production swaps for real embeddings/vector DB) and AnswerSynthesisNode
    (LLM synthesis with citations). LLM injected via graph config; None in CI.
    """

    required_trust_level = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None, config: dict[str, Any] | None = None):
        super().__init__()
        self._llm = llm
        cfg = config or {}
        self._top_k = int(cfg.get("top_k", _DEFAULT_TOP_K))
        self._min_chunk_len = int(cfg.get("min_chunk_len", _MIN_CHUNK_LEN))
        self._max_context_chunks = int(cfg.get("max_context_chunks", _MAX_CONTEXT_CHUNKS))

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        llm, _llm_provider = resolve_llm(self._llm, state)
        query = state.get("validated_input", state.get("user_input", "")) or ""
        ingested_chunks = state.get("ingested_chunks") or []

        if not ingested_chunks:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": state.get("error_log", [])
                + ["MainNode: ingested_chunks is empty — pre_process must run first"],
            }

        # ── Retrieve: normalised keyword overlap, top-k ───────────────────────
        scored: list[dict[str, Any]] = []
        for chunk in ingested_chunks:
            text = chunk.get("text", "")
            if len(text) < self._min_chunk_len:
                continue
            scored.append(
                {
                    "text": text,
                    "source_type": chunk.get("source_type", ""),
                    "source_uri": chunk.get("source_uri", ""),
                    "score": self._score(query, text),
                }
            )
        scored.sort(key=lambda c: c["score"], reverse=True)
        retrieved = scored[: self._top_k]

        # ── Synthesise: LLM (None-safe fallback in CI) ────────────────────────
        context_chunks = retrieved[: self._max_context_chunks]
        context_text = self._build_context(context_chunks)
        prompt = _SYNTHESIS_PROMPT.format(context=context_text, query=query)

        if llm is None:
            answer = self._compose_extractive_answer(query, context_chunks)
        else:
            # The key is bound into the client at construction; kept for the call signature.
            try:
                answer = llm.complete(prompt, api_key=None, temperature=0.1, max_tokens=1024).strip()
            except Exception as exc:  # noqa: BLE001
                emit_trace_event("synthesis_failed", {"reason": str(exc)}, state)
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": state.get("error_log", []) + [f"MainNode: LLM synthesis failed — {exc}"],
                }

        citations = self._build_citations(context_chunks)
        emit_trace_event(
            "answer_synthesised",
            {"retrieved": len(retrieved), "cited": len(citations), "answer_len": len(answer)},
            state,
        )

        return {
            "retrieved_chunks": retrieved,
            "answer": answer,
            "citations": citations,
            "result": answer,
            "status": AgentStatus.SUCCESS.value,
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _compose_extractive_answer(query: str, chunks: list[dict[str, Any]]) -> str:
        """Deterministic extractive synthesis used when no LLM client is injected.

        Builds a real, grounded answer out of the retrieved passages instead of a
        placeholder marker: the highest-scoring sentences from each source, attributed
        inline. Lower quality than LLM synthesis, but genuine content the caller can
        use — never a stub string.
        """
        if not chunks:
            return (
                f"No source passage in the ingested corpus matched the query "
                f'"{query[:120]}". Ingest additional sources, or refine the query.'
            )

        q_terms = {t for t in query.lower().split() if len(t) > 2}
        parts: list[str] = [
            f'Synthesised from {len(chunks)} matching source passage(s) for: "{query[:120]}"',
            "",
        ]
        for i, chunk in enumerate(chunks, start=1):
            text = (chunk.get("text") or "").strip()
            if not text:
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?。])\s+", text) if s.strip()]
            ranked = sorted(
                sentences,
                key=lambda s: len(q_terms & set(s.lower().split())),
                reverse=True,
            )
            excerpt = " ".join(ranked[:2]) if ranked else text[:300]
            src = chunk.get("source_type") or "source"
            uri = chunk.get("source_uri") or ""
            parts.append(f"[{i}] ({src}{' — ' + uri if uri else ''}) {excerpt}")
        return "\n".join(parts).strip()

    @staticmethod
    def _score(query: str, chunk_text: str) -> float:
        if not query:
            return 0.0
        q = set(query.lower().split())
        c = set(chunk_text.lower().split())
        return round(len(q & c) / max(len(q), 1), 4)

    @staticmethod
    def _build_context(chunks: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            lines.append(
                f"[Source {i}] (source_type: {chunk.get('source_type', 'unknown')}, uri: {chunk.get('source_uri', '')})"
            )
            lines.append(chunk.get("text", ""))
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _build_citations(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
        seen: set[str] = set()
        citations: list[dict[str, str]] = []
        for chunk in chunks:
            uri = chunk.get("source_uri", "")
            if uri in seen:
                continue
            seen.add(uri)
            text = chunk.get("text", "")
            excerpt = text[:120].rstrip() + ("…" if len(text) > 120 else "")
            citations.append(
                {
                    "source_uri": uri,
                    "source_type": chunk.get("source_type", ""),
                    "excerpt": excerpt,
                }
            )
        return citations
