import os
import sys
from pathlib import Path
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from IPython import get_ipython
from IPython.display import Image, display


# ==================================================
# 1. STATE: Información compartida
# ==================================================

class AgentState(TypedDict):
    servidor: str
    cpu: int
    memoria: int
    proceso: str
    diagnostico: str


# ==================================================
# 2. NODE: Consultar métricas
# ==================================================

def consultar_metricas(state: AgentState):
    print(f"[NODE] Consultando {state['servidor']}")

    # Simulamos métricas de Linux.
    # En la clase 4 crearemos herramientas reales.
    if state["servidor"] == "srv-linux-ok":
        return {
            "cpu": 25,
            "memoria": 40,
            "proceso": "systemd"
        }

    return {
        "cpu": 95,
        "memoria": 88,
        "proceso": "oracle"
    }


# ==================================================
# 3. ROUTER: Decidir si hace falta diagnóstico
# ==================================================

def decidir_ruta(
    state: AgentState
) -> Literal["diagnosticar_llm", "finalizar_normal"]:

    if state["cpu"] > 90 or state["memoria"] > 90:
        print("[ROUTER] Anomalía detectada")
        return "diagnosticar_llm"

    print("[ROUTER] Métricas normales")
    return "finalizar_normal"


# ==================================================
# 4. NODE: Diagnóstico mediante un LLM
# ==================================================

def diagnosticar_llm(state: AgentState):
    print("[NODE] Solicitando diagnóstico al LLM")

    # Crear el cliente del modelo
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0
    )

    # Instrucciones para el modelo
    mensajes = [
        (
            "system",
            "Eres un asistente experto en diagnóstico Linux. "
            "Analiza las métricas proporcionadas. "
            "Explica las posibles causas y recomienda "
            "comprobaciones adicionales. "
            "No inventes evidencias ni afirmes haber "
            "ejecutado comandos. "
            "No propongas cambios destructivos."
        ),
        (
            "human",
            f"""
            Servidor: {state['servidor']}
            CPU: {state['cpu']}%
            Memoria: {state['memoria']}%
            Proceso observado: {state['proceso']}

            Genera un diagnóstico técnico breve
            en español.
            """
        )
    ]

    # Llamada real al LLM
    respuesta = llm.invoke(mensajes)

    # Actualizar el estado
    return {
        "diagnostico": str(respuesta.content)
    }


# ==================================================
# 5. NODE: Finalizar sin llamar al LLM
# ==================================================

def finalizar_normal(state: AgentState):
    print("[NODE] No se necesita diagnóstico con IA")

    return {
        "diagnostico": "Métricas dentro de los umbrales."
    }


# ==================================================
# 6. CONSTRUIR LANGGRAPH
# ==================================================

builder = StateGraph(AgentState)

builder.add_node("consultar_metricas", consultar_metricas)
builder.add_node("diagnosticar_llm", diagnosticar_llm)
builder.add_node("finalizar_normal", finalizar_normal)

builder.add_edge(START, "consultar_metricas")

builder.add_conditional_edges(
    "consultar_metricas",
    decidir_ruta,
    {
        "diagnosticar_llm": "diagnosticar_llm",
        "finalizar_normal": "finalizar_normal"
    }
)

builder.add_edge("diagnosticar_llm", END)
builder.add_edge("finalizar_normal", END)

graph = builder.compile()


# ==================================================
# 7. VISUALIZAR EL GRAFO
# ==================================================

# Generar la imagen PNG del grafo
png_data = graph.get_graph().draw_mermaid_png()

# Guardar el PNG en el mismo directorio que main.py
ruta_png = Path("graph.png")
ruta_png.write_bytes(png_data)

print(f"[GRAPH] Grafo guardado en: {ruta_png.resolve()}")

# Si estamos en Jupyter, mostrar la imagen directamente
ipython = get_ipython()

if ipython is not None and "IPKernelApp" in ipython.config:
    display(Image(data=png_data))


# ==================================================
# 8. EJECUTAR
# ==================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Uso: uv run python main.py <servidor>")
        sys.exit(1)

    servidor = sys.argv[1]

    if not os.getenv("OPENAI_API_KEY"):
        print("Aviso: OPENAI_API_KEY no configurada.")
        print("Será necesaria si se detecta una anomalía.")

    resultado = graph.invoke({
        "servidor": servidor,
        "cpu": 0,
        "memoria": 0,
        "proceso": "",
        "diagnostico": ""
    })

    print("\n========== DIAGNÓSTICO ==========")
    print(resultado["diagnostico"])