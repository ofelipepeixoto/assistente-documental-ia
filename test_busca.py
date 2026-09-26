import unittest

from exemplos.app import buscar


class TestBusca(unittest.TestCase):
    def test_encontra_prazo(self):
        resultado = buscar("Qual é o prazo?")
        self.assertIn("Cláusula 2", resultado)
        self.assertIn("contrato_ficticio.txt", resultado)


    def test_encontra_rescisao(self):
        resultado = buscar("Qual é a antecedência para rescindir?")
        self.assertIn("Cláusula 4", resultado)


    def test_nao_inventa_resposta(self):
        resultado = buscar("Qual é a cor do logotipo?")
        self.assertIn("Não encontrei", resultado)

    def test_encontra_pagamento(self):
        resultado = buscar("Qual é o pagamento mensal?")
        self.assertIn("Cláusula 3", resultado)
        self.assertIn("R$ 500", resultado)


if __name__ == "__main__":
    unittest.main()
