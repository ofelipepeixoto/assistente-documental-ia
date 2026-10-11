# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Trechos locais com vínculo integral; não é endpoint nem autenticador."""

import json

from ingestion.contracts import LabError
from ingestion.evidence_adapter import export_approved_evidence

MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_PARENTS = 256
MAX_CITATIONS = 2048
FIELDS = {"schema_version", "kind", "scope", "window", "evidence", "citations"}


def _kit():
    try:
        from radar_evidence import Citation, Scope, resolve_citation, split_evidence
    except ImportError:
        raise LabError("Instale a versão fixada em requirements-evidence.txt para exportar trechos.") from None
    return Citation, Scope, resolve_citation, split_evidence


def _encode(payload):
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise LabError("Snapshot de trechos inválido.") from None
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise LabError("Snapshot excede 2 MiB; selecione menos documentos.")
    return encoded


def _shape(payload):
    if (type(payload) is not dict or set(payload) != FIELDS
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1
            or payload.get("kind") != "documental_passage_snapshot"
            or type(payload.get("evidence")) is not list
            or len(payload["evidence"]) > MAX_PARENTS
            or type(payload.get("citations")) is not list
            or len(payload["citations"]) > MAX_CITATIONS):
        raise LabError("Formato ou limites do snapshot de trechos inválidos.")


def load_passage_snapshot(stream):
    """Lê um stream binário local, limitado antes do parsing; não aceita URLs."""
    chunks = []
    size = 0
    while True:
        chunk = stream.read(min(65536, MAX_SNAPSHOT_BYTES + 1 - size))
        if type(chunk) is not bytes:
            raise LabError("Abra o snapshot como arquivo binário local.")
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_SNAPSHOT_BYTES:
            raise LabError("Snapshot excede 2 MiB.")
        chunks.append(chunk)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("non-finite number")

    try:
        result = json.loads(b"".join(chunks).decode("utf-8"),
                            object_pairs_hook=pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise LabError("JSON de trechos inválido.") from None
    _shape(result)
    _encode(result)
    return result


def export_passage_snapshot(store, *, tenant_id, project_id, expected_revisions,
                            max_chars=512, overlap=64):
    """Export completo ou erro; páginas pendentes/rejeitadas não são incluídas."""
    _, Scope, _, split = _kit()
    # Validate options even if no page has been approved.
    if (type(max_chars) is not int or not 64 <= max_chars <= 4096
            or type(overlap) is not int or not 0 <= overlap <= max_chars // 2):
        raise LabError("Janela deve ter 64–4096 caracteres e sobreposição até metade.")
    parents = export_approved_evidence(
        store, tenant_id=tenant_id, project_id=project_id,
        expected_revisions=expected_revisions,
    )
    if len(parents) > MAX_PARENTS:
        raise LabError("Export excede 256 páginas aprovadas.")
    citations = []
    for parent in parents:
        citations.extend(item.to_dict() for item in split(parent, max_chars=max_chars, overlap=overlap))
        if len(citations) > MAX_CITATIONS:
            raise LabError("Export excede 2048 trechos; selecione menos documentos.")
    payload = {
        "schema_version": 1, "kind": "documental_passage_snapshot",
        "scope": Scope(tenant_id, project_id, expected_revisions).to_dict(),
        "window": {"max_chars": max_chars, "overlap": overlap},
        "evidence": [{"evidence_id": item.evidence_id, "record": item.to_dict()} for item in parents],
        "citations": citations,
    }
    _encode(payload)
    return payload


def validate_passage_snapshot(store, payload, *, tenant_id, project_id,
                              document_ids, max_chars=512, overlap=64):
    """Revalida no Store atual e retorna Evidence por trecho para pesquisa local.

    Tenant, projeto, documentos e janelas vêm da configuração do consumidor.
    Não confiar nesses valores no JSON recebido. Uma alteração posterior ao
    retorno exige nova verificação antes de exibir ou utilizar os trechos.
    """
    _shape(payload)
    received = _encode(payload)
    current = store.snapshots(document_ids)
    revisions = {key: manifest.get("revision") for key, manifest in current.items()}
    fresh = export_passage_snapshot(
        store, tenant_id=tenant_id, project_id=project_id, expected_revisions=revisions,
        max_chars=max_chars, overlap=overlap,
    )
    if received != _encode(fresh):
        raise LabError("Snapshot diverge do escopo, texto, revisão ou janela atuais.")
    Citation, Scope, resolve, _ = _kit()
    from radar_evidence import Evidence

    parents = {item["evidence_id"]: Evidence.from_dict(item["record"]) for item in fresh["evidence"]}
    scope = Scope(tenant_id, project_id, revisions)
    return [resolve(Citation.from_dict(item), parents[item["parent_evidence_id"]],
                    scope, require_verified_review=False) for item in fresh["citations"]]
