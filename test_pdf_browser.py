"""Browser real opcional; CI habilita PDF_BROWSER_TESTS=1 explicitamente."""

import os
import tempfile
import threading
import unittest

from avaliacao.pdf_fixtures import make_pdf
from documentos_web import Server
from ingestion.store import Store


@unittest.skipUnless(os.environ.get("PDF_BROWSER_TESTS") == "1", "Browser E2E opcional; habilitado no CI")
class BrowserPdfTests(unittest.TestCase):
    def test_user_uploads_reviews_queries_corrects_and_rejects(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as directory:
            server = Server(Store(directory), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as driver:
                    browser = driver.chromium.launch(headless=True)
                    try:
                        context = browser.new_context(viewport={"width": 1100, "height": 900}, accept_downloads=True)
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(f"http://127.0.0.1:{server.server_port}")
                        page.locator("#file").set_input_files({
                            "name": "contrato_demo.pdf", "mimeType": "application/pdf", "buffer": make_pdf(),
                        })
                        page.get_by_role("button", name="Extrair texto").click()
                        page.get_by_text("Página 2", exact=True).wait_for()
                        page.locator("#question").fill("pagamento mensal")
                        page.get_by_role("button", name="Buscar trechos").click()
                        page.get_by_text("Não encontrei evidência aprovada para essa pergunta.", exact=True).wait_for()
                        page.locator("#reviewer").fill("Pessoa fictícia")
                        page.locator("#pages article").nth(1).get_by_role("button", name="Aprovar esta página").click()
                        page.locator("#pages article").nth(1).get_by_text("Extração: texto extraído · revisão: aprovada", exact=True).wait_for()
                        page.get_by_role("button", name="Buscar trechos").click()
                        page.locator("#results h3").filter(has_text="contrato_demo.pdf — página 2").wait_for()
                        self.assertIn("R$ 1.250,50", page.locator("#results pre").inner_text())
                        with page.expect_download() as download:
                            page.get_by_role("button", name="Baixar original para conferir").click()
                        self.assertEqual(download.value.suggested_filename, "contrato_demo.pdf")
                        correction = 'Pagamento mensal revisado: R$ 1.200,00. <script>window.injected=true</script>'
                        page.locator("#page-2").fill(correction)
                        with page.expect_response(lambda response: response.url.endswith("/api/review")) as response:
                            page.locator("#pages article").nth(1).get_by_role("button", name="Aprovar esta página").click()
                        revision = response.value.json()["revision"]
                        page.wait_for_function("revision => current.revision === revision && document.getElementById('page-2').value.includes('1.200,00')", arg=revision)
                        page.get_by_role("button", name="Buscar trechos").click()
                        page.locator("#results pre").filter(has_text="1.200,00").wait_for()
                        self.assertIsNone(page.evaluate("window.injected"))
                        page.locator("#pages article").nth(1).get_by_role("button", name="Rejeitar esta página").click()
                        page.locator("#pages article").nth(1).get_by_text("Extração: texto extraído · revisão: rejeitada", exact=True).wait_for()
                        page.get_by_role("button", name="Buscar trechos").click()
                        page.get_by_text("Não encontrei evidência aprovada para essa pergunta.", exact=True).wait_for()
                        page.set_viewport_size({"width": 390, "height": 844})
                        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
