import builtins
import os
import unittest
from unittest.mock import patch

from resposta_ia import responder


class TestRespostaSemApi(unittest.TestCase):
    def test_sem_chave_exibe_trecho_e_fonte_sem_importar_openai(self):
        original_import = builtins.__import__

        def impedir_openai(name, *args, **kwargs):
            if name == "openai":
                raise AssertionError("Não deve importar openai sem chave")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch(
            "builtins.__import__", side_effect=impedir_openai
        ):
            resultado = responder("Qual é o prazo?")

        self.assertIn("Chave de API não configurada", resultado)
        self.assertIn("contrato_ficticio.txt", resultado)
        self.assertIn("Cláusula 2", resultado)
        self.assertIn("12 meses", resultado)

    def test_sem_trecho_nao_chama_api_mesmo_com_chave(self):
        original_import = builtins.__import__

        def impedir_openai(name, *args, **kwargs):
            if name == "openai":
                raise AssertionError("Não deve importar openai sem trecho")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "chave-ficticia"}), patch(
            "builtins.__import__", side_effect=impedir_openai
        ):
            resultado = responder("Qual é a cor do logotipo?")

        self.assertIn("Não encontrei", resultado)

    def test_chave_nao_libera_custo_ou_envio_sem_controle_persistente(self):
        original_import = builtins.__import__

        def impedir_openai(name, *args, **kwargs):
            if name == "openai":
                raise AssertionError("Budget ausente: não importar ou chamar SDK")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "chave-ficticia"}), patch(
            "builtins.__import__", side_effect=impedir_openai
        ):
            resultado = responder("Qual é o prazo?")
        self.assertIn("Geração paga bloqueada", resultado)
        self.assertIn("reserva atômica", resultado)
        self.assertIn("contrato_ficticio.txt", resultado)


if __name__ == "__main__":
    unittest.main()
