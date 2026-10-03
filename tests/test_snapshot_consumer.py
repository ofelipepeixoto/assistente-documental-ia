"""Replays e adulterações locais; nenhuma identidade, LLM ou efeito externo."""

import copy
import tempfile
import unittest
from unittest.mock import patch

from radar_evidence import Evidence, Scope

from avaliacao.pdf_fixtures import make_pdf
from ingestion.contracts import LabError
from ingestion.evidence_adapter import export_approved_evidence, validate_local_snapshot
from ingestion.store import Store


class SnapshotConsumerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = Store(temporary.name)
        document = self.store.ingest(make_pdf([
            "Pagamento mensal fictício de R$ 1.250,50, conferido em contrato."
        ]), "ficticio.pdf")
        self.doc = self.store.review(document["id"], 1, 1, "Pessoa local", "approved")
        items = export_approved_evidence(
            self.store, tenant_id="local", project_id="demo",
            expected_revisions={self.doc["id"]: self.doc["revision"]},
        )
        self.payload = {
            "schema_version": 1,
            "kind": "documental_evidence_snapshot",
            "scope": Scope(tenant_id="local", project_id="demo",
                           current_revisions={self.doc["id"]: self.doc["revision"]}).to_dict(),
            "evidence": [{"evidence_id": item.evidence_id, "record": item.to_dict()} for item in items],
        }

    def validate(self, payload=None, **scope):
        return validate_local_snapshot(
            self.store, payload if payload is not None else self.payload,
            tenant_id=scope.get("tenant_id", "local"), project_id=scope.get("project_id", "demo"),
            document_ids=scope.get("document_ids", [self.doc["id"]]),
        )

    def test_current_snapshot_returns_only_unverified_store_records(self):
        item, = self.validate()
        self.assertEqual(item.source_sha256, self.doc["source_sha256"])
        self.assertEqual(item.revision, self.doc["revision"])
        self.assertFalse(item.identity_verified)

    def test_rejected_approval_cannot_be_replayed(self):
        self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "rejected")
        with self.assertRaises(LabError):
            self.validate()

    def test_corrected_approval_cannot_be_replayed_even_with_recomputed_hash(self):
        updated = self.store.review(self.doc["id"], 1, self.doc["revision"], "Pessoa local", "approved",
                                    "Pagamento mensal corrigido de R$ 1.200,00, conferido localmente.")
        payload = copy.deepcopy(self.payload)
        payload["scope"]["current_revisions"][self.doc["id"]] = updated["revision"]
        record = payload["evidence"][0]["record"]
        record["revision"] = updated["revision"]
        payload["evidence"][0]["evidence_id"] = Evidence.from_dict(record).evidence_id
        with self.assertRaises(LabError):
            self.validate(payload)

    def test_relabelled_reviewer_and_identity_never_gain_trust(self):
        for changes in [{"reviewer": "Outra pessoa"}, {"identity_verified": True}]:
            payload = copy.deepcopy(self.payload)
            record = payload["evidence"][0]["record"]
            record.update(changes)
            payload["evidence"][0]["evidence_id"] = Evidence.from_dict(record).evidence_id
            with self.subTest(changes=changes), self.assertRaises(LabError):
                self.validate(payload)

    def test_hash_page_source_and_record_omission_fail_closed(self):
        for mutation in ["id", "source", "page", "omit", "bool_page"]:
            payload = copy.deepcopy(self.payload)
            if mutation == "id":
                payload["evidence"][0]["evidence_id"] = "0" * 64
            elif mutation == "omit":
                payload["evidence"] = []
            else:
                key, value = {"source": ("source_sha256", "0" * 64),
                              "page": ("page", 2), "bool_page": ("page", True)}[mutation]
                payload["evidence"][0]["record"][key] = value
            with self.subTest(mutation=mutation), self.assertRaises(LabError):
                self.validate(payload)

    def test_consumer_configuration_controls_scope_and_document_selection(self):
        for configuration in [{"tenant_id": "outro"}, {"project_id": "outro"},
                              {"document_ids": ["0" * 64]}]:
            with self.subTest(configuration=configuration), self.assertRaises(LabError):
                self.validate(**configuration)

    def test_schema_boolean_and_extra_fields_are_rejected(self):
        for change in [{"schema_version": True}, {"identity_verified": True}, {"kind": "action"}]:
            payload = copy.deepcopy(self.payload)
            payload.update(change)
            with self.subTest(change=change), self.assertRaises(LabError):
                self.validate(payload)

    def test_original_corruption_blocks_consumption(self):
        with self.store.connection() as db:
            db.execute("UPDATE documents SET original = ? WHERE id = ?", (b"%PDF- corrompido", self.doc["id"]))
        with self.assertRaises(LabError):
            self.validate()

    def test_selected_documents_share_historical_snapshot(self):
        second = self.store.ingest(make_pdf(["Outro pagamento fictício, separado para revisão local."]), "segundo.pdf")
        second = self.store.review(second["id"], 1, 1, "Pessoa local", "approved")
        revisions = {self.doc["id"]: self.doc["revision"], second["id"]: second["revision"]}
        snapshots = self.store.snapshots

        def revise_after_read(document_ids):
            result = snapshots(document_ids)
            self.store.review(second["id"], 1, second["revision"], "Pessoa local", "rejected")
            return result

        with patch.object(self.store, "snapshots", side_effect=revise_after_read):
            items = export_approved_evidence(self.store, tenant_id="local", project_id="demo",
                                             expected_revisions=revisions)
        self.assertEqual({item.document_id for item in items}, set(revisions))
        self.assertEqual({item.review_status for item in items}, {"approved"})
        self.assertEqual(self.store.get(second["id"])["revision"], second["revision"] + 1)

    def test_snapshot_document_limits_and_duplicates(self):
        for ids in [[], [self.doc["id"], self.doc["id"]], [f"{index:064x}" for index in range(51)]]:
            with self.subTest(ids=len(ids)), self.assertRaises(LabError):
                self.store.snapshots(ids)


if __name__ == "__main__":
    unittest.main()
