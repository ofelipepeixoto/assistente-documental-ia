"""CLI local; o fluxo principal para leigos está em documentos_web.py."""

import argparse
import json
from pathlib import Path

from ingestion.contracts import LabError, Limits
from ingestion.olmocr import MAX_IMPORT_BYTES, import_output
from ingestion.search import search
from ingestion.store import Store


def read_bounded(path, size):
    with Path(path).open("rb") as stream:
        return stream.read(size + 1)


def main():
    parser = argparse.ArgumentParser(description="Laboratório documental local, sem API paga.")
    parser.add_argument("--pasta", default=".documentos")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingerir")
    ingest.add_argument("pdf")
    commands.add_parser("listar")
    show = commands.add_parser("mostrar")
    show.add_argument("id")
    review = commands.add_parser("revisar")
    review.add_argument("id")
    review.add_argument("pagina", type=int)
    review.add_argument("--versao", type=int, required=True)
    review.add_argument("--revisor", required=True)
    review.add_argument("--decisao", choices=["approved", "rejected"], required=True)
    review.add_argument("--texto", help="Arquivo UTF-8 de correção opcional")
    query = commands.add_parser("buscar")
    query.add_argument("pergunta")
    ocr = commands.add_parser("importar-ocr")
    ocr.add_argument("id")
    ocr.add_argument("arquivo")
    ocr.add_argument("--versao", type=int, required=True)
    ocr.add_argument("--sha256-origem", required=True)
    ocr.add_argument("--fonte-processada", required=True)
    ocr.add_argument("--modelo", required=True)
    ocr.add_argument("--revisao-modelo", required=True)
    args = parser.parse_args()
    store = Store(args.pasta)
    try:
        if args.command == "ingerir":
            result = store.ingest(read_bounded(args.pdf, Limits().max_bytes), Path(args.pdf).name)
        elif args.command == "listar":
            result = store.list()
        elif args.command == "mostrar":
            result = store.get(args.id)
        elif args.command == "revisar":
            correction = read_bounded(args.texto, Limits().max_page_chars * 4).decode("utf-8") if args.texto else None
            result = store.review(args.id, args.pagina, args.versao, args.revisor, args.decisao, correction)
        elif args.command == "buscar":
            result = search(store, args.pergunta)
        else:
            result = import_output(
                store, args.id, read_bounded(args.arquivo, MAX_IMPORT_BYTES),
                expected_revision=args.versao, source_sha256=args.sha256_origem,
                source_file=args.fonte_processada, model=args.modelo, model_revision=args.revisao_modelo,
            )
    except (LabError, OSError, UnicodeError) as exc:
        parser.exit(1, f"Não foi possível concluir: {exc if isinstance(exc, LabError) else 'arquivo indisponível ou codificação inválida'}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
