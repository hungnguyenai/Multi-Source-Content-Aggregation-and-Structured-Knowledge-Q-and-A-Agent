# 02_design.md — CMN-C1-128 Design Specification

## Overview

**Template:** CMN-C1-128 — Multi-Source Content Aggregation & Structured Knowledge Q&A Agent  
**Category:** Cat 1 (config-driven, no hardcoded domain logic)  
**L1 Base:** AgentBaseGraph (L1 direct)  
**Pattern:** Multi-source ingestion pipeline → EmbeddingRetrieval → AnswerSynthesis

---

## Agent Workflow (ASCII Diagram)

New-gen scaffold: `AgentBaseGraph` 3-slot fixed backbone. `initialize` + `finalize`
are injected by `super().register_nodes()`; `add_edges()` / `route()` are owned by
the framework (not overridden). The legacy 4-node pipeline is folded into the 3 slots.

```
  Input: user_input (question) + source_configs
        │
        ▼
START → initialize → pre_process ── {route} ── main ──→ post_process → finalize → END
                         │                       │
   PreProcessNode        │   MainNode            │   PostProcessNode
   • validate sources    │   • keyword-overlap   │   • assemble answer + citations
     (→ routing_plan)    │     retrieve top_k    │     → formatted_output (JSON)
   • ingest content      │     (→ retrieved_     │   • S-3 _extra_security_gate_output
     (→ ingested_chunks) │       chunks)         │     (credential scan)
   • set validated_input │   • LLM synthesis     │
                         │     (→ answer,        │
                         │       citations,      │
                         │       result)         │
        ▲                │                       │
        └──── RETRY ──────┘  (status routing: SUCCESS→post_process, RETRY→pre_process,
                              ERROR→finalize; max_retry=3)

  Output: result (answer) + formatted_output {answer, citations, source_count}
```

Legacy → new-gen node mapping:
`SourceRouterNode` + `ContentIngestionNode` → **PreProcessNode** ·
`EmbeddingAndRetrievalNode` + `AnswerSynthesisNode` → **MainNode** ·
output formatting + S-3 credential gate → **PostProcessNode**.

---

## State Schema

**File:** `src/schemas/state.py`  
**Type:** `class State(AgentState)` — flat TypedDict extending `AgentState` (no Pydantic,
no dataclass, no credentials; all msgpack-safe primitives).

Inherited from `AgentState` (not re-declared): `user_input`, `validated_input`,
`status` (AgentStatus enum), `result`, `formatted_output`, `error_log`, `session_id`,
`trace_id`, `correlation_id`, `node_history`, `schema_version`, `response_metadata`,
`trust_level`.

| Field | Type | Direction | Description |
|-------|------|-----------|-------------|
| `user_input` | `str` | Input (inherited) | User's natural language question (was legacy `query`) |
| `validated_input` | `str` | Processing (inherited) | Question after pre_process validation |
| `source_configs` | `list[dict]` | Input | List of SourceConfig dicts (see below) |
| `routing_plan` | `list[dict]` | Processing | Validated routing plan from PreProcessNode |
| `ingested_chunks` | `list[dict]` | Processing | Extracted text chunks from all sources |
| `retrieved_chunks` | `list[dict]` | Processing | Top-k chunks from MainNode retrieval |
| `answer` | `str` | Output | Synthesized answer |
| `citations` | `list[dict]` | Output | Source citations for the answer |
| `result` | `str` | Output (inherited) | Plain-text answer for simple callers |
| `status` | `AgentStatus` | Control (inherited) | SUCCESS / RETRY / ERROR (replaces legacy `error`/`is_safe`) |
| `error_log` | `list[str]` | Control (inherited) | Accumulated error messages (replaces legacy `error`) |

### SourceConfig Dict Schema

```python
{
    "source_type": str,          # "video" | "pdf" | "web" | "audio" | "doc"
    "source_uri":  str,          # URL or file path
    "metadata":    dict[str, str]  # optional key-value tags (e.g., title, language)
}
```

### ingested_chunks Item Schema

```python
{
    "text":         str,   # extracted text content
    "source_type":  str,   # matches source_config.source_type
    "source_uri":   str,   # original source URI
    "chunk_index":  int,   # 0-based index within this source
    "metadata":     dict   # inherited from source_config.metadata
}
```

### retrieved_chunks Item Schema

```python
{
    "text":        str,   # chunk text
    "source_type": str,
    "source_uri":  str,
    "score":       float  # retrieval relevance score (0.0–1.0)
}
```

---

## Source Type Config Schema

Source types accepted by the router are defined via config, not hardcoded in logic paths.

**Default allowed set (constant):** `["video", "pdf", "web", "audio", "doc"]`

At runtime, `SourceRouterNode` reads `self._config.get("allowed_source_types", ALLOWED_SOURCE_TYPES_DEFAULT)`
so operators can restrict or extend the accepted types without code changes.

---

## Node Responsibility Table

| Slot / Node | Responsibility (folds legacy nodes) |
|------|---------------|
| `initialize` (framework) | Injected by `super().register_nodes()` — sets schema_version, session_id, trust level |
| `PreProcessNode` | Validate sources → `routing_plan`; ingest content (per-type stub extractors) → `ingested_chunks`; set `validated_input` *(folds legacy SourceRouterNode + ContentIngestionNode)* |
| `MainNode` | Keyword-overlap top-k retrieval → `retrieved_chunks`; LLM synthesis (`.complete()`, None-safe in CI) → `answer`, `citations`, `result` *(folds legacy EmbeddingAndRetrievalNode + AnswerSynthesisNode)* |
| `PostProcessNode` | Assemble `formatted_output` (JSON); S-3 `_extra_security_gate_output` credential scan |
| `finalize` (framework) | Injected by `super().register_nodes()` — builds response_metadata + timing |

