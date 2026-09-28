"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.
#
# CMN-C1-128 note: this template's nodes are self-contained (in-process keyword
# retrieval + LLM synthesis) and do not currently require an external data service.
# This module is an intentional placeholder for the new-gen layer boundary; wire a
# real service here only when an external integration (e.g. a vector DB) is added.
