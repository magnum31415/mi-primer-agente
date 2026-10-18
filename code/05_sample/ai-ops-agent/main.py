
import os
import sys
import uuid

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)

from agent.graph import graph
from agent.config import SERVIDORES
from agent.audit import registrar_evento


def main():

    if len(sys.argv) != 2:
        sys.exit(
            "Uso: uv run python main.py <servidor>"
        )

    servidor = sys.argv[1]

    if servidor not in SERVIDORES:
        sys.exit("Servidor no autorizado")

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("Falta OPENAI_API_KEY")

    run_id = str(uuid.uuid4())

    print(f"RUN ID: {run_id}")
    print(f"Servidor: {servidor}")

    registrar_evento(
        run_id, servidor, "START"
    )

    estado_inicial = {
        "servidor": servidor,
        "tool_calls_used": 0,
        "messages": [
            HumanMessage(
                content=(
                    f"Investiga la alerta de CPU "
                    f"del servidor {servidor}. "
                    f"Usa las herramientas necesarias "
                    f"y genera un diagnóstico."
                )
            )
        ],
    }

    diagnostico = None
    solicitudes = 0

    try:
        for actualizacion in graph.stream(
            estado_inicial,
            config={"recursion_limit": 20},
            stream_mode="updates",
        ):

            for nombre_nodo, cambios in actualizacion.items():

                print(f"\n[NODE] {nombre_nodo}")

                if not isinstance(cambios, dict):
                    continue

                if "tool_calls_used" in cambios:
                    solicitudes = cambios["tool_calls_used"]

                for mensaje in cambios.get("messages", []):

                    if isinstance(mensaje, AIMessage):

                        if mensaje.tool_calls:

                            for llamada in mensaje.tool_calls:
                                nombre = llamada["name"]

                                print(
                                    f"[LLM] Solicita {nombre}"
                                )

                                registrar_evento(
                                    run_id,
                                    servidor,
                                    "TOOL_REQUEST",
                                    {"tool": nombre}
                                )

                        else:
                            diagnostico = mensaje.content

                    elif isinstance(mensaje, ToolMessage):

                        print(
                            f"[TOOL] Resultado de {mensaje.name}"
                        )

                        # Identificamos errores controlados.
                        import json

                        try:
                            datos = json.loads(mensaje.content)
                            error = isinstance(datos, dict) and (
                                "error" in datos
                            )
                        except (ValueError, TypeError):
                            error = False

                        registrar_evento(
                            run_id,
                            servidor,
                            "TOOL_RESULT",
                            {
                                "tool": mensaje.name,
                                "status": (
                                    "error" if error else "success"
                                )
                            }
                        )

        registrar_evento(
            run_id,
            servidor,
            "END",
            {"tool_requests_counted": solicitudes}
        )

        print("\n========== DIAGNÓSTICO ==========")
        print(diagnostico or "Sin diagnóstico disponible")

    except Exception as exc:

        registrar_evento(
            run_id,
            servidor,
            "FAILED",
            {"error_type": type(exc).__name__}
        )

        raise


if __name__ == "__main__":
    main()
