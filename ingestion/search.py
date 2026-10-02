"""Retorna evidências aprovadas; não interpreta cláusulas nem chama um LLM."""

import re
import unicodedata

from ingestion.contracts import LabError

STOP = set("a as o os de do da dos das e em um uma qual quais que com para por pelo pela no na nos nas eh documento documentos contrato clausula valor informado prevista previsto sobre".split())


def tokens(text):
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return {word for word in re.findall(r"[a-z0-9]+", text) if len(word) > 2 and word not in STOP}


def search(store, question, limit=3):
    if not isinstance(question, str) or len(question) > 500 or type(limit) is not int or not 1 <= limit <= 10:
        raise LabError("Pergunta ou limite inválido.")
    terms = tokens(question)
    if not terms:
        return []
    results = []
    for document, page in store.approved_pages():
        if terms <= tokens(page["text"]):
            results.append({
                "document_id": document["id"], "document_revision": document["revision"],
                "source_sha256": document["source_sha256"], "page_number": page["page_number"],
                "original_name": document["original_name"], "text": page["text"],
                "text_sha256": page["review"]["text_sha256"], "method": page["method"],
                "citation": f"{document['original_name']} — página {page['page_number']}",
            })
    return results[:limit]
