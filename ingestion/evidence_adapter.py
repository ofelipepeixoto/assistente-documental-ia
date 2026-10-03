# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Exporta snapshots de páginas aprovadas, sem modelos ou ações externas.

O escopo vem do operador. Ele não autentica uma pessoa nem separa tenants no
Store local. O texto e os hashes são lidos do Store, nunca de resposta de LLM.
"""

import sqlite3

from ingestion.contracts import LabError, SCHEMA_VERSION, approved, digest, validate_id


def _evidence_type():
    try:
        from radar_evidence import Evidence, Scope
    except ImportError:
        raise LabError(
            "Exportação opcional indisponível. Instale radar-evidence-kit "
            "na versão indicada em docs/evidencias.md."
        ) from None
    return Evidence, Scope


def _read(store, document_id, *, original=False):
    try:
        return store.original(document_id) if original else store.get(document_id)
    except LabError:
        raise
    except (sqlite3.Error, KeyError, IndexError, TypeError, ValueError, UnicodeError):
        raise LabError("Workspace incompatível ou corrompida; export interrompido.") from None


def _validate_request(tenant_id, project_id, expected_revisions, scope_type):
    for label in (tenant_id, project_id):
        if type(label) is not str or not label.strip():
            raise LabError("Informe tenant e projeto como rótulos do operador.")
        try:
            label.encode("utf-8")
        except UnicodeError:
            raise LabError("Rótulo de escopo com codificação inválida.") from None
    if type(expected_revisions) is not dict or not expected_revisions:
        raise LabError("Informe os documentos e suas revisões atuais.")
    revisions = expected_revisions.copy()
    for document_id, revision in revisions.items():
        validate_id(document_id)
        if type(revision) is not int or revision < 1:
            raise LabError("Versão de documento inválida.")
    try:
        # Enforce the core's identifier and map limits even with no approved
        # pages, rather than waiting for Evidence.from_dict to validate them.
        scope = scope_type(tenant_id=tenant_id, project_id=project_id, current_revisions=revisions)
    except (TypeError, ValueError):
        raise LabError("Escopo incompatível com o contrato de evidências.") from None
    return scope.to_dict()["current_revisions"]


def export_approved_evidence(store, *, tenant_id, project_id, expected_revisions):
    """Retorna ``list[Evidence]`` com páginas completas e revisão vinculada.

    ``expected_revisions`` é um dict ID -> revisão escolhido pelo operador.
    Documentos ausentes, revisão divergente ou original adulterado interrompem
    o export inteiro. Páginas pendentes, rejeitadas ou cujo hash não corresponde
    à revisão ficam fora. Texto maior que o contrato opcional é rejeitado sem
    truncamento. Nenhuma evidência concede autorização para executar ações.

    Uma nova revisão depois do retorno pode tornar este snapshot antigo: o
    consumidor deve comparar com seu Scope atual antes de utilizá-lo.
    """
    Evidence, Scope = _evidence_type()
    revisions = _validate_request(tenant_id, project_id, expected_revisions, Scope)
    result = []
    for document_id, revision in sorted(revisions.items()):
        manifest = _read(store, document_id)
        if (type(manifest) is not dict or type(manifest.get("schema_version")) is not int
                or manifest.get("schema_version") != SCHEMA_VERSION
                or type(manifest.get("revision")) is not int):
            raise LabError("Manifesto incompatível com o contrato documental.")
        if manifest.get("id") != document_id or manifest.get("revision") != revision:
            raise LabError("Documento mudou. Recarregue antes de exportar evidências.")
        # Store.original checks the BLOB against its registered hash. Compare
        # with this manifest too, to detect a change between the separate reads.
        source_sha = manifest.get("source_sha256")
        original = _read(store, document_id, original=True)
        if digest(original) != source_sha:
            raise LabError("Original não corresponde ao snapshot de evidências.")
        try:
            pages = manifest["pages"]
            if type(pages) is not list:
                raise ValueError
            for position, page in enumerate(pages, start=1):
                if (type(page) is not dict or type(page.get("page_number")) is not int
                        or page.get("page_number") != position
                        or type(page.get("text")) is not str
                        or type(page.get("status")) is not str
                        or (page.get("review") is not None and type(page.get("review")) is not dict)):
                    raise ValueError
                if not approved(page, source_sha):
                    continue
                text = page["text"]
                review = page["review"]
                reviewer = review.get("reviewer")
                if type(reviewer) is not str or not reviewer.strip():
                    raise ValueError
                result.append(Evidence.from_dict({
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "revision": revision,
                    "page": position,
                    "start": 0,
                    "end": len(text),
                    "text": text,
                    "source_sha256": source_sha,
                    "text_sha256": review["text_sha256"],
                    "review_status": "approved",
                    "reviewer": reviewer,
                    # A locally entered label is not a verified identity, even
                    # if a hand-edited manifest claims otherwise.
                    "identity_verified": False,
                }))
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise LabError(
                "Página aprovada incompatível com o contrato de evidências. "
                "Confira texto, revisão e limite da biblioteca; nada foi truncado."
            ) from None
        if _read(store, document_id) != manifest:
            raise LabError("Documento mudou durante o export. Recarregue e tente novamente.")
    return result
