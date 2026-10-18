
from langchain_core.tools import tool

from agent.config import SERVIDORES


def obtener_servidor(servidor: str) -> dict:
    """Obtiene datos simulados de un servidor autorizado."""

    if servidor not in SERVIDORES:
        raise ValueError(
            f"Servidor no autorizado: {servidor}"
        )

    return SERVIDORES[servidor]


@tool
def linux_cpu_usage(servidor: str) -> dict:
    """Consulta el porcentaje de CPU de un servidor
    Linux autorizado del laboratorio."""

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "cpu_percent": datos["cpu"],
    }


@tool
def linux_memory_usage(servidor: str) -> dict:
    """Consulta el porcentaje de memoria utilizada
    por un servidor Linux autorizado del laboratorio."""

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "memory_percent": datos["memoria"],
    }


@tool
def linux_processes(servidor: str) -> dict:
    """Consulta los procesos y su consumo de CPU
    de un servidor Linux autorizado del laboratorio."""

    datos = obtener_servidor(servidor)

    return {
        "servidor": servidor,
        "procesos": datos["procesos"],
    }


# Catálogo de herramientas autorizadas
TOOLS = [
    linux_cpu_usage,
    linux_memory_usage,
    linux_processes,
]

# Facilita buscar una Tool por su nombre
TOOLS_BY_NAME = {
    herramienta.name: herramienta
    for herramienta in TOOLS
}
