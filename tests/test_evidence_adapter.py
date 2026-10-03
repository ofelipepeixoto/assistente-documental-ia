"""Store/PDF reais; kit local, sem modelo, rede ou ação externa."""

from contextlib import redirect_stderr, redirect_stdout
import builtins
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from avaliacao.pdf_fixtures import make_pdf
from exportar_evidencias import main
from ingestion.contracts import LabError, text_digest
from ingestion.evidence_adapter import export_approved_evidence
from ingestion.store import Store


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(self.temporary.name)
        self.doc = self.store.ingest(make_pdf([
            "Pagamento mensal fictício de R$ 1.250,50. Não há multa contratual."
        ]), "contrato.pdf")

    def approve(self, text=None):
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "approved", text)
        return self.doc

    def export(self, revisions=None):
        return export_approved_evidence(
            self.store, tenant_id="operador-local", project_id="contratos-demo",
            expected_revisions=revisions if revisions is not None else {self.doc["id"]: self.doc["revision"]},
        )

    def tamper_manifest(self, change):
        manifest = self.store.get(self.doc["id"])
        change(manifest)
        with self.store.connection() as db:
            db.execute("UPDATE documents SET manifest = ? WHERE id = ?", (json.dumps(manifest), self.doc["id"]))

    def test_only_approved_snapshot_with_full_text_hash_and_page(self):
        self.approve()
        item, = self.export()
        page = self.doc["pages"][0]
        self.assertEqual(item.text, page["text"])
        self.assertEqual(item.text_sha256, text_digest(page["text"]))
        self.assertEqual(item.source_sha256, self.doc["source_sha256"])
        self.assertEqual((item.page, item.revision, item.start, item.end), (1, self.doc["revision"], 0, len(page["text"])))
        self.assertEqual(item.quote, page["text"])
        self.assertEqual(item.reviewer, "Pessoa local")
        self.assertEqual(item.review_status, "approved")
        self.assertFalse(item.identity_verified)
        self.assertEqual(len(item.evidence_id), 64)

    def test_unreviewed_pages_are_excluded(self):
        self.assertEqual(self.export(), [])

    def test_rejected_pages_are_excluded(self):
        self.approve()
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "rejected")
        self.assertEqual(self.export(), [])

    def test_changed_text_requires_new_revision_and_preserves_new_full_text(self):
        self.approve()
        old_revision = self.doc["revision"]
        corrected = "Pagamento corrigido fictício: R$ 1.200,00. Conferido pela pessoa local."
        self.doc = self.store.review(self.doc["id"], 1, old_revision, "Pessoa local", "approved", corrected)
        with self.assertRaises(LabError):
            self.export({self.doc["id"]: old_revision})
        item, = self.export()
        self.assertEqual(item.text, corrected)
        self.assertEqual(item.text_sha256, text_digest(corrected))

    def test_stale_revision_is_rejected_without_partial_result(self):
        self.approve()
        with self.assertRaises(LabError):
            self.export({self.doc["id"]: self.doc["revision"] - 1})

    def test_text_tamper_invalidates_approval(self):
        self.approve()
        self.tamper_manifest(lambda manifest: manifest["pages"][0].update(text="Texto local adulterado."))
        self.assertEqual(self.export(), [])

    def test_original_tamper_blocks_export(self):
        self.approve()
        with self.store.connection() as db:
            db.execute("UPDATE documents SET original = ? WHERE id = ?", (b"%PDF- adulterado", self.doc["id"]))
        with self.assertRaises(LabError):
            self.export()

    def test_forged_review_text_hash_is_excluded(self):
        self.approve()
        self.tamper_manifest(lambda manifest: manifest["pages"][0]["review"].update(text_sha256="0" * 64))
        self.assertEqual(self.export(), [])

    def test_forged_review_source_hash_is_excluded(self):
        self.approve()
        self.tamper_manifest(lambda manifest: manifest["pages"][0]["review"].update(source_sha256="0" * 64))
        self.assertEqual(self.export(), [])

    def test_manifest_identity_claim_never_promotes_verified_identity(self):
        self.approve()
        self.tamper_manifest(lambda manifest: manifest["pages"][0]["review"].update(identity_verified=True))
        item, = self.export()
        self.assertFalse(item.identity_verified)

    def test_missing_document_blocks_export(self):
        with self.assertRaises(LabError):
            self.export({"0" * 64: 1})

    def test_invalid_scope_and_revision_types(self):
        for revisions in [{self.doc["id"]: True}, {self.doc["id"]: 0}, {}, []]:
            with self.subTest(revisions=revisions), self.assertRaises(LabError):
                self.export(revisions)
        with self.assertRaises(LabError):
            export_approved_evidence(self.store, tenant_id="", project_id="p", expected_revisions={self.doc["id"]: 1})

    def test_scope_limit_is_checked_even_with_zero_approved_pages(self):
        for tenant, project in [("x" * 257, "p"), ("t", "p" * 257)]:
            with self.subTest(tenant=len(tenant), project=len(project)), self.assertRaises(LabError):
                export_approved_evidence(self.store, tenant_id=tenant, project_id=project,
                                         expected_revisions={self.doc["id"]: self.doc["revision"]})

    def test_scope_map_limit_and_extra_missing_document_are_rejected(self):
        too_many = {f"{index:064x}": 1 for index in range(10001)}
        with patch.object(self.store, "get") as read, self.assertRaises(LabError):
            self.export(too_many)
        read.assert_not_called()
        with self.assertRaises(LabError):
            self.export({self.doc["id"]: self.doc["revision"], "0" * 64: 1})

    def test_large_page_is_rejected_without_truncation(self):
        text = "Texto fictício aprovado. " + ("é" * (16 * 1024))
        self.approve(text)
        with self.assertRaisesRegex(LabError, "nada foi truncado"):
            self.export()
        self.assertEqual(self.store.get(self.doc["id"])["pages"][0]["text"], text)

    def test_unicode_span_is_complete_and_uses_code_points(self):
        text = "Cláusula fictícia com acentuação e emoji 😀; revisão local completa."
        self.approve(text)
        item, = self.export()
        self.assertEqual(item.end, len(text))
        self.assertEqual(item.quote, text)

    def test_manifest_change_during_export_is_rejected(self):
        self.approve()
        original = self.store.original
        def changing_original(document_id):
            data = original(document_id)
            self.store.review(document_id, 1, self.doc["revision"], "Pessoa local", "rejected")
            return data
        with patch.object(self.store, "original", side_effect=changing_original), self.assertRaises(LabError):
            self.export()

    def test_corrupt_manifest_shapes_fail_with_safe_error(self):
        self.approve()
        changes = [lambda m: m.update(schema_version=True), lambda m: m.update(revision=True),
                   lambda m: m["pages"][0].update(page_number=True),
                   lambda m: m["pages"][0].update(text=123),
                   lambda m: m["pages"][0].update(review=["approved"])]
        saved = self.store.get(self.doc["id"])
        for change in changes:
            with self.subTest(change=change):
                with self.store.connection() as db:
                    db.execute("UPDATE documents SET manifest = ? WHERE id = ?", (json.dumps(saved), self.doc["id"]))
                self.tamper_manifest(change)
                with self.assertRaises(LabError):
                    self.export()

    def test_missing_optional_kit_has_clear_error_and_baseline_imports_work(self):
        importer = builtins.__import__
        def missing(name, *args, **kwargs):
            if name == "radar_evidence":
                raise ImportError("missing optional kit")
            return importer(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=missing), self.assertRaisesRegex(LabError, "opcional indisponível"):
            self.export()
        self.assertEqual(self.store.get(self.doc["id"]), self.doc)

    def test_cli_exports_json_envelope_and_unverified_scope(self):
        self.approve()
        output = io.StringIO()
        with redirect_stdout(output):
            main(["--pasta", self.temporary.name, "--tenant", "t", "--projeto", "p",
                  "--documento", f"{self.doc['id']}:{self.doc['revision']}"])
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["scope"]["current_revisions"], {self.doc["id"]: self.doc["revision"]})
        record = payload["evidence"][0]
        self.assertFalse(record["record"]["identity_verified"])
        self.assertEqual(set(record), {"record", "evidence_id"})

    def test_cli_does_not_create_missing_workspace(self):
        missing = Path(self.temporary.name) / "missing"
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["--pasta", str(missing), "--tenant", "t", "--projeto", "p", "--documento", f"{self.doc['id']}:1"])
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(missing.exists())

    def test_cli_existing_corrupt_database_and_manifest_have_safe_errors(self):
        corrupt = Path(self.temporary.name) / "corrupt"
        corrupt.mkdir()
        (corrupt / "lab.sqlite3").write_bytes(b"not SQLite")
        with self.store.connection() as db:
            db.execute("UPDATE documents SET manifest = ? WHERE id = ?", ("invalid-json-marker", self.doc["id"]))
        for workspace in [corrupt, Path(self.temporary.name)]:
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(workspace=workspace), redirect_stdout(output), redirect_stderr(errors), self.assertRaises(SystemExit) as failure:
                main(["--pasta", str(workspace), "--tenant", "t", "--projeto", "p", "--documento", f"{self.doc['id']}:1"])
            self.assertEqual(failure.exception.code, 1)
            self.assertEqual(output.getvalue(), "")
            self.assertNotIn("invalid-json-marker", errors.getvalue())

    def test_cli_missing_document_emits_no_partial_snapshot(self):
        self.approve()
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--pasta", self.temporary.name, "--tenant", "t", "--projeto", "p",
                  "--documento", f"{self.doc['id']}:{self.doc['revision']}", "--documento", f"{'0' * 64}:1"])
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
