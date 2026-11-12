# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""CLI opcional de snapshots locais. Nenhum modelo, rede ou ação externa."""

import argparse
import json
from pathlib import Path
import sqlite3

from ingestion.contracts import LabError, validate_id
from ingestion.evidence_adapter import export_approved_evidence
from ingestion.store import Store


def document_revision(value):
    try:
        document_id, raw_revision = value.rsplit(":", 1)
        validate_id(document_id)
        revision = int(raw_revision)
        if revision < 1 or str(revision) != raw_revision:
            raise ValueError
    except (LabError, ValueError):
        raise argparse.ArgumentTypeError("Use ID_SHA256:REVISAO, com revisão inteira positiva.") from None
    return document_id, revision


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Exporta texto integral de páginas aprovadas para stdout, sem autenticar revisores ou executar ações.",
    )
    parser.add_argument("--pasta", default=".documentos", help="Workspace local já existente")
    parser.add_argument("--tenant", required=True, help="Rótulo de escopo escolhido pelo operador; não é login")
    parser.add_argument("--projeto", required=True, help="Rótulo de projeto escolhido pelo operador")
    parser.add_argument("--trechos", action="store_true",
                        help="Exportar referências a janelas de 512 caracteres, sobreposição 64")
    parser.add_argument("--documento", type=document_revision, action="append", required=True,
                        metavar="ID:REVISAO", help="Documento/revisão selecionado pelo operador; pode repetir")
    args = parser.parse_args(argv)
    revisions = {}
    for document_id, revision in args.documento:
        if document_id in revisions:
            parser.error("Não repita o mesmo documento.")
        revisions[document_id] = revision
    try:
        if not (Path(args.pasta) / "lab.sqlite3").is_file():
            raise LabError("Workspace documental não encontrado; nenhum banco foi criado.")
        store = Store(args.pasta)
        if args.trechos:
            from ingestion.passages import export_passage_snapshot
            payload = export_passage_snapshot(
                store, tenant_id=args.tenant, project_id=args.projeto,
                expected_revisions=revisions,
            )
        else:
            evidence = export_approved_evidence(
                store, tenant_id=args.tenant, project_id=args.projeto,
                expected_revisions=revisions,
            )
            from radar_evidence import Scope

            scope = Scope(tenant_id=args.tenant, project_id=args.projeto, current_revisions=revisions)
            payload = {
                "schema_version": 1,
                "kind": "documental_evidence_snapshot",
                "scope": scope.to_dict(),
                "evidence": [{"evidence_id": item.evidence_id, "record": item.to_dict()} for item in evidence],
            }
    except (LabError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.exit(1, f"Não foi possível exportar: {exc if isinstance(exc, LabError) else 'workspace indisponível'}\n")
    if args.trechos:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), end="")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
