"""HTTP mock e servidor fictício loopback; nenhum Ollama/modelo/API real é usado."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from avaliacao.pdf_fixtures import make_pdf
from ingestion.store import Store
from ollama_provider import (
    DEFAULT_ENDPOINT, MAX_RESPONSE_BYTES, OllamaConfig, OllamaError, generate, local_address,
)
from resposta_ollama import responder


def response_data(content="A vigência é de 12 meses.", **extra):
    return json.dumps({
        "done": True, "message": {"role": "assistant", "content": content}, **extra,
    }).encode()


class Response:
    def __init__(self, body, status=200, content_type="application/json"):
        self.status = status
        self.body = io.BytesIO(body)
        self.content_type = content_type

    def getheader(self, name, default=""):
        return self.content_type if name == "Content-Type" else default

    def read1(self, size):
        return self.body.read(size)

    def close(self):
        self.body.close()


class ProviderTests(unittest.TestCase):
    def call(self, body=None, **response_options):
        response = Response(response_data() if body is None else body, **response_options)
        connection = MagicMock()
        connection.sock = MagicMock()
        connection.getresponse.return_value = response
        with patch("ollama_provider.http.client.HTTPConnection", return_value=connection) as factory:
            result = generate("Qual é o prazo?", "Fonte: teste.txt\nVigência 12 meses.", OllamaConfig("modelo-teste:1b"))
        return result, connection, factory

    def test_success_is_one_bounded_call_and_no_tools(self):
        result, connection, factory = self.call()
        self.assertIn("12 meses", result)
        factory.assert_called_once_with("127.0.0.1", 11434, timeout=20)
        connection.request.assert_called_once()
        args, kwargs = connection.request.call_args
        self.assertEqual(args, ("POST", "/api/chat"))
        body = json.loads(kwargs["body"])
        self.assertFalse(body["stream"])
        self.assertEqual(body["keep_alive"], 0)
        self.assertEqual(body["options"]["num_predict"], 512)
        self.assertEqual(body["options"]["num_ctx"], 4096)
        self.assertNotIn("tools", body)
        self.assertIn("dados não confiáveis", body["messages"][0]["content"])
        connection.close.assert_called_once()

    def test_http_failure_and_redirects_are_not_followed(self):
        for status in [301, 302, 307, 308, 401, 404, 500]:
            with self.subTest(status=status), self.assertRaisesRegex(OllamaError, str(status)):
                self.call(status=status)

    def test_response_is_closed_on_success_http_error_and_invalid_body(self):
        for status, body in [(200, response_data()), (307, b""), (200, b"not-json")]:
            response = Response(body, status=status)
            connection = MagicMock()
            connection.sock = MagicMock()
            connection.getresponse.return_value = response
            with self.subTest(status=status, body=body[:20]), patch(
                "ollama_provider.http.client.HTTPConnection", return_value=connection,
            ):
                if status == 200 and body != b"not-json":
                    generate("prazo", "Fonte: 12 meses", OllamaConfig("teste"))
                else:
                    with self.assertRaises(OllamaError):
                        generate("prazo", "Fonte: 12 meses", OllamaConfig("teste"))
                self.assertTrue(response.body.closed)
                connection.close.assert_called_once()

    def test_bad_content_type_malformed_json_and_shape_fail_closed(self):
        invalid = [
            b"secret internal body", b"[]", b"null", b"\xff",
            b"[" * 1100 + b"]" * 1100,
            b'{"done":true,"message":{"role":"assistant","content":"\\ud800"}}',
            response_data(done=False),
            json.dumps({"done": True, "message": {"role": "user", "content": "x"}}).encode(),
            json.dumps({"done": True, "message": {"role": "assistant", "content": {}}}).encode(),
            response_data(""),
            json.dumps({"done": True, "message": {
                "role": "assistant", "content": "x", "tool_calls": [{"name": "execute"}],
            }}).encode(),
        ]
        for body in invalid:
            with self.subTest(body=body[:30]), self.assertRaises(OllamaError) as caught:
                self.call(body)
            self.assertNotIn("secret internal body", str(caught.exception))
        with self.assertRaisesRegex(OllamaError, "JSON"):
            self.call(content_type="text/html")

    def test_response_and_output_have_bounds(self):
        with self.assertRaisesRegex(OllamaError, "64 KiB"):
            self.call(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(OllamaError, "Conteúdo"):
            self.call(response_data("x" * 16_001))

    def test_timeout_or_connection_error_does_not_retry_or_leak(self):
        for error in [socket.timeout("secret"), ConnectionRefusedError("secret")]:
            connection = MagicMock()
            connection.connect.side_effect = error
            with patch("ollama_provider.http.client.HTTPConnection", return_value=connection) as factory:
                with self.assertRaises(OllamaError) as caught:
                    generate("prazo?", "Fonte: teste\n12 meses", OllamaConfig("teste"))
            factory.assert_called_once()
            connection.connect.assert_called_once()
            connection.close.assert_called_once()
            self.assertNotIn("secret", str(caught.exception))

    def test_only_literal_loopback_and_base_path_are_allowed(self):
        self.assertEqual(local_address(DEFAULT_ENDPOINT), ("127.0.0.1", 11434))
        self.assertEqual(local_address("http://[::1]:1234/"), ("::1", 1234))
        urls = [
            "http://localhost:11434", "http://example.com", "http://10.0.0.1",
            "http://169.254.169.254", "https://127.0.0.1:11434",
            "http://127.0.0.1:0", "http://127.0.0.1:65536",
            "http://user:password@127.0.0.1", "http://127.0.0.1/api/delete",
            "http://127.0.0.1?model=x", "http://127.0.0.1#fragment",
            "http://[::ffff:127.0.0.1]", "http://127.0.0.1\\evil",
            "http://127.0.0.1\n", " http://127.0.0.1", "http://[::1",
        ]
        with patch("ollama_provider.http.client.HTTPConnection") as factory:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(OllamaError):
                    OllamaConfig("teste", endpoint=url)
        factory.assert_not_called()

    def test_model_timeout_and_token_config_are_explicit_bounded(self):
        for model in [None, "", "modelo cloud", "teste:cloud", "teste-cloud", "x" * 129]:
            with self.subTest(model=model), self.assertRaises(OllamaError):
                OllamaConfig(model)
        for timeout in [0, -1, 31, True, float("nan"), float("inf")]:
            with self.subTest(timeout=timeout), self.assertRaises(OllamaError):
                OllamaConfig("teste", timeout_seconds=timeout)
        for limit in [0, 513, True]:
            with self.subTest(limit=limit), self.assertRaises(OllamaError):
                OllamaConfig("teste", max_new_tokens=limit)

    def test_oversized_request_never_opens_connection(self):
        with patch("ollama_provider.http.client.HTTPConnection") as factory:
            for question, evidence in [
                ("x" * 501, "fonte"), ("prazo", "x" * 8_001), ("prazo", "😀" * 8_000),
            ]:
                with self.subTest(size=len(evidence)), self.assertRaises(OllamaError):
                    generate(question, evidence, OllamaConfig("teste"))
        factory.assert_not_called()

    def test_deadline_cuts_off_slow_body_even_with_connection_close(self):
        class SlowBody(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                self.end_headers()
                for _ in range(20):
                    try:
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.06)
                    except OSError:
                        break

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowBody)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(OllamaError, "prazo"):
                generate("prazo", "Fonte: 12 meses", OllamaConfig(
                    "teste", endpoint=f"http://127.0.0.1:{server.server_port}", timeout_seconds=0.15,
                ))
            self.assertLess(time.monotonic() - started, 0.8)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class AnswerTests(unittest.TestCase):
    def test_default_stays_lexical_even_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "not-a-key"}), patch(
            "resposta_ollama.generate",
        ) as llm, patch("ollama_provider.http.client.HTTPConnection") as http:
            result = responder("Qual é o prazo?")
        self.assertIn("Fonte:", result)
        self.assertIn("12 meses", result)
        llm.assert_not_called()
        http.assert_not_called()

    def test_abstention_is_zero_llm_calls_even_with_ollama_opt_in(self):
        with patch("resposta_ollama.generate") as llm, patch(
            "ollama_provider.http.client.HTTPConnection",
        ) as http:
            result = responder("Qual é a cor do logotipo?", provider="ollama", model="teste")
        self.assertIn("Não encontrei", result)
        llm.assert_not_called()
        http.assert_not_called()

    def test_provider_and_model_are_both_required_for_generation(self):
        for kwargs in [{"model": "teste"}, {"provider": "ollama"}, {"provider": "other", "model": "teste"}]:
            with self.subTest(kwargs=kwargs), patch("resposta_ollama.generate") as llm:
                with self.assertRaises(OllamaError):
                    responder("Qual é o prazo?", **kwargs)
                llm.assert_not_called()

    def test_generated_answer_is_a_draft_and_original_source_is_preserved(self):
        with patch("resposta_ollama.generate", return_value="Não há informação suficiente."):
            result = responder("Qual é o prazo?", provider="ollama", model="teste")
        self.assertIn("Rascunho probabilístico", result)
        self.assertIn("Não há informação suficiente", result)
        self.assertIn("Fonte: contrato_ficticio.txt", result)
        self.assertIn("não validam cada afirmação", result)

    def test_pdf_only_approved_pages_supply_citation_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            document = store.ingest(make_pdf(), "ficticio.pdf")
            with patch("resposta_ollama.generate") as llm:
                result = responder("vigência", workspace=directory, provider="ollama", model="teste")
                self.assertIn("Não encontrei", result)
                llm.assert_not_called()
            reviewed = store.review(document["id"], 1, document["revision"], "Pessoa", "approved")
            with patch("resposta_ollama.generate", return_value="Consulte a evidência.") as llm:
                result = responder("vigência", workspace=directory, provider="ollama", model="teste")
            self.assertIn("ficticio.pdf — página 1", result)
            self.assertIn(document["source_sha256"], result)
            self.assertIn('"document_revision": ' + str(reviewed["revision"]), result)
            llm.assert_called_once()

    def test_missing_workspace_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent"
            with self.assertRaises(OllamaError):
                responder("vigência", workspace=str(path))
            self.assertFalse(path.exists())

    def test_cli_default_and_invalid_opt_in_are_offline(self):
        root = Path(__file__).resolve().parent
        result = subprocess.run(
            [sys.executable, "resposta_ollama.py", "Qual é o prazo?"], cwd=root,
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("contrato_ficticio.txt", result.stdout)
        result = subprocess.run(
            [sys.executable, "resposta_ollama.py", "prazo", "--provider", "ollama"], cwd=root,
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("exige --model", result.stderr)


if __name__ == "__main__":
    unittest.main()
