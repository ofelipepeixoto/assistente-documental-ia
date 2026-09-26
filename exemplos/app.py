from pathlib import Path
import re
import unicodedata

PASTA_DOCUMENTOS = Path("exemplos")
PALAVRAS_COMUNS = {
    "a", "as", "o", "os", "de", "do", "da", "dos", "das",
    "e", "em", "um", "uma", "qual", "quais", "com", "para",
    "posso", "contrato", "clausula", "quantos", "qual"
}


def palavras(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return {
        palavra
        for palavra in re.findall(r"[a-z0-9]+", texto)
        if palavra not in PALAVRAS_COMUNS and len(palavra) > 2
    }


def buscar(pergunta):
    termos = palavras(pergunta)
    resultados = []

    for caminho in PASTA_DOCUMENTOS.glob("*.txt"):
        conteudo = caminho.read_text(encoding="utf-8")
        secoes = re.split(r"(?=Cláusula \d+ —)", conteudo)

        for secao in secoes:
            correspondencias = termos & palavras(secao)
            if correspondencias:
                resultados.append(
                    (len(correspondencias), caminho.name, secao.strip())
                )

    if not resultados:
        return "Não encontrei um trecho relacionado nos documentos disponíveis."

    resultados.sort(key=lambda item: item[0], reverse=True)
    _, arquivo, trecho = resultados[0]
    return f"Fonte: {arquivo}\n\nTrecho encontrado:\n{trecho}"


if __name__ == "__main__":
    pergunta = input("Pergunta sobre os documentos: ").strip()
    print("\n" + buscar(pergunta))
