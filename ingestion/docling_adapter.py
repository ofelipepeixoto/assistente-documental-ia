"""Adaptação original do Docling ao contrato de revisão existente; sem download de pesos."""

from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path

from ingestion.contracts import LabError, digest


def configuration(artifacts):
    if not artifacts or not Path(artifacts).is_dir():
        raise LabError("Docling exige --artefatos com modelos locais previamente provisionados.")
    try:
        installed = version("docling")
    except PackageNotFoundError:
        raise LabError("Instale requirements-docling.txt em ambiente opcional separado.") from None
    # Hash do conjunto local: mudanças nos pesos invalidam a identidade da extração.
    entries = []
    root = Path(artifacts).resolve()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise LabError("Artefatos Docling não podem conter links simbólicos.")
        if path.is_file():
            import hashlib
            with path.open("rb") as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            entries.append(f"{path.relative_to(root)}:{sha}")
    if not entries:
        raise LabError("Diretório de artefatos Docling vazio.")
    return {"parser": "docling", "parser_version": installed,
            "artifacts_sha256": digest("\n".join(entries).encode()),
            "memory_mib_linux": 4096, "adapter_version": 1, "ocr": False, "tables": False, "remote_services": False}


def parse_docling(data, limits, artifacts):
    # Pré-validação no mesmo subprocesso, antes de carregar modelos.
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=True)
    base = {"parser": "docling", "pages": []}
    if reader.is_encrypted:
        return {**base, "error": "encrypted_pdf"}
    count = len(reader.pages)
    if not count or count > limits.max_pages:
        return {**base, "error": "page_limit"}
    from docling.datamodel.base_models import InputFormat, DocumentStream, ConversionStatus
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    options = PdfPipelineOptions(artifacts_path=Path(artifacts), do_ocr=False,
                                 do_table_structure=False, enable_remote_services=False)
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF], format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options),
    })
    result = converter.convert(DocumentStream(name="local.pdf", stream=BytesIO(data)),
                               max_num_pages=limits.max_pages, max_file_size=limits.max_bytes,
                               raises_on_error=False)
    if result.status != ConversionStatus.SUCCESS:
        return {**base, "error": "docling_conversion_failed"}
    if set(result.document.pages) != set(range(1, count + 1)):
        return {**base, "error": "docling_page_mismatch"}
    total = 0
    for number in range(1, count + 1):
        text = result.document.export_to_markdown(page_no=number)
        record = {"page_number": number, "method": "docling", "error": None}
        if len(text) > limits.max_page_chars or total + len(text) > limits.max_document_chars:
            record.update(text="", status="failed", error="text_limit")
        else:
            total += len(text)
            poor = sum(c.isalpha() for c in text) < limits.min_letters
            record.update(text=text, status="needs_ocr" if poor else "extracted")
        base["pages"].append(record)
    return {**base, "error": None}
