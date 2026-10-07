# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Optional single-operator memory; source writes serialized with decisions."""
from contextlib import contextmanager
import sqlite3
import time

from ingestion.contracts import LabError
from ingestion.evidence_adapter import export_approved_evidence


class ProjectMemory:
    def __init__(self, store, *, tenant_id="local-operator", project_id="documental-lab", clock=None):
        from radar_evidence import Scope
        from radar_evidence.memory import MemoryStore
        # Validate trusted operator configuration before accepting HTTP input.
        Scope(tenant_id, project_id, {})
        self.store = store
        self.tenant = tenant_id
        self.project = project_id
        self.clock = clock or (lambda: int(time.time()))
        self.memory = MemoryStore(store.path.with_name("memory.sqlite3"), local_review=True)

    @contextmanager
    def current(self, *, permit_source_failure=False):
        from radar_evidence import Scope
        # Reserved SQLite source write lock blocks writers in other processes,
        # not just threads sharing this Store. Reads on other connections work.
        # Lock order is always source -> memory. No source data is changed here.
        with self.store.lock, self.store.connection() as guard:
            guard.execute("BEGIN IMMEDIATE")
            self.source_unavailable = False
            try:
                documents = self.store.list()
                revisions = {doc["id"]: doc["revision"] for doc in documents}
                scope = Scope(self.tenant, self.project, revisions)
                sources = export_approved_evidence(
                    self.store, tenant_id=self.tenant, project_id=self.project,
                    expected_revisions=revisions,
                ) if revisions else []
            except (LabError, ValueError, TypeError, KeyError, sqlite3.Error):
                if not permit_source_failure:
                    raise
                self.source_unavailable = True
                scope, sources = Scope(self.tenant, self.project, {}), []
            yield scope, {source.evidence_id: source for source in sources}

    def state(self):
        from radar_evidence import Scope
        try:
            with self.current(permit_source_failure=True) as (scope, sources):
                return self._state(scope, sources, self.source_unavailable)
        except sqlite3.Error:
            # Even an unreadable source database must not hide discard receipts.
            return self._state(Scope(self.tenant, self.project, {}), {}, True)

    def _state(self, scope, sources, unavailable):
        now = self.clock()
        active = self.memory.recall(scope=scope, sources=list(sources.values()), now=now)
        latest = self.memory.latest(scope=scope)
        heads = {note["note_id"]: note for note in latest}
        pending = self.memory.pending(scope=scope, now=now)
        visible = {note["proposal_hash"] for note in active + pending}
        for note in active:
            note["latest_proposal_hash"] = heads[note["note_id"]]["proposal_hash"]
            note["latest_version"] = heads[note["note_id"]]["version"]
        return dict(
            active=active, pending=pending,
            archived=[note for note in latest if note["proposal_hash"] not in visible],
            source_unavailable=unavailable,
            sources=[dict(id=key, document_id=value.document_id, page=value.page,
                          revision=value.revision, source_sha256=value.source_sha256,
                          identity_verified=False) for key, value in sources.items()],
            identity_verified=False,
        )

    def source(self, evidence_id):
        with self.current() as (_, sources):
            if evidence_id not in sources:
                raise LabError("Fonte mudou ou não está aprovada. Recarregue.")
            return sources[evidence_id].to_dict()

    def apply(self, action, body):
        required = {
            "propose": {"note_id", "text", "proposer", "source_ids"},
            "approve": {"note_id", "proposal_hash", "reviewer"},
            "reject": {"note_id", "proposal_hash", "reviewer"},
            "undo": {"note_id", "proposal_hash", "actor"},
            "forget": {"note_id", "proposal_hash", "actor"},
        }
        if action not in required or type(body) is not dict or set(body) != required[action]:
            raise LabError("Solicitação de memória inválida.")
        if action == "forget":
            from radar_evidence import Scope
            self.memory.forget(scope=Scope(self.tenant, self.project, {}), note_id=body["note_id"],
                               proposal_hash=body["proposal_hash"], actor=body["actor"], now=self.clock())
            return {"ok": True, "identity_verified": False}
        with self.current() as (scope, sources):
            now = self.clock()
            if action == "propose":
                ids = body["source_ids"]
                if (type(ids) is not list or not 1 <= len(ids) <= 8
                        or any(type(key) is not str or key not in sources for key in ids)
                        or len(set(ids)) != len(ids)):
                    raise LabError("Selecione até oito fontes aprovadas atuais.")
                return self.memory.propose(note_id=body["note_id"], text=body["text"],
                                           proposer=body["proposer"], scope=scope,
                                           sources=[sources[key] for key in ids], now=now,
                                           ttl=7 * 24 * 3600)
            args = dict(scope=scope, note_id=body["note_id"], proposal_hash=body["proposal_hash"], now=now)
            if action in ("approve", "reject"):
                self.memory.decide(**args, reviewer=body["reviewer"], identity_verified=False,
                                   decision="approved" if action == "approve" else "rejected",
                                   sources=list(sources.values()))
            elif action == "undo":
                self.memory.undo(**args, actor=body["actor"], sources=list(sources.values()))
            return {"ok": True, "identity_verified": False}
