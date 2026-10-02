"""Importa um Dolma JSON/JSONL local; não instala ou executa o modelo."""

import json
import re

from ingestion.contracts import LabError, digest

MAX_IMPORT_BYTES = 4 * 1024 * 1024


def import_output(store, document_id, raw, *, expected_revision, source_sha256, source_file, model, model_revision):
    document = store.get(document_id)
    if source_sha256 != document["source_sha256"]:
        raise LabError("Hash de origem diferente do PDF registrado.")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise LabError("Identifique o modelo utilizado.")
    if not isinstance(source_file, str) or not source_file.strip() or len(source_file) > 1024:
        raise LabError("Identifique a fonte processada (até 1024 caracteres).")
    if not isinstance(model_revision, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", model_revision):
        raise LabError("Informe a revisão fixa do modelo (SHA de 40 caracteres).")
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_IMPORT_BYTES:
        raise LabError("Arquivo OCR vazio ou acima de 4 MiB.")
    try:
        parsed = json.loads(raw)
        metadata = parsed["metadata"]
        text = parsed["text"]
        spans = parsed["attributes"]["pdf_page_numbers"]
        count = len(document["pages"])
        if parsed["source"] != "olmocr" or metadata["Source-File"] != source_file or not source_file:
            raise ValueError
        if not count or type(metadata["pdf-total-pages"]) is not int or metadata["pdf-total-pages"] != count:
            raise ValueError
        if metadata["total-fallback-pages"] != 0 or type(metadata["total-fallback-pages"]) is not int:
            raise ValueError
        if not isinstance(metadata["olmocr-version"], str) or not metadata["olmocr-version"]:
            raise ValueError
        if len(metadata["olmocr-version"]) > 64:
            raise ValueError
        metadata["olmocr-version"].encode("utf-8")
        if not isinstance(text, str) or len(text) > document["config"]["limits"]["max_document_chars"]:
            raise ValueError
        text.encode("utf-8")
        source_file.encode("utf-8")
        model.encode("utf-8")
        if not isinstance(spans, list) or len(spans) != count:
            raise ValueError
        parts, cursor = [], 0
        for expected_number, span in enumerate(spans, 1):
            if not isinstance(span, list) or len(span) != 3 or any(type(n) is not int for n in span):
                raise ValueError
            start, end, number = span
            if number != expected_number or start != cursor or not start <= end <= len(text):
                raise ValueError
            part = text[start:end]
            if len(part) > document["config"]["limits"]["max_page_chars"]:
                raise ValueError
            parts.append(part)
            cursor = end
        if cursor != len(text):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        raise LabError("Saída OCR inválida, fonte/páginas divergentes ou fallback. Importe um único registro Dolma completo.") from None

    def change(manifest):
        provenance = {
            "model": model.strip(), "model_revision": model_revision.lower(),
            "olmocr_version": metadata["olmocr-version"], "output_sha256": digest(raw),
            "source_file_declared": source_file, "input_binding": "operator_attestation",
        }
        for page, part in zip(manifest["pages"], parts):
            page["text"] = part
            page["method"] = "olmocr_import"
            page["status"] = "extracted" if part.strip() else "needs_ocr"
            page["error"] = None
            page["review"] = None
            page["ocr_provenance"] = provenance
        manifest["events"].append({"type": "ocr.imported", **provenance, "document_revision": expected_revision})
    return store.update(document_id, expected_revision, change)
