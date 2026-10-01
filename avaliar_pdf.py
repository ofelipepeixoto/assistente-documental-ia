"""Avaliação sintética do parser, revisão e recuperação; NÃO mede OCR real."""

import argparse
import json
from pathlib import Path
import re
import tempfile
import unicodedata

from avaliacao.pdf_fixtures import PAGES, make_pdf
from ingestion.search import search
from ingestion.store import Store


def normalize(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def distance(first, second):
    previous = list(range(len(second) + 1))
    for i, a in enumerate(first, 1):
        current = [i]
        for j, b in enumerate(second, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def evaluate():
    cases = json.loads((Path(__file__).parent / "avaliacao/casos_pdf.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory)
        doc = store.ingest(make_pdf(), "contrato_demo.pdf")
        before_review = search(store, "pagamento mensal")
        expected = normalize("\n".join(PAGES))
        actual = normalize("\n".join(page["text"] for page in doc["pages"]))
        cer = distance(expected, actual) / len(expected)
        wer = distance(expected.split(), actual.split()) / len(expected.split())
        for page in doc["pages"]:
            doc = store.review(doc["id"], page["page_number"], doc["revision"], "revisor-ficticio", "approved")
        results = []
        for case in cases:
            matches = search(store, case["pergunta"])
            pages = [match["page_number"] for match in matches]
            content = "\n".join(match["text"] for match in matches)
            results.append({
                "pergunta": case["pergunta"], "esperado": case["paginas"], "encontrado": pages,
                "acertou": pages == case["paginas"] and all(field in content for field in case["campos"]),
                "citacoes": [match["citation"] for match in matches],
            })
        scan = store.ingest(make_pdf([""], scan=True), "scan_sintetico.pdf")
        return {
            "corpus": "PDFs sintéticos PT-BR; WinAnsi/Helvetica; NÃO corpus jurídico real",
            "pipeline": doc["config"], "native_pages": len(doc["pages"]),
            "cer_normalizado": cer, "wer_normalizado": wer,
            "bloqueio_antes_revisao": not before_review,
            "scan_sinalizado": scan["pages"][0]["status"] == "needs_ocr",
            "casos": results, "acertos": sum(item["acertou"] for item in results),
            "total_casos": len(results), "ocr_inferencia_executada": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--saida", help="Arquivo JSON de resultado")
    parser.add_argument("--strict", action="store_true", help="Falhar se o contrato sintético regredir")
    args = parser.parse_args()
    result = evaluate()
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.saida:
        Path(args.saida).write_text(output + "\n", encoding="utf-8")
    if args.strict and not (
        result["acertos"] == result["total_casos"] and result["cer_normalizado"] == 0
        and result["wer_normalizado"] == 0 and result["bloqueio_antes_revisao"] and result["scan_sinalizado"]
    ):
        raise SystemExit(1)
