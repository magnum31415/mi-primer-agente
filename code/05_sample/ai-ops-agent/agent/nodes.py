
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage,
    ToolMessage,
)

from agent.config import (
    MAX_TOOL_CALLS,
    MODEL_NAME,
)
from agent.state import AgentState
from agent.tools import TOOLS, TOOLS_BY_NAME


# ==========================================
# 1. MODELO
# ==========================================

llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=0,
    timeout=30,
    max_retries=2,
)

llm_with_tools = llm.bind_tools(TOOLS)


# ==========================================
# 2. PROMPT
# ==========================================

SYSTEM_PROMPT = """
Eres un agente de diagnóstico Linux.

Objetivo:
Investigar alertas de CPU de servidores.

Reglas:
- Consulta la CPU mediante herramientas.
- Si está elevada, investiga los procesos.
- Consulta memoria si es relevante.
- No repitas herramientas innecesariamente.
- No inventes métricas ni ejecuciones.
- No ejecutes comandos destructivos.
- Distingue hechos de hipótesis.
- Solo tienes permiso de lectura.
- Responde en español.

Cuando hayas obtenido suficiente información
o se agote el presupuesto de herramientas,
genera el diagnóstico con la información disponible.
Indica qué no has podido comprobar.
"""


# ==========================================
# 3. NODO AGENTE
# ==========================================

def agente(state: AgentState):

    usadas = state["tool_calls_used"]

    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ]

    if usadas >= MAX_TOOL_CALLS:
        # El modelo deja de tener Tools disponibles
        respuesta = llm.invoke(
            mensajes + [
                SystemMessage(
                    content=(
                        "Se ha agotado el presupuesto "
                        "de herramientas. Genera ahora "
                        "el diagnóstico final sin "
                        "solicitar otras comprobaciones."
                    )
                )
            ]
        )
    else:
        respuesta = llm_with_tools.invoke(mensajes)

    return {
        "messages": [respuesta]
    }


# ==========================================
# 4. NODO EJECUTOR DE TOOLS
# ==========================================

def ejecutar_tools(state: AgentState):

    ultimo_mensaje = state["messages"][-1]

    usadas = state["tool_calls_used"]
    resultados = []

    for llamada in ultimo_mensaje.tool_calls:

        nombre = llamada["name"]
        argumentos = llamada["args"]
        call_id = llamada["id"]

        if usadas >= MAX_TOOL_CALLS:
            contenido = {
                "error": "Presupuesto de Tools agotado"
            }

        else:
            # Contamos también los intentos rechazados
            usadas += 1

            herramienta = TOOLS_BY_NAME.get(nombre)

            if herramienta is None:
                contenido = {
                    "error": "Tool no autorizada"
                }

            elif not isinstance(argumentos, dict):
                contenido = {
                    "error": "Argumentos inválidos"
                }

            elif argumentos.get("servidor") != state["servidor"]:
                contenido = {
                    "error": "Servidor no autorizado"
                }

            else:
                try:
                    resultado = herramienta.invoke(argumentos)

                    contenido = resultado

                except Exception:
                    # No revelar detalles internos al LLM
                    contenido = {
                        "error": "Error ejecutando Tool"
                    }

        resultados.append(
            ToolMessage(
                content=json.dumps(
                    contenido,
                    ensure_ascii=False
                ),
                name=nombre,
                tool_call_id=call_id,
            )
        )

    return {
        "messages": resultados,
        "tool_calls_used": usadas,
    }
