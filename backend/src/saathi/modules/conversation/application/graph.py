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

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From saathi.modules.conversation.application.nodes.guard — the first chat step (blocks bad
#   messages): guard_node = the guard step.
from saathi.modules.conversation.application.nodes.guard import guard_node

# From saathi.modules.conversation.domain.state — the data passed between chat steps: ChatState
#   = the data passed between chat steps.
from saathi.modules.conversation.domain.state import ChatState


# Builds the flow. LangGraph is imported only here, so it stays optional.
def build_graph() -> Any:
    # From langgraph.graph — LangGraph, which connects chat steps into a flow: END = the 'flow
    #   finished' marker; StateGraph = the flow builder.
    from langgraph.graph import END, StateGraph  # lazy: optional dependency

    graph = StateGraph(ChatState)
    graph.add_node("guard", guard_node)
    graph.set_entry_point("guard")
    # P3.2 - P3.6: add language, rewrite, intent, rag, answer, handoff nodes + conditional edges.
    graph.add_edge("guard", END)
    return graph.compile()
