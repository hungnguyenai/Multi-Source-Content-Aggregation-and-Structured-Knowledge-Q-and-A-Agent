"""AGENTIC STAR Marketplace entrypoint — one-shot Pod process.

Invoked by the Dockerfile as CMD ["python", "cli.py"]. Compiles the agent,
provisions its secrets, then hands the Marketplace lifecycle to
shared.bootstrap.marketplace_app.

The class below must match `class:` in config/agent.yaml. The deploy kit's
default entrypoint hardcodes `Graph`, so a repo whose class is named anything
else fails with ImportError the instant the container starts — while build, push
and registration all still report success.

This repo has a config/config.yaml and its values change the answer, so it is
loaded explicitly here. The Marketplace runner does not read that file — omit the
load and every runtime parameter silently falls back to a default while the agent
still returns a confident-looking answer.
"""

from pathlib import Path

from framework.utils.config_loader import load_agent_config
from src.graph.graph import MultiSourceKnowledgeQAAgent
from shared.bootstrap.marketplace_app import run_agent_marketplace

if __name__ == "__main__":
    run_agent_marketplace(
        MultiSourceKnowledgeQAAgent,
        agent_name="cmn_c1_128",
        namespace="cmn-c1-128",
        config=load_agent_config(Path(__file__).resolve().parent),
    )
