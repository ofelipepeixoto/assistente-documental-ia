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

    from openai import OpenAI

    resposta = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        store=False,
        instructions=(
            "Você prepara um rascunho para revisão humana. "
            "Responda somente com base no trecho fornecido. "
            "Se ele não sustentar a resposta, diga que não há "
            "informação suficiente. Não invente fatos nem apresente "
            "o texto como aconselhamento jurídico."
        ),
        input=f"Pergunta: {pergunta}\n\n{trecho}",
    )

    return (
        f"Rascunho para revisão humana:\n{resposta.output_text}\n\n"
        f"{trecho}"
    )


if __name__ == "__main__":
    pergunta = input("Pergunta: ").strip()
    print("\n" + responder(pergunta))
