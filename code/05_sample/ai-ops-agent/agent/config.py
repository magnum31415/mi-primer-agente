
import os

# Límite total de solicitudes de Tools
MAX_TOOL_CALLS = 4

# Modelo utilizado
MODEL_NAME = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)

# Laboratorio: servidores autorizados y sus métricas
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
