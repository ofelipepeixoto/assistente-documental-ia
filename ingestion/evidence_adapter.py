# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Exporta snapshots de páginas aprovadas, sem modelos ou ações externas.

O escopo vem do operador. Ele não autentica uma pessoa nem separa tenants no
Store local. O texto e os hashes são lidos do Store, nunca de resposta de LLM.
"""

import json

from ingestion.contracts import LabError, SCHEMA_VERSION, approved, validate_id


def _evidence_type():
    try:
        from radar_evidence import Evidence, Scope
    except ImportError:
        raise LabError(
            "Exportação opcional indisponível. Instale radar-evidence-kit "
            "na versão indicada em docs/evidencias.md."
        ) from None
    return Evidence, Scope


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
    snapshots = store.snapshots(list(revisions))
    result = []
    for document_id, revision in sorted(revisions.items()):
        manifest = snapshots[document_id]
        if (type(manifest) is not dict or type(manifest.get("schema_version")) is not int
                or manifest.get("schema_version") != SCHEMA_VERSION
                or type(manifest.get("revision")) is not int):
            raise LabError("Manifesto incompatível com o contrato documental.")
        if manifest.get("id") != document_id or manifest.get("revision") != revision:
            raise LabError("Documento mudou. Recarregue antes de exportar evidências.")
        # Store.snapshots binds the original BLOB and every selected manifest
        # to one SQLite read transaction, including multi-document exports.
        source_sha = manifest.get("source_sha256")
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
    return result


def validate_local_snapshot(store, payload, *, tenant_id, project_id, document_ids):
    """Compara um export com a workspace atual para leitura de laboratório.

    O consumidor escolhe tenant/projeto e documentos permitidos pela sua própria
    configuração, nunca pelos rótulos do JSON recebido. A revisão corrente e os
    registros aprovados vêm do Store. Não autentica pessoas, não transforma um
    rótulo local em identidade verificada e não autoriza efeitos externos.
    Uma mudança depois do retorno ainda exige nova verificação pelo consumidor.
    """
    if (type(payload) is not dict
            or set(payload) != {"schema_version", "kind", "scope", "evidence"}
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or payload.get("kind") != "documental_evidence_snapshot"):
        raise LabError("Snapshot documental inválido.")
    current = store.snapshots(document_ids)
    revisions = {key: manifest.get("revision") for key, manifest in current.items()}
    fresh = export_approved_evidence(
        store, tenant_id=tenant_id, project_id=project_id,
        expected_revisions=revisions,
    )
    _, Scope = _evidence_type()
    scope = Scope(tenant_id=tenant_id, project_id=project_id, current_revisions=revisions)
    expected_records = [
        {"evidence_id": item.evidence_id, "record": item.to_dict()} for item in fresh
    ]
    try:
        received = json.dumps([payload["scope"], payload["evidence"]], sort_keys=True, allow_nan=False)
        expected = json.dumps([scope.to_dict(), expected_records], sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise LabError("Snapshot documental inválido.") from None
    if received != expected:
        raise LabError("Snapshot mudou, diverge do escopo ou não corresponde às revisões atuais.")
    return fresh
