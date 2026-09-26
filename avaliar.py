"""Mede recuperação de cláusulas em perguntas fictícias, sem usar uma API."""

import json
from pathlib import Path

from exemplos.app import buscar

CASOS = Path(__file__).resolve().parent / "avaliacao" / "casos.json"


def avaliar(casos=None):
    if casos is None:
        casos = json.loads(CASOS.read_text(encoding="utf-8"))
    resultados = []
    for caso in casos:
        resposta = buscar(caso["pergunta"])
        esperado = caso["clausula_esperada"]
        encontrado = next((f"Cláusula {n}" for n in range(1, 5)
                          if f"Cláusula {n}" in resposta), None)
        resultados.append({"pergunta": caso["pergunta"], "esperado": esperado,
                           "encontrado": encontrado, "acertou": esperado == encontrado})
    return resultados


if __name__ == "__main__":
    resultados = avaliar()
    for item in resultados:
        status = "OK" if item["acertou"] else "ERRO"
        print(f"{status}: {item['pergunta']} | esperado={item['esperado']} | encontrado={item['encontrado']}")
    acertos = sum(item["acertou"] for item in resultados)
    print(f"Acertos: {acertos}/{len(resultados)}")
