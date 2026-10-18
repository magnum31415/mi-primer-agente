
from typing import Literal

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from agent.state import AgentState
from agent.nodes import (
    agente,
    ejecutar_tools,
)


# ==========================================
# ROUTER
# ==========================================

def decidir_siguiente_paso(
    state: AgentState,
) -> Literal["ejecutar_tools", "__end__"]:

    ultimo_mensaje = state["messages"][-1]

    if getattr(ultimo_mensaje, "tool_calls", []):
        return "ejecutar_tools"

    return "__end__"


# ==========================================
# CONSTRUIR GRAFO
# ==========================================

builder = StateGraph(AgentState)

builder.add_node("agente", agente)
builder.add_node("ejecutar_tools", ejecutar_tools)

builder.add_edge(START, "agente")

builder.add_conditional_edges(
    "agente",
    decidir_siguiente_paso,
    {
        "ejecutar_tools": "ejecutar_tools",
        "__end__": END,
    },
)

# LOOP
builder.add_edge("ejecutar_tools", "agente")

graph = builder.compile()
