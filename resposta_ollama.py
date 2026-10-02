"""CLI separada e opcional; o caminho OpenAI de resposta_ia.py permanece independente."""

import argparse
import json
from pathlib import Path

from exemplos.app import buscar
from ollama_provider import OllamaConfig, OllamaError, generate

NO_EVIDENCE = "Não encontrei evidência aprovada que sustente a pergunta."


def retrieve(question, workspace=None):
    if workspace is None:
        return buscar(question)
    # Leitura do workspace já revisado; não executa ingestão nem aprova páginas.
    from ingestion.search import search
    from ingestion.store import Store

    if not (Path(workspace) / "lab.sqlite3").is_file():
        raise OllamaError("Workspace PDF existente não encontrado; faça ingestão e revisão primeiro.")
    results = search(Store(workspace), question)
    if not results:
        return NO_EVIDENCE
    return json.dumps({"fontes_recuperadas": results}, ensure_ascii=False, indent=2)


def responder(pergunta, *, provider=None, model=None, workspace=None,
              endpoint="http://127.0.0.1:11434", timeout_seconds=20):
    if not isinstance(pergunta, str) or not pergunta.strip() or len(pergunta) > 500:
        raise OllamaError("Informe uma pergunta de até 500 caracteres.")
    evidence = retrieve(pergunta, workspace)
    if evidence.startswith("Não encontrei"):
        return evidence  # Abstention determinística: nenhum cliente/HTTP é criado.
    if provider is None:
        if model is not None:
            raise OllamaError("Informe também --provider ollama para usar um modelo.")
        return evidence
    if provider != "ollama":
        raise OllamaError("Provider não permitido; escolha ollama explicitamente.")
    config = OllamaConfig(model=model, endpoint=endpoint, timeout_seconds=timeout_seconds)
    draft = generate(pergunta, evidence, config)
    return (
        f"Rascunho probabilístico para revisão humana:\n{draft}\n\n"
        "Evidências recuperadas (não validam cada afirmação do rascunho):\n"
        f"{evidence}"
    )


def main():
    parser = argparse.ArgumentParser(description="Busca local; Ollama somente com opt-in explícito.")
    parser.add_argument("pergunta")
    parser.add_argument("--provider", choices=["ollama"])
    parser.add_argument("--model", help="Nome local exato; não baixa ou instala modelos.")
    parser.add_argument("--workspace", help="Workspace PDF local já revisado; opcional.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    if args.model is not None and args.provider is None:
        parser.error("--model exige --provider ollama.")
    if args.provider == "ollama" and args.model is None:
        parser.error("--provider ollama exige --model.")
    try:
        print(responder(
            args.pergunta, provider=args.provider, model=args.model, workspace=args.workspace,
            endpoint=args.endpoint, timeout_seconds=args.timeout,
        ))
    except (OllamaError, ValueError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
