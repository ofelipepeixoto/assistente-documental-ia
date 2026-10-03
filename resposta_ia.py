import os
from exemplos.app import buscar


def responder(pergunta):
    trecho = buscar(pergunta)

    if trecho.startswith("Não encontrei"):
        return trecho

    if not os.getenv("OPENAI_API_KEY"):
        return (
            "Chave de API não configurada. A busca encontrou:\n\n"
            + trecho
        )

    return (
        "Geração paga bloqueada neste laboratório: falta integrar autorização "
        "e orçamento persistente com reserva atômica e reconciliação. "
        "A chave configurada não libera chamadas. A busca encontrou:\n\n"
        + trecho
    )


if __name__ == "__main__":
    pergunta = input("Pergunta: ").strip()
    print("\n" + responder(pergunta))
