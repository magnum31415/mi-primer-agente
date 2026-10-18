
import json
from datetime import datetime, timezone
from pathlib import Path


LOG_FILE = Path("logs/audit.jsonl")


def registrar_evento(
    run_id: str,
    servidor: str,
    evento: str,
    detalle: dict | None = None,
):
    """Escribe un evento estructurado en JSONL."""

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    registro = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "run_id": run_id,
        "servidor": servidor,
        "evento": evento,
        "detalle": detalle or {},
    }

    with LOG_FILE.open(
        "a",
        encoding="utf-8"
    ) as fichero:

        fichero.write(
            json.dumps(
                registro,
                ensure_ascii=False
            ) + "\n"
        )
