"""Fluxo HTTP real em loopback: upload → revisão → busca → rejeição."""

import base64
import http.client
import json
import tempfile
import threading
import unittest

from avaliacao.pdf_fixtures import make_pdf
from documentos_web import MAX_REQUEST_BYTES, Server
from ingestion.contracts import LabError
from ingestion.olmocr import import_output
from ingestion.store import Store


class HttpPdfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(self.temporary.name)
        self.server = Server(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def call(self, path, body=None, *, token=True, extra_headers=None, raw=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=30)
        headers = {"X-Lab-Token": self.server.token} if token else {}
        if extra_headers:
            headers.update(extra_headers)
        if body is not None:
            headers.setdefault("Content-Type", "application/json")
            body = body if raw else json.dumps(body)
        connection.request("POST" if body is not None else "GET", path, body, headers)
        response = connection.getresponse()
        data = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(data)
        return status, data, response_headers

    def ingest(self):
        return self.call("/api/ingest", {"name": "ficticio.pdf", "data": base64.b64encode(make_pdf()).decode()})[1]

    def test_end_to_end_http_flow_persists_citation_and_revocation(self):
        status, homepage, _headers = self.call("/", token=False)
        self.assertEqual(status, 200)
        self.assertIn("Conferir e pesquisar", homepage.decode())
        doc = self.ingest()
        self.assertEqual(self.call("/api/search", {"question": "pagamento mensal"})[1], [])
        status, updated, _ = self.call("/api/review", {
            "id": doc["id"], "page_number": 2, "revision": doc["revision"],
            "reviewer": "Pessoa fictícia", "decision": "approved",
        })
        self.assertEqual(status, 200)
        result = self.call("/api/search", {"question": "pagamento mensal"})[1]
        self.assertEqual(result[0]["citation"], "ficticio.pdf — página 2")
        self.assertIn("R$ 1.250,50", result[0]["text"])
        status, data, headers = self.call("/api/original/" + doc["id"])
        self.assertEqual((status, data), (200, make_pdf()))
        self.assertIn("attachment", headers["Content-Disposition"])
        self.call("/api/review", {
            "id": doc["id"], "page_number": 2, "revision": updated["revision"],
            "reviewer": "Pessoa fictícia", "decision": "rejected",
        })
        self.assertEqual(self.call("/api/search", {"question": "pagamento mensal"})[1], [])
        self.assertEqual(Store(self.temporary.name).get(doc["id"])["pages"][1]["review"]["decision"], "rejected")

    def test_missing_token_foreign_origin_and_host_are_denied(self):
        self.assertEqual(self.call("/api/documents", token=False)[0], 403)
        self.assertEqual(self.call("/api/documents", token=False, extra_headers={"X-Lab-Token": "é" * 64})[0], 403)
        self.assertEqual(self.call("/api/search", {"question": "pagamento"}, token=False)[0], 403)
        self.assertEqual(self.call("/", token=False, extra_headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.call("/api/search", {"question": "pagamento"}, extra_headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_stale_review_returns_error_without_mutation(self):
        doc = self.ingest()
        body = {"id": doc["id"], "page_number": 1, "revision": 1, "reviewer": "Pessoa", "decision": "approved"}
        self.assertEqual(self.call("/api/review", body)[0], 200)
        status, error, _ = self.call("/api/review", body)
        self.assertEqual(status, 400)
        self.assertIn("mudou", error["error"])

    def test_invalid_reviewer_unicode_returns_error_without_mutation(self):
        doc = self.ingest()
        for reviewer in ("\ud800", "\udfff"):
            with self.subTest(reviewer=ascii(reviewer)):
                status, error, _ = self.call("/api/review", {
                    "id": doc["id"], "page_number": 1, "revision": doc["revision"],
                    "reviewer": reviewer, "decision": "approved",
                })
                self.assertEqual(status, 400)
                self.assertIsInstance(error["error"], str)
                persisted = self.store.get(doc["id"])
                self.assertEqual(persisted["revision"], doc["revision"])
                self.assertEqual(persisted["events"], doc["events"])
                self.assertEqual(persisted, doc)
                status, reloaded, _ = self.call("/api/documents/" + doc["id"])
                self.assertEqual((status, reloaded), (200, doc))

    def test_invalid_ocr_version_unicode_preserves_readable_manifest(self):
        doc = self.ingest()
        text, spans = "", []
        for page in doc["pages"]:
            start = len(text)
            text += page["text"]
            spans.append([start, len(text), page["page_number"]])
        for version in ("\ud800", "\udfff"):
            with self.subTest(version=ascii(version)):
                record = {
                    "source": "olmocr", "text": text,
                    "metadata": {"Source-File": "origem.pdf", "pdf-total-pages": len(spans),
                                 "total-fallback-pages": 0, "olmocr-version": version},
                    "attributes": {"pdf_page_numbers": spans},
                }
                with self.assertRaisesRegex(LabError, "Saída OCR inválida"):
                    import_output(self.store, doc["id"], json.dumps(record).encode(),
                                  expected_revision=doc["revision"], source_sha256=doc["source_sha256"],
                                  source_file="origem.pdf", model="modelo", model_revision="a" * 40)
                persisted = self.store.get(doc["id"])
                self.assertEqual(persisted["revision"], doc["revision"])
                self.assertEqual(persisted["events"], doc["events"])
                self.assertEqual(persisted, doc)
                status, reloaded, _ = self.call("/api/documents/" + doc["id"])
                self.assertEqual((status, reloaded), (200, doc))

    def test_size_type_base64_path_and_busy_are_bounded(self):
        self.assertEqual(self.call("/api/ingest", {}, extra_headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})[0], 413)
        self.assertEqual(self.call("/api/ingest", {}, extra_headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("/api/ingest", {"name": "x.pdf", "data": "not base64!"})[0], 400)
        self.assertEqual(self.call("/api/search", [], raw=False)[0], 400)
        self.assertEqual(self.call("/api/search", "[" * 2000 + "]" * 2000, raw=True)[0], 400)
        self.assertEqual(self.call("/api/documents/../../etc/passwd")[0], 400)
        self.server.work.acquire()
        try:
            self.assertEqual(self.call("/api/search", {"question": "pagamento"})[0], 429)
        finally:
            self.server.work.release()

    def test_ui_uses_text_content_and_security_headers(self):
        status, html, headers = self.call("/", token=False)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        content = html.decode()
        self.assertNotIn("innerHTML", content)
        self.assertIn("text.textContent=match.text", content)
        self.assertIn("text.value=page.text", content)
        self.assertNotIn("cdn.", content)


if __name__ == "__main__":
    unittest.main()
