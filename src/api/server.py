"""AgentCore Platform v1.0"""

# Standalone HTTP entry point for the agent.
# Entry points are adapters only — no business logic here.
# For platform-level routing, AgentGateway calls agent.invoke() directly.

import json
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.context import bound_secrets
from shared.secrets import factory as secrets_factory
from src.graph.graph import MultiSourceKnowledgeQAAgent

app = FastAPI(title="CMN-C1-128 Multi-Source Knowledge Q&A Agent")

agent = MultiSourceKnowledgeQAAgent()
agent.compile()
agent.provision_secrets(secrets_factory(namespace="cmn-c1-128", agent_name="cmn_c1_128"))


class InvokeRequest(BaseModel):
    input: str
    session_id: str = ""
    source_configs: list[dict[str, Any]] = []


@app.post("/invoke")
async def invoke(req: InvokeRequest, request: Request) -> dict[str, Any]:
    with bound_secrets(agent._secrets_provider):
        ctx = InvocationContext(
            session_id=req.session_id or str(uuid4()),
            caller_trust_level=getattr(request.state, "trust_level", TrustLevel.ANONYMOUS),
            caller_id=getattr(request.state, "caller_id", ""),
        )
        envelope = json.dumps({"query": req.input, "source_configs": req.source_configs})
        return cast("dict[str, Any]", agent.invoke(envelope, ctx=ctx))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "cmn_c1_128"}
