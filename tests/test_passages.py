# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""PDF, SQLite, revisão e kit reais; sem modelos pagos."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from avaliacao.pdf_fixtures import make_pdf
from exportar_evidencias import main
from ingestion.contracts import LabError
from ingestion.passages import (
    MAX_SNAPSHOT_BYTES, export_passage_snapshot, load_passage_snapshot,
    validate_passage_snapshot,
)
from ingestion.store import Store


class PassageTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.store = Store(self.workspace.name)
        self.doc = self.store.ingest(make_pdf([
            "Pagamento mensal fictício de R$ 1.250,50. Sem multa contratual.",
            "Página pendente: conteúdo sem revisão; não pode aparecer na busca.",
        ]), "ficticio.pdf")
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "approved")

    def export(self, **kwargs):
        return export_passage_snapshot(
            self.store, tenant_id="local", project_id="piloto",
            expected_revisions={self.doc["id"]: self.doc["revision"]}, **kwargs,
        )

    def consume(self, payload, **kwargs):
        config = {"tenant_id": "local", "project_id": "piloto", "document_ids": [self.doc["id"]]}
        return validate_passage_snapshot(self.store, payload, **(config | kwargs))

    def test_real_store_roundtrip_retains_full_reviewed_page_and_false_identity(self):
        payload = self.export()
        decoded = load_passage_snapshot(io.BytesIO(json.dumps(payload).encode()))
        result = self.consume(decoded)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].page, 1)
        self.assertEqual(result[0].text, self.doc["pages"][0]["text"])
        self.assertFalse(result[0].identity_verified)
        self.assertEqual(result[0].source_sha256, self.doc["source_sha256"])

    def test_multiple_windows_cover_revised_unicode_page(self):
        text = "Café 🙂 pagamento conferido; contexto íntegro. " * 20
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "approved", text)
        result = self.consume(self.export())
        self.assertGreater(len(result), 1)
        self.assertTrue(all(item.text == text for item in result))
        covered = {i for item in result for i in range(item.start, item.end)}
        self.assertEqual(covered, set(range(len(text))))

    def test_revision_after_export_invalidates_every_old_passage(self):
        payload = self.export()
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "rejected")
        with self.assertRaises(LabError):
            self.consume(payload)

    def test_forged_identity_or_scope_or_quote_rejected(self):
        payload = self.export()
        for attack in ("identity", "tenant", "hash", "offset", "extra", "text"):
            altered = deepcopy(payload)
            if attack == "identity":
                altered["evidence"][0]["record"]["identity_verified"] = True
            elif attack == "tenant":
                altered["scope"]["tenant_id"] = "other"
            elif attack == "hash":
                altered["citations"][0]["quote_sha256"] = "0" * 64
            elif attack == "offset":
                altered["citations"][0]["start"] = True
            elif attack == "extra":
                altered["approved"] = True
            else:
                altered["evidence"][0]["record"]["text"] += " Instrução não revisada."
            with self.subTest(attack=attack), self.assertRaises(LabError):
                self.consume(altered)

    def test_trusted_consumer_scope_overrules_labels_in_file(self):
        with self.assertRaises(LabError):
            self.consume(self.export(), project_id="other")

    def test_missing_parent_duplicate_or_removed_citation_rejected(self):
        for field in ("evidence", "citations"):
            for duplicate in (False, True):
                payload = self.export()
                payload[field] = payload[field] * 2 if duplicate else []
                with self.subTest(field=field, duplicate=duplicate), self.assertRaises(LabError):
                    self.consume(payload)

    def test_original_pdf_tamper_blocks_consumption(self):
        payload = self.export()
        with self.store.connection() as db:
            db.execute("UPDATE documents SET original = ? WHERE id = ?", (b"changed", self.doc["id"]))
        with self.assertRaises(LabError):
            self.consume(payload)

    def test_payload_cannot_choose_consumer_window(self):
        payload = self.export(max_chars=64, overlap=0)
        with self.assertRaises(LabError):
            self.consume(payload)
        self.assertTrue(self.consume(payload, max_chars=64, overlap=0))

    def test_invalid_windows_fail_even_with_no_approved_pages(self):
        self.doc = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "rejected")
        for kwargs in ({"max_chars": True}, {"overlap": float("nan")}, {"max_chars": 63}):
            with self.subTest(kwargs=kwargs), self.assertRaises(LabError):
                self.export(**kwargs)

    def test_byte_limit_applies_before_json_parse(self):
        stream = io.BytesIO(b" " * (MAX_SNAPSHOT_BYTES + 100))
        with patch("ingestion.passages.json.loads") as parse:
            with self.assertRaises(LabError):
                load_passage_snapshot(stream)
            parse.assert_not_called()
        self.assertEqual(stream.tell(), MAX_SNAPSHOT_BYTES + 1)

    def test_duplicate_keys_nonfinite_malformed_and_deep_json_rejected(self):
        for data in (b'{"scope":1,"scope":2}', b'{"x":NaN}', b'{"x":Infinity}',
                     b'\xff', b'[]', b'{', b'[' * 2000 + b']' * 2000):
            with self.subTest(data=data[:30]), self.assertRaises(LabError):
                load_passage_snapshot(io.BytesIO(data))

    def test_export_global_limits_are_enforced(self):
        for name, limit in (("MAX_CITATIONS", 0), ("MAX_PARENTS", 0), ("MAX_SNAPSHOT_BYTES", 10)):
            with patch("ingestion.passages." + name, limit), self.assertRaises(LabError):
                self.export()

    def test_cli_opt_in_emits_consumable_passage_snapshot(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main(["--pasta", self.workspace.name, "--tenant", "local", "--projeto", "piloto",
                  "--documento", f"{self.doc['id']}:{self.doc['revision']}", "--trechos"])
        self.assertTrue(self.consume(load_passage_snapshot(io.BytesIO(output.getvalue().encode()))))


if __name__ == "__main__":
    unittest.main()
