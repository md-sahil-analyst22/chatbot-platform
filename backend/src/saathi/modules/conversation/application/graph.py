# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Connects the chat steps into a flow ('graph') using LangGraph.
# Status: 🟡 Only the guard step today; language, search, answer and handoff steps come in Phase
#         3.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Agent graph wiring (P3.1). Requires the 'agent' extra: uv sync --extra agent.

LangGraph is used only here for orchestration; nodes stay plain functions over ChatState, so
the orchestrator could be replaced without touching node logic.
"""

from typing import Any

from saathi.modules.conversation.application.nodes.guard import guard_node
from saathi.modules.conversation.domain.state import ChatState


# Builds the flow. LangGraph is imported only here, so it stays optional.
def build_graph() -> Any:
    from langgraph.graph import END, StateGraph  # lazy: optional dependency

    graph = StateGraph(ChatState)
    graph.add_node("guard", guard_node)
    graph.set_entry_point("guard")
    # P3.2 - P3.6: add language, rewrite, intent, rag, answer, handoff nodes + conditional edges.
    graph.add_edge("guard", END)
    return graph.compile()
