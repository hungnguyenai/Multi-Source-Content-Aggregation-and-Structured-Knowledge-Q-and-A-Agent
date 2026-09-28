# CMN-C1-128 — Test Specification

**Template:** CMN-C1-128 Multi-Source Content Aggregation & Structured Knowledge Q&A Agent
**Category:** Cat 1 | CMN
**Version:** 1.0.0 (new-gen scaffold)

> Rewritten 2026-06-22 for the new-gen scaffold structure. Tests live under
> `tests/unit/`, `tests/integration/`, `tests/proof_of_boundary/`. The legacy layout
> was removed in the migration. Framework-compliance is now enforced by the central
> scaffold CI gates (import-isolation, composition, invoke-chain, state-safety, etc.),
> not by per-template TC stubs.

---

## 1. Test Strategy

| Layer | Location | What it verifies |
|---|---|---|
| Unit | `tests/unit/` | Each node's `execute()` in isolation — happy + error paths, LLM-None fallback |
| Integration | `tests/integration/` | Full `agent.invoke()` through the 5-node backbone (Initialize→Pre→Main→Post→Finalize) incl. S-3 hook |
| Proof-of-Boundary | `tests/proof_of_boundary/` | Framework boundary invariants (import isolation, state safety) |

**Total tests: 19** (all green — CI pipeline run-tests). LLM is `None` in CI; `MainNode`
uses its deterministic fallback path so tests are network-free.

---

## 2. Unit Tests

### `tests/unit/test_pre_process_node.py` — PreProcessNode (6)
| Test | Verifies |
|---|---|
| `test_empty_user_input_returns_error` | empty question → `status=ERROR` |
| `test_empty_source_configs_returns_error` | no sources → `status=ERROR` + `error_log` |
| `test_invalid_source_type_returns_error` | disallowed source_type → `status=ERROR` |
| `test_valid_sources_produce_routing_plan_and_chunks` | happy path → `routing_plan`, `ingested_chunks`, `validated_input`, `SUCCESS` |
| `test_multiple_sources_all_ingested` | N sources → N ingested chunks |
| `test_allowed_types_config_override_restricts` | `allowed_source_types` config restricts routing |

### `tests/unit/test_main_node.py` — MainNode (5)
| Test | Verifies |
|---|---|
| `test_empty_ingested_chunks_returns_error` | no chunks → `status=ERROR` |
| `test_fallback_synthesis_without_llm` | LLM=None → deterministic answer + `result` + citations + `SUCCESS` |
| `test_retrieval_ranks_by_keyword_overlap` | top chunk = highest keyword overlap; scores descending |
| `test_top_k_config_limits_retrieved` | `top_k` config caps retrieved count |
| `test_citations_deduplicated_by_uri` | duplicate source_uri → single citation |

### `tests/unit/test_post_process_node.py` — PostProcessNode (4)
| Test | Verifies |
|---|---|
| `test_formats_answer_and_citations` | `formatted_output` JSON + `result` + `SUCCESS` |
| `test_s3_gate_passes_clean_output` | `_extra_security_gate_output` returns clean output unchanged |
| `test_s3_gate_blocks_credential_leak` | API-key pattern in output → raises (blocked) |
| `test_s3_gate_blocks_jwt_leak` | JWT pattern in output → raises (blocked) |

---

## 3. Integration Tests

### `tests/integration/test_invoke.py` (2)
| Test | Verifies |
|---|---|
| `test_backbone_nodes_registered` | compile() registers all 5 backbone nodes (Initialize/Pre/Main/Post/Finalize) |
| `test_invoke_reaches_terminal_status` | full `agent.invoke()` reaches a terminal `AgentStatus` (SUCCESS/ERROR), never hangs — exercises the full gate→execute→gate chain incl. S-3 hook |

---

## 4. Proof-of-Boundary Tests

### `tests/proof_of_boundary/` (2)
| Test | Boundary |
|---|---|
| `test_import_isolation.py::test_no_prohibited_imports_in_src` | PB-4 — `src/` does not import the Level-0 SDK (`agenticstar`) |
| `test_state_safety.py::test_state_file_safety` | PB-2/PB-5 — `State` has no credential-named fields / Pydantic / InvocationContext annotations (msgpack-safe) |

---

## 5. Running

```bash
pip install -e ".[dev]"   # framework provided by platform / CI runner
python -m pytest tests/ -v
```

Framework-compliance and security gates (5-layer, import isolation, composition,
invoke-chain, dependency pinning) are enforced by the **central scaffold CI** at MR
time — see the central CI configuration.
