import unittest

from avaliar import avaliar
from demo_web import pagina


class TestAvaliacaoEDemo(unittest.TestCase):
    def test_casos_cobrem_clausulas_e_ausencia(self):
        resultados = avaliar()
        self.assertEqual(len(resultados), 7)
        self.assertEqual({r["esperado"] for r in resultados},
                         {None, "Cláusula 1", "Cláusula 2", "Cláusula 3", "Cláusula 4"})
        self.assertEqual(sum(r["acertou"] for r in resultados), 5)

    def test_demo_escapa_entrada_e_saida(self):
        html = pagina("<script>alert(1)</script>", "<b>documento</b>")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>documento</b>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;b&gt;documento&lt;/b&gt;", html)


if __name__ == "__main__":
    unittest.main()
