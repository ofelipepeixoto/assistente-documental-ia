"""Contrato versionado e limites do laboratório de uma única pessoa."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import re

SCHEMA_VERSION = 1
PIPELINE_VERSION = "pdf-lab-1"


class LabError(ValueError):
    """Erro seguro para exibição, sem conteúdo do PDF ou traceback."""


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 10 * 1024 * 1024
    max_pages: int = 50
    max_page_chars: int = 100_000
    max_document_chars: int = 500_000
    timeout_seconds: int = 20
    min_letters: int = 20

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise LabError("Limites devem ser inteiros positivos.")
        if self.max_page_chars > self.max_document_chars:
            raise LabError("O limite por página excede o limite do documento.")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_digest(text):
    return digest(text.encode("utf-8"))


def clean_name(name):
    if not isinstance(name, str):
        raise LabError("Nome de arquivo inválido.")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if c.isprintable()).strip()[:180]
    if not name.lower().endswith(".pdf"):
        raise LabError("Escolha um arquivo PDF.")
    return name


def validate_id(document_id):
    if not isinstance(document_id, str) or not re.fullmatch(r"[a-f0-9]{64}", document_id):
        raise LabError("Identificador de documento inválido.")


def approved(page, source_sha):
    review = page.get("review") or {}
    return (
        page["status"] == "extracted"
        and bool(page["text"].strip())
        and review.get("decision") == "approved"
        and review.get("text_sha256") == text_digest(page["text"])
        and review.get("source_sha256") == source_sha
    )
