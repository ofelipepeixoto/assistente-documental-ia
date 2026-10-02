"""Parser em subprocesso: prazo no pai; memória/CPU/arquivo limitados em POSIX."""

from io import BytesIO
import json
from pathlib import Path
import sys

from ingestion.contracts import Limits


def resource_limits(seconds, memory_mib=512):
    if sys.platform != "linux":
        return False
    try:
        import resource
    except ImportError:
        return False
    resource.setrlimit(resource.RLIMIT_AS, (memory_mib * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (6 * 1024 * 1024,) * 2)
    return True


def parse(data, limits):
    from pypdf import PdfReader, __version__

    reader = PdfReader(BytesIO(data), strict=True)
    base = {"parser": "pypdf", "parser_version": __version__, "pages": []}
    if reader.is_encrypted:
        return {**base, "error": "encrypted_pdf"}
    count = len(reader.pages)
    if not count or count > limits.max_pages:
        return {**base, "error": "page_limit"}
    total = 0
    for number, page in enumerate(reader.pages, 1):
        record = {"page_number": number, "method": "native", "error": None}
        try:
            text = page.extract_text() or ""
            if len(text) > limits.max_page_chars or total + len(text) > limits.max_document_chars:
                record.update(text="", status="failed", error="text_limit")
            else:
                total += len(text)
                letters = sum(c.isalpha() for c in text)
                poor = letters < limits.min_letters or text.count("\ufffd") > max(1, len(text) // 100)
                record.update(text=text, status="needs_ocr" if poor else "extracted")
        except Exception:
            record.update(text="", status="failed", error="page_extraction_failed")
        base["pages"].append(record)
    return {**base, "error": None}


def main():
    limits = Limits(**json.loads(sys.argv[2]))
    parser = sys.argv[3] if len(sys.argv) > 3 else "pypdf"
    capped = resource_limits(limits.timeout_seconds, 4096 if parser == "docling" else 512)
    data = sys.stdin.buffer.read(limits.max_bytes + 1)
    try:
        if parser == "docling":
            from ingestion.docling_adapter import parse_docling
            result = parse_docling(data, limits, sys.argv[4])
        else:
            result = parse(data, limits)
    except Exception:
        result = {"pages": [], "error": "pdf_parse_failed", "parser": parser}
    result["resource_limits_applied"] = capped
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