---

## Cat 1 Purity Notes

This template adheres to **Cat 1 config-driven architecture**:

1. **No hardcoded domain logic** — source type routing is driven by config values,
   not by `if source_type == "finance_report":` style domain assumptions.
2. **Operator-configurable source set** — the allowed source types list lives in
   the default constant and is overridable via runtime config.
3. **No domain-specific extractors** — `ContentIngestionNode` dispatches by
   source_type string; the handler implementations are generic stubs that can be
   swapped for domain-specific libraries at deployment time via config.
4. **No industry-specific state fields** — all state fields are generic
   (query, chunks, answer, citations) with no vertical-specific naming.

---

## Dependency: DRAFT-730 (MinerU PDF Extraction)

The `_ingest_pdf` handler in `ContentIngestionNode` currently uses a stub extractor.
Full PDF extraction requires **MinerU** (DRAFT-730 dependency):

- **Dependency:** DRAFT-730 (MinerU integration scaffold issue)
- **Status:** Stub until DRAFT-730 is resolved and `framework.pdf.MinerUExtractor` is available
- **Stub behavior:** Returns structured placeholder text indicating PDF processing
- **Production swap:** Replace stub with `from framework.pdf import MinerUExtractor`
  once DRAFT-730 ships; no state/interface changes required

---

## Error Handling Strategy

| Scenario | Handling |
|----------|---------|
| Empty `user_input` or empty `source_configs` | `PreProcessNode` returns `status=AgentStatus.ERROR` + appends to `error_log`; framework routes to `finalize` |
| Unknown / disallowed source_type | `PreProcessNode` returns `status=AgentStatus.ERROR` + `error_log`; framework routes to `finalize` |
| Empty `ingested_chunks` at MainNode | `MainNode` returns `status=AgentStatus.ERROR` + `error_log` |
| LLM synthesis failure | `MainNode` emits `synthesis_failed` trace, returns `status=AgentStatus.ERROR` + `error_log` (no silent failure) |
| Credential pattern in output | `PostProcessNode._extra_security_gate_output` raises → framework converts to `status=error` |

**Error propagation rule:** nodes signal failure by returning `status=AgentStatus.ERROR`
(with a message appended to `error_log`); the framework's `route()` then sends the run
to `finalize`. Nodes do **not** manually check a legacy `is_safe`/`error` flag — status
routing is owned by `AgentBaseGraph` (SUCCESS→post_process, RETRY→pre_process, ERROR→finalize).

---

## Error Propagation Strategy

`MultiSourceKnowledgeQAAgent` composes the standard 3-slot `AgentBaseGraph` backbone
(initialize → pre_process → main → post_process → finalize). Error propagation is owned
by the framework's status routing — nodes do not chain manual short-circuit checks.

### Status-driven propagation

| Category | Mechanism | Effect |
|----------|-----------|--------|
| **Node error** | A node returns `status=AgentStatus.ERROR` (+ message in `error_log`) | `route()` sends the run straight to `finalize`; later slots are not executed |
| **Retry** | A node returns `status=AgentStatus.RETRY` | `route()` re-enters `pre_process` (up to `max_retry`, default 3) |
| **Output block (S-3)** | `PostProcessNode._extra_security_gate_output` raises | Framework `__call__` converts the raise to `status=error` |
| **Unhandled exception** | Any exception inside a node `execute()` | Framework node `__call__` wrapper traps it → `status=error` (no exception escapes the agent boundary) |

Each node returns only its changed keys; the framework merges them into `State` and
evaluates `status` after every slot. There is no `is_safe`/`error`-flag short-circuit
in node code (that was the legacy pattern) — `AgentStatus` is the single control signal.

### Composition consistency note

The outer graph uses only the fixed `AgentBaseGraph` backbone (no `GraphNode`-wrapped
inner graph, no `RemoteAgentNode`, no cross-template imports). All error propagation is
defined by the framework's `route()` over `AgentStatus`, satisfying the framework composition criterion.


---

## Inheritance & Framework Contract

New-gen scaffold: there is **no local framework-stub package and no Level 2 base class**. The
outer graph extends `framework.graph.agent_base_graph.AgentBaseGraph` (L1 direct); the
three slot nodes extend `framework.nodes.function_node.FunctionNode` and implement
`execute(self, state) -> dict` (returning only changed keys, with `AgentStatus` enum
status). The framework package (`agenticstar-agentcore`) is provided by the platform /
CI runner — `pyproject.toml` declares `dependencies = []`.

State is `class State(AgentState)` (`framework.schemas.agent_state`), a flat TypedDict.
`execute()` methods accept the state dict and AST-scan-compliant `AgentState` typing is
satisfied via the inherited schema. The legacy 5-layer security that lived in
`src/agent.py` is re-homed: S-1 trust via node `required_trust_level`, S-2 input gate at
the framework + `pre_process` validation, S-3 via `PostProcessNode._extra_security_gate_output`,
S-4 via `shared.utils.audit_logger.emit_trace_event` (defensive import), S-5 automatic.

### Production / CI parity

Tests run against the same `framework.*` package the platform uses (installed by the
central scaffold CI `run-tests` job) — there is no stub-vs-production divergence to
maintain. The LLM client is injected at runtime via graph config (None in CI → MainNode
deterministic fallback); it is not declared in `config/agent.yaml`.

*Migrated to the new-gen scaffold structure 2026-06-22.*
