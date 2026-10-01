"""Fronteira de execução do parser, sem shell, rede ou código do PDF."""

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from ingestion.contracts import LabError, Limits


def extract(data, limits=None):
    limits = limits or Limits()
    if not isinstance(data, bytes) or not data or len(data) > limits.max_bytes:
        raise LabError("PDF vazio ou acima do limite de tamanho.")
    if not data.startswith(b"%PDF-"):
        raise LabError("O arquivo não tem cabeçalho PDF válido.")
    with tempfile.TemporaryDirectory(prefix="pdf-parser-") as temporary:
        output = Path(temporary) / "result.json"
        command = [sys.executable, "-m", "ingestion.worker", str(output), json.dumps(asdict(limits))]
        try:
            process = subprocess.run(
                command, input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=limits.timeout_seconds, cwd=Path(__file__).resolve().parent.parent,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"pages": [], "error": "parser_timeout", "parser": "pypdf"}
        except OSError:
            return {"pages": [], "error": "parser_unavailable", "parser": "pypdf"}
        if process.returncode or not output.exists() or output.stat().st_size > 6 * 1024 * 1024:
            return {"pages": [], "error": "parser_terminated", "parser": "pypdf"}
        try:
            return json.loads(output.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {"pages": [], "error": "invalid_parser_result", "parser": "pypdf"}
