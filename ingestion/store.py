"""SQLite local com revisão vinculada ao texto e controle de versão."""

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import threading

from ingestion.contracts import (
    LabError, Limits, PIPELINE_VERSION, SCHEMA_VERSION, approved, clean_name,
    digest, now, text_digest, validate_id,
)
from ingestion.native import extract

MAX_DOCUMENTS = 50
MAX_STORED_BYTES = 128 * 1024 * 1024


def enforce_quota(db, added_bytes=0, replacing_id=None):
    rows = db.execute("SELECT id, length(original) + length(manifest) FROM documents").fetchall()
    total = sum(size for key, size in rows if key != replacing_id)
    if (replacing_id is None and len(rows) >= MAX_DOCUMENTS) or total + added_bytes > MAX_STORED_BYTES:
        raise LabError("Workspace atingiu a cota local (50 documentos ou 128 MiB lógicos).")


def document_status(pages):
    if pages and all(p["status"] == "extracted" for p in pages):
        return "extracted"
    return "partial" if any(p["status"] == "extracted" for p in pages) else "failed"


class Store:
    """Uma workspace de operador local. NÃO é auth nem isolamento multitenant."""

    def __init__(self, directory=".documentos"):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / "lab.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, original BLOB NOT NULL, manifest TEXT NOT NULL)")
        self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, document_id):
        validate_id(document_id)
        with self.connection() as db:
            row = db.execute("SELECT manifest FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            raise LabError("Documento não encontrado.")
        return json.loads(row[0])

    def original(self, document_id):
        manifest = self.get(document_id)
        with self.connection() as db:
            data = db.execute("SELECT original FROM documents WHERE id = ?", (document_id,)).fetchone()[0]
        if digest(data) != manifest["source_sha256"]:
            raise LabError("Original não corresponde ao hash registrado.")
        return data

    def list(self):
        with self.connection() as db:
            rows = db.execute("SELECT manifest FROM documents ORDER BY id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def ingest(self, data, name, limits=None):
        limits = limits or Limits()
        name = clean_name(name)
        if not isinstance(data, bytes) or not data or len(data) > limits.max_bytes or not data.startswith(b"%PDF-"):
            raise LabError("Escolha um PDF válido de até 10 MiB (limite padrão).")
        try:
            from pypdf import __version__
        except ImportError:
            raise LabError("Instale requirements-pdf.txt para usar PDFs.") from None
        config = {"pipeline": PIPELINE_VERSION, "parser_version": __version__, "limits": asdict(limits)}
        source_sha = digest(data)
        document_id = digest((source_sha + json.dumps(config, sort_keys=True)).encode())
        with self.lock:
            try:
                return self.get(document_id)
            except LabError:
                pass
            result = extract(data, limits)
            pages = [
                {**p, "extracted_text": p["text"], "review": None}
                for p in result["pages"]
            ]
            manifest = {
                "schema_version": SCHEMA_VERSION, "id": document_id,
                "source_sha256": source_sha, "original_name": name,
                "created_at": now(), "revision": 1, "config": config,
                "extraction_status": document_status(pages), "error": result["error"],
                "resource_limits_applied": result.get("resource_limits_applied", False),
                "pages": pages, "events": [],
            }
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                encoded = json.dumps(manifest)
                if not db.execute("SELECT 1 FROM documents WHERE id = ?", (document_id,)).fetchone():
                    enforce_quota(db, len(data) + len(encoded.encode("utf-8")))
                    db.execute("INSERT INTO documents VALUES (?, ?, ?)", (document_id, data, encoded))
            return self.get(document_id)

    def update(self, document_id, expected_revision, change):
        validate_id(document_id)
        if type(expected_revision) is not int:
            raise LabError("Versão de revisão inválida.")
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT manifest FROM documents WHERE id = ?", (document_id,)).fetchone()
            if not row:
                raise LabError("Documento não encontrado.")
            manifest = json.loads(row[0])
            if manifest["revision"] != expected_revision:
                raise LabError("Documento mudou. Recarregue antes de revisar.")
            if len(manifest["events"]) >= 2000:
                raise LabError("Limite de eventos deste laboratório atingido.")
            change(manifest)
            manifest["revision"] += 1
            manifest["extraction_status"] = document_status(manifest["pages"])
            encoded = json.dumps(manifest)
            original_size = db.execute("SELECT length(original) FROM documents WHERE id = ?", (document_id,)).fetchone()[0]
            enforce_quota(db, original_size + len(encoded.encode("utf-8")), replacing_id=document_id)
            db.execute("UPDATE documents SET manifest = ? WHERE id = ?", (encoded, document_id))
            return manifest

    def review(self, document_id, page_number, expected_revision, reviewer, decision, corrected_text=None):
        if decision not in {"approved", "rejected"} or not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100:
            raise LabError("Informe seu nome e uma decisão válida.")

        def change(manifest):
            if type(page_number) is not int or not 1 <= page_number <= len(manifest["pages"]):
                raise LabError("Página inválida.")
            page = manifest["pages"][page_number - 1]
            if corrected_text is not None:
                if not isinstance(corrected_text, str) or len(corrected_text) > manifest["config"]["limits"]["max_page_chars"]:
                    raise LabError("Texto corrigido acima do limite.")
                try:
                    corrected_text.encode("utf-8")
                except UnicodeError:
                    raise LabError("Texto com codificação inválida.") from None
                total = sum(len(p["text"]) for p in manifest["pages"] if p is not page) + len(corrected_text)
                if total > manifest["config"]["limits"]["max_document_chars"]:
                    raise LabError("Texto total acima do limite.")
                if corrected_text != page["text"]:
                    page.update(text=corrected_text, method="human_corrected", status="extracted" if corrected_text.strip() else "needs_ocr")
            if decision == "approved" and (page["status"] != "extracted" or not page["text"].strip()):
                raise LabError("Página sem extração válida. Corrija o texto ou rejeite.")
            page["review"] = {
                "decision": decision, "reviewer": reviewer.strip(), "identity_verified": False,
                "reviewed_at": now(), "source_sha256": manifest["source_sha256"],
                "text_sha256": text_digest(page["text"]),
            }
            manifest["events"].append({
                "type": "page.reviewed", "page_number": page_number, **page["review"],
                "document_revision": expected_revision,
            })
        return self.update(document_id, expected_revision, change)

    def approved_pages(self):
        for document in self.list():
            for page in document["pages"]:
                if approved(page, document["source_sha256"]):
                    yield document, page
