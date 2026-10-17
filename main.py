
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# 1. Definir el estado compartido
class AgentState(TypedDict):
    servidor: str
    cpu: int
    diagnostico: str


# 2. Primer nodo: consultar CPU
def consultar_cpu(state: AgentState):
    print(f"Consultando CPU de {state['servidor']}")

    # Simulamos un valor de CPU
    return {"cpu": 35}


# 3. Segundo nodo: analizar CPU
def analizar_cpu(state: AgentState):
    cpu = state["cpu"]

    if cpu > 90:
        resultado = "CRITICAL: CPU muy alta"
    else:
        resultado = "OK: CPU normal"

    return {"diagnostico": resultado}


# 4. Construir el grafo
builder = StateGraph(AgentState)

builder.add_node("consultar_cpu", consultar_cpu)
builder.add_node("analizar_cpu", analizar_cpu)

# 5. Conectar los nodos
builder.add_edge(START, "consultar_cpu")
builder.add_edge("consultar_cpu", "analizar_cpu")
builder.add_edge("analizar_cpu", END)

# 6. Compilar
graph = builder.compile()


# 7. Ejecutar
resultado = graph.invoke({
    "servidor": "srv-linux-01",
    "cpu": 0,
    "diagnostico": ""
})

print(resultado)
