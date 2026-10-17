"""RepoBrain Company Brain Agent package.

Provides evidence-gated question answering with typed graph tools, freshness checking,
bounded execution loops, and strict non-LLM verification.
"""

from src.agent.models import AgentAnswer, AgentRequest, Claim, SourceItem, ToolCall, ToolResult
from src.agent.loop import AgentExecutionLoop
from src.agent.tools import ToolRegistry, get_default_tool_registry
from src.agent.verifier import AgentEvidenceVerifier

__all__ = [
    "AgentAnswer",
    "AgentRequest",
    "Claim",
    "SourceItem",
    "ToolCall",
    "ToolResult",
    "AgentExecutionLoop",
    "ToolRegistry",
    "get_default_tool_registry",
    "AgentEvidenceVerifier",
]
