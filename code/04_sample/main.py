import os
import sys
from pathlib import Path

from IPython import get_ipython
from IPython.display import Image, display

from langchain.tools import tool
from langchain_openai import ChatOpenAI

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition


# ==================================================
# 1. DATOS SIMULADOS
# ==================================================

SERVIDORES = {
    "srv-oracle-01": {
        "cpu": 96,
        "memoria": 72,
        "procesos": [
            {"nombre": "oracle", "cpu": 89},
            {"nombre": "java", "cpu": 4},
            {"nombre": "systemd", "cpu": 1},
        ],
    },
    "srv-linux-ok": {
        "cpu": 15,
        "memoria": 35,
        "procesos": [
            {"nombre": "python", "cpu": 4},
            {"nombre": "systemd", "cpu": 1},
        ],
    },
}


def obtener_servidor(servidor: str) -> dict:
    """Validar que el servidor existe en el laboratorio."""
    if servidor not in SERVIDORES:
        raise ValueError(
            f"Servidor no permitido: {servidor}"
        )
    return SERVIDORES[servidor]


# ==================================================
# 2. TOOLS
# ==================================================

@tool
def linux_cpu_usage(servidor: str) -> dict:
    """Obtiene el porcentaje de uso de CPU de un
    servidor Linux del laboratorio."""
    print(f"[TOOL] linux_cpu_usage({servidor})")

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "cpu_percent": datos["cpu"],
    }


@tool
def linux_memory_usage(servidor: str) -> dict:
    """Obtiene el porcentaje de memoria utilizada
    por un servidor Linux del laboratorio."""
    print(f"[TOOL] linux_memory_usage({servidor})")

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "memory_percent": datos["memoria"],
    }


@tool
def linux_processes(servidor: str) -> dict:
    """Obtiene los procesos con mayor consumo de CPU
    de un servidor Linux del laboratorio."""
    print(f"[TOOL] linux_processes({servidor})")

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "procesos": datos["procesos"],
    }


# ==================================================
# 3. REGISTRAR TOOLS EN EL MODELO
# ==================================================

tools = [
    linux_cpu_usage,
    linux_memory_usage,
    linux_processes,
]

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)

llm_with_tools = llm.bind_tools(tools)


# ==================================================
# 4. NODE: AGENTE LLM
# ==================================================

SYSTEM_PROMPT = """
Eres un agente de diagnóstico de servidores Linux.

Tienes tres herramientas:
- linux_cpu_usage
- linux_memory_usage
- linux_processes

Reglas:
1. Usa herramientas para obtener las métricas.
2. No inventes datos de servidores.
3. Si detectas CPU elevada, investiga los procesos.
4. Puedes consultar memoria cuando sea relevante.
5. No repitas herramientas innecesariamente.
6. No afirmes causas que no estén demostradas.
7. No ejecutes ni propongas cambios destructivos.
8. Una vez tengas información suficiente, responde
   con un diagnóstico técnico breve en español.
9. Distingue hechos observados de hipótesis.
"""


def agente(state: MessagesState):
    print("\n[NODE] agente")

    respuesta = llm_with_tools.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]
    )

    return {
        "messages": [respuesta]
    }


# ==================================================
# 5. NODE: EJECUTAR TOOLS
# ==================================================

tool_node = ToolNode(
    tools,
    handle_tool_errors=True,
)


# ==================================================
# 6. CONSTRUIR LANGGRAPH
# ==================================================

builder = StateGraph(MessagesState)

builder.add_node("agente", agente)
builder.add_node("tools", tool_node)

builder.add_edge(START, "agente")

builder.add_conditional_edges(
    "agente",
    tools_condition,
    {
        "tools": "tools",
        "__end__": END,
    },
)

# LOOP: volver al LLM después de ejecutar Tools
builder.add_edge("tools", "agente")

graph = builder.compile()


# ==================================================
# 7. GENERAR Y VISUALIZAR EL GRAFO
# ==================================================

# Determinar el directorio donde guardar el diagrama
# Compatible con scripts Python y Jupyter Notebook
directorio = (
    Path(__file__).resolve().parent
    if "__file__" in globals()
    else Path.cwd()
)

# Obtener el código Mermaid del grafo compilado
mermaid_code = graph.get_graph().draw_mermaid()

# Guardar el código Mermaid en un fichero .mmd
ruta_mermaid = directorio / "graph.mmd"
ruta_mermaid.write_text(mermaid_code, encoding="utf-8")

print(f"[GRAPH] Mermaid guardado en: {ruta_mermaid}")

# Generar la imagen PNG del grafo
# Si el renderizado falla, el agente continúa ejecutándose
try:
    png_data = graph.get_graph().draw_mermaid_png()

    # Guardar el PNG
    ruta_png = directorio / "graph.png"
    ruta_png.write_bytes(png_data)

    print(f"[GRAPH] PNG guardado en: {ruta_png}")

    # Si estamos en Jupyter, mostrar la imagen directamente
    ipython = get_ipython()

    if ipython is not None and "IPKernelApp" in ipython.config:
        display(Image(data=png_data))

except Exception as error:
    print(f"[GRAPH] No se pudo generar el PNG: {error}")


# ==================================================
# 8. EJECUTAR
# ==================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Uso: uv run python main.py <servidor>")
        sys.exit(1)

    servidor = sys.argv[1]

    # Validación antes de llamar al LLM
    obtener_servidor(servidor)

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("Falta OPENAI_API_KEY")

    pregunta = (
        f"Investiga el estado de CPU del servidor "
        f"{servidor}. Consulta las herramientas "
        f"necesarias y genera un diagnóstico."
    )

    resultado = graph.invoke(
        {
            "messages": [
                HumanMessage(content=pregunta)
            ]
        },
        config={
            "recursion_limit": 16
        },
    )

    print("\n========== DIAGNÓSTICO ==========")
    print(resultado["messages"][-1].content)