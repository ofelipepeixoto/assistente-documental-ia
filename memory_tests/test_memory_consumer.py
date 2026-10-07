# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from avaliacao.pdf_fixtures import make_pdf
from ingestion.project_memory import ProjectMemory
from ingestion.store import Store
from memoria_web import MAX_BODY, Server


class Fixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.doc = self.store.ingest(make_pdf(), "fixture.pdf")
        self.doc = self.store.review(self.doc["id"], 2, self.doc["revision"], "source-reviewer", "approved")
        self.now = 100
        self.consumer = ProjectMemory(self.store, clock=lambda: self.now)

    def proposal(self, text="Pagamento mensal exige conferência."):
        return self.consumer.apply("propose", dict(note_id="pagamento", text=text, proposer="author",
                                                   source_ids=[self.consumer.state()["sources"][0]["id"]]))

    def approve(self, draft):
        return self.consumer.apply("approve", dict(note_id=draft["note_id"], proposal_hash=draft["proposal_hash"],
                                                   reviewer="reviewer"))


class ConsumerTests(Fixture, unittest.TestCase):

    def test_restart_preserves_unverified_review_and_original_sources(self):
        draft = self.proposal()
        self.assertEqual(self.consumer.state()["active"], [])
        self.approve(draft)
        new = ProjectMemory(Store(self.tmp.name), clock=lambda: self.now)
        self.assertFalse(new.state()["active"][0]["identity_verified"])
        evidence = new.source(draft["source_ids"][0])
        self.assertEqual(evidence["source_sha256"], self.doc["source_sha256"])
        self.assertIn("1.250,50", evidence["text"])

    def test_corrected_proposal_blocks_old_review(self):
        old = self.proposal()
        latest = self.proposal("Correção da nota.")
        with self.assertRaises(ValueError):
            self.approve(old)
        self.approve(latest)
        self.assertEqual(self.consumer.state()["active"][0]["text"], "Correção da nota.")

    def test_rejection_does_not_promote(self):
        draft = self.proposal()
        self.consumer.apply("reject", dict(note_id=draft["note_id"], proposal_hash=draft["proposal_hash"], reviewer="reviewer"))
        self.assertEqual(self.consumer.state()["active"], [])
        self.assertEqual(self.consumer.state()["pending"], [])

    def test_source_correction_or_rejection_revokes_memory(self):
        draft = self.proposal()
        self.approve(draft)
        self.doc = self.store.review(self.doc["id"], 2, self.doc["revision"], "source-reviewer", "approved",
                                     corrected_text="Pagamento mensal: R$ 1.200,00.")
        self.assertEqual(self.consumer.state()["active"], [])
        draft = self.proposal()
        self.store.review(self.doc["id"], 2, self.doc["revision"], "source-reviewer", "rejected")
        with self.assertRaises(ValueError):
            self.approve(draft)

    def test_backend_rejects_client_scope_identity_status_and_sources(self):
        base = dict(note_id="n", text="nota", proposer="author", source_ids=[self.consumer.state()["sources"][0]["id"]])
        for field, value in (("tenant_id", "other"), ("identity_verified", True), ("status", "approved")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consumer.apply("propose", dict(base, **{field: value}))
        with self.assertRaises(ValueError):
            self.consumer.apply("propose", dict(base, source_ids=["a" * 64]))
        other = ProjectMemory(self.store, tenant_id="other", clock=lambda: self.now)
        self.approve(self.proposal())
        self.assertEqual(other.state()["active"], [])

    def test_source_original_tamper_fails_closed(self):
        self.approve(self.proposal())
        with self.store.connection() as db:
            db.execute("UPDATE documents SET original=?", (b"tampered",))
        with self.assertRaises(ValueError):
            self.consumer.state()

    def test_undo_forget_and_ttl(self):
        first = self.proposal()
        self.approve(first)
        second = self.proposal("Segunda versão.")
        self.approve(second)
        self.consumer.apply("undo", dict(note_id=second["note_id"], proposal_hash=second["proposal_hash"], actor="operator"))
        self.assertEqual(self.consumer.state()["active"][0]["text"], first["text"])
        self.consumer.apply("forget", dict(note_id=second["note_id"], proposal_hash=second["proposal_hash"], actor="operator"))
        self.assertEqual(self.consumer.state()["active"], [])
        self.approve(self.proposal())
        self.now += 7 * 24 * 3600
        self.assertEqual(self.consumer.state()["active"], [])
        self.consumer.memory.purge_expired(now=self.now)
        with sqlite3.connect(Path(self.tmp.name) / "memory.sqlite3") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM notes WHERE payload IS NOT NULL").fetchone()[0], 0)

    def test_independent_source_writer_blocks_until_guard_released(self):
        writer = Store(self.tmp.name)
        started, done = threading.Event(), threading.Event()
        errors = []
        def change():
            started.set()
            try:
                writer.review(self.doc["id"], 2, self.doc["revision"], "writer", "rejected")
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                done.set()
        with self.consumer.current():
            thread = threading.Thread(target=change)
            thread.start()
            self.assertTrue(started.wait(1))
            self.assertFalse(done.wait(.1))
        self.assertTrue(done.wait(2))
        thread.join(2)
        self.assertEqual(errors, [])


class HttpMemoryTests(Fixture, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.server = Server(self.consumer, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def call(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        hdr = {"X-Lab-Token": self.server.token}
        if headers:
            hdr.update(headers)
        if body is not None:
            hdr.setdefault("Content-Type", "application/json")
        conn.request("GET" if body is None else "POST", path, None if body is None else json.dumps(body), hdr)
        response = conn.getresponse()
        result = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, result, response_headers

    def test_http_review_source_and_edit_flow(self):
        sources = json.loads(self.call("/api/state")[1])["sources"]
        status, raw, _ = self.call("/api/propose", dict(note_id="http", text="Nota via HTTP.", proposer="author", source_ids=[sources[0]["id"]]))
        self.assertEqual(status, 200)
        draft = json.loads(raw)
        self.assertEqual(self.call("/api/approve", dict(note_id="http", proposal_hash=draft["proposal_hash"], reviewer="reviewer"))[0], 200)
        self.assertEqual(json.loads(self.call("/api/state")[1])["active"][0]["text"], "Nota via HTTP.")
        self.assertEqual(self.call("/api/source/" + sources[0]["id"])[0], 200)
        self.assertEqual(self.call("/api/approve", dict(note_id="http", proposal_hash=draft["proposal_hash"], reviewer="reviewer"))[0], 400)

    def test_host_origin_token_body_and_busy_guards(self):
        self.assertEqual(self.call("/api/state", headers={"X-Lab-Token":""})[0], 403)
        self.assertEqual(self.call("/", headers={"Host":"evil.example"})[0], 403)
        self.assertEqual(self.call("/api/state", headers={"Origin":"https://evil.example"})[0], 403)
        self.assertEqual(self.call("/api/propose", {}, headers={"Content-Length":str(MAX_BODY + 1)})[0], 413)
        self.assertEqual(self.call("/api/propose", {}, headers={"Content-Type":"text/plain"})[0], 415)
        self.assertEqual(self.call("/api/propose", [])[0], 400)
        self.assertEqual(self.call("/api/propose", {"text":"private-note"})[0], 400)
        self.server.work.acquire()
        try:
            self.assertEqual(self.call("/api/propose", {})[0], 429)
        finally:
            self.server.work.release()

    def test_ui_headers_and_no_html_execution(self):
        status, html, headers = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn(b"innerHTML", html)
        self.assertIn(b"text.textContent=note.text", html)
        self.assertNotIn(b"private-note", self.call("/api/propose", {"text":"private-note"})[1])


@unittest.skipUnless(os.environ.get("PDF_BROWSER_TESTS") == "1", "Browser optional; enabled in CI")
class BrowserMemoryTests(unittest.TestCase):
    def test_operator_proposes_reads_sources_reviews_corrects_undoes_and_forgets(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            doc = store.ingest(make_pdf(), "fixture.pdf")
            store.review(doc["id"], 2, doc["revision"], "source-reviewer", "approved")
            server = Server(ProjectMemory(store), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as driver:
                    browser = driver.chromium.launch(headless=True)
                    try:
                        page = browser.new_page(viewport={"width":390,"height":844})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(f"http://127.0.0.1:{server.server_port}")
                        page.locator("#sources input").first.wait_for()
                        page.get_by_role("button", name="Ler fonte").first.click()
                        page.locator("#sources pre").filter(has_text="1.250,50").wait_for()
                        page.locator("#note").fill("continuidade")
                        page.locator("#proposer").fill("author")
                        page.locator("#reviewer").fill("reviewer")
                        page.locator("#actor").fill("operator")
                        note = '<script>window.injected=true</script> Conferir pagamento.'
                        page.locator("#text").fill(note)
                        page.locator("#sources input").first.check()
                        page.get_by_role("button",name="Criar proposta").click()
                        page.locator("#pending pre").filter(has_text="Conferir pagamento").wait_for()
                        page.get_by_role("button",name="Aprovar nota").click()
                        page.locator("#active pre").filter(has_text="Conferir pagamento").wait_for()
                        self.assertIsNone(page.evaluate("window.injected"))
                        page.locator("#active").get_by_role("button",name="Corrigir nota").click()
                        page.locator("#text").fill("Texto corrigido.")
                        page.get_by_role("button",name="Criar proposta").click()
                        page.locator("#pending pre").filter(has_text="Texto corrigido").wait_for()
                        page.get_by_role("button",name="Aprovar nota").click()
                        page.locator("#active pre").filter(has_text="Texto corrigido").wait_for()
                        page.get_by_role("button",name="Desfazer aprovação").click()
                        page.locator("#active pre").filter(has_text="Conferir pagamento").wait_for()
                        page.on("dialog", lambda dialog: dialog.accept())
                        page.locator("#active").get_by_role("button",name="Esquecer todas as versões").click()
                        page.get_by_text("Nenhuma nota aprovada atual.", exact=True).wait_for()
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),390)
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)
