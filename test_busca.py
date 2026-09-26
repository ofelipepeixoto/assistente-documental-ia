from exemplos.app import buscar


def test_encontra_prazo():
    resultado = buscar("Qual é o prazo?")
    assert "Cláusula 2" in resultado
    assert "contrato_ficticio.txt" in resultado


def test_encontra_rescisao():
    resultado = buscar("Qual é a antecedência para rescindir?")
    assert "Cláusula 4" in resultado


def test_nao_inventa_resposta():
    resultado = buscar("Qual é a cor do logotipo?")
    assert "Não encontrei" in resultado


if __name__ == "__main__":
    test_encontra_prazo()
    test_encontra_rescisao()
    test_nao_inventa_resposta()
    print("3 verificações passaram.")
