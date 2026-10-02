"""Fronteira de execução do parser, sem shell, rede ou código do PDF."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ingestion.contracts import LabError, Limits


def extract(data, limits=None, *, parser="pypdf", artifacts=None):
    if parser not in {"pypdf", "docling"}:
        raise LabError("Parser desconhecido.")
    limits = limits or Limits()
    if not isinstance(data, bytes) or not data or len(data) > limits.max_bytes:
        raise LabError("PDF vazio ou acima do limite de tamanho.")
    if not data.startswith(b"%PDF-"):
        raise LabError("O arquivo não tem cabeçalho PDF válido.")
    with tempfile.TemporaryDirectory(prefix="pdf-parser-") as temporary:
        output = Path(temporary) / "result.json"
        command = [sys.executable, "-m", "ingestion.worker", str(output), json.dumps(asdict(limits)), parser, artifacts or ""]
        try:
            process = subprocess.run(
                command, input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=limits.timeout_seconds, cwd=Path(__file__).resolve().parent.parent,
                check=False,
                env={**os.environ, "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                     "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"} if parser == "docling" else None,
            )
        except subprocess.TimeoutExpired:
            return {"pages": [], "error": "parser_timeout", "parser": parser}
        except OSError:
            return {"pages": [], "error": "parser_unavailable", "parser": parser}
        if process.returncode or not output.exists() or output.stat().st_size > 6 * 1024 * 1024:
            return {"pages": [], "error": "parser_terminated", "parser": parser}
        try:
            return json.loads(output.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {"pages": [], "error": "invalid_parser_result", "parser": parser}
