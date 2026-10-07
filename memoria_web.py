# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Optional offline reviewed-memory UI. Loopback, one operator, no real auth."""
import argparse
from http.server import ThreadingHTTPServer
import json
import secrets
import sqlite3
import threading

from documentos_web import Handler as DocumentHandler
from ingestion.contracts import LabError
from ingestion.project_memory import ProjectMemory
from ingestion.store import Store

MAX_BODY = 64 * 1024


def page(token):
    return r'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Memória revisável do projeto</title>
<style>body{font:18px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;color:#18232f;line-height:1.5}
article,section{border:1px solid #ccd3dd;border-radius:10px;padding:1rem;margin:1rem 0}
textarea,input,button{font:inherit;max-width:100%;box-sizing:border-box;padding:.5rem}textarea{width:100%;min-height:120px}
pre,small{white-space:pre-wrap;overflow-wrap:anywhere}button{margin:.3rem;cursor:pointer}small{display:block}
.notice{background:#fff4d1;padding:1rem}label{display:block}</style>
<h1>Memória revisável do projeto</h1>
<p class="notice">Piloto local de um operador. Nomes são rótulos não autenticados.
Notas são dados derivados; não autorizam ferramentas nem substituem o documento.
Use fontes fictícias ou autorizadas. Validade de sete dias. Nada é enviado a provedores.</p>
<p id="message" role="status" aria-live="polite"></p>
<section><h2>1. Preparar uma nota</h2>
<p>Aprove as páginas na interface documental antes de usá-las como fonte.
Para corrigir, use o mesmo identificador: a nova versão exige outra revisão.</p>
<label for="note">Identificador da nota</label><input id="note" maxlength="256">
<label for="proposer">Nome do proponente</label><input id="proposer" maxlength="256">
<label for="text">Texto completo da proposta</label><textarea id="text"></textarea>
<h3>Fontes atuais — selecione de uma a oito</h3><div id="sources"></div>
<button id="propose">Criar proposta</button></section>
<section><h2>2. Conferir propostas</h2><label for="reviewer">Nome distinto para registrar revisão</label>
<input id="reviewer" maxlength="256"><p>Confira texto e fontes antes de aprovar.
Nomes distintos não comprovam duas pessoas.</p><div id="pending"></div></section>
<section><h2>3. Notas aprovadas atuais</h2><label for="actor">Nome para desfazer ou esquecer</label>
<input id="actor" maxlength="256"><button id="refresh">Atualizar</button><div id="active"></div>
<p>Esquecer remove todas as versões da nota no banco ativo. Cópias de backup precisam de descarte separado.</p></section>
<section><h2>4. Notas fora da leitura aprovada</h2><p>Rejeitadas, retiradas, desfeitas ou vencidas; confira a fonte antes de propor novamente.</p><div id="archived"></div></section>
<script nonce="__TOKEN__">
const token="__TOKEN__";const el=id=>document.getElementById(id);
const message=text=>el('message').textContent=text;
async function request(path,body){const options={headers:{'X-Lab-Token':token}};
if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw new Error(data.error);return data;}
async function guarded(fn){try{await fn();}catch(error){message(error.message);}}
function button(caption,fn){const b=document.createElement('button');b.textContent=caption;b.onclick=()=>guarded(fn);return b;}
async function source(id,parent){const data=await request('/api/source/'+id);
const pre=document.createElement('pre');pre.textContent='Documento '+data.document_id+' · página '+data.page+' · versão '+data.revision+'\nSHA256 '+data.source_sha256+'\n'+data.text;parent.append(pre);}
function render(notes,kind){const parent=el(kind);parent.replaceChildren();
if(!notes.length)parent.textContent=kind==='active'?'Nenhuma nota aprovada atual.':kind==='pending'?'Nenhuma proposta pendente.':'Nenhuma nota arquivada.';
for(const note of notes){const card=document.createElement('article');const title=document.createElement('h3');title.textContent=note.note_id+' · versão '+note.version;
const text=document.createElement('pre');text.textContent=note.text;const hash=document.createElement('small');hash.textContent='Hash da proposta: '+note.proposal_hash+' · vence: '+new Date(note.expires_at*1000).toLocaleString('pt-BR');card.append(title,text,hash);
if(note.latest_version){const receipt=document.createElement('small');receipt.textContent='Descarte usa o recibo da última versão: '+note.latest_version+' · '+note.latest_proposal_hash;card.append(receipt);}
for(const id of note.source_ids)card.append(button('Conferir fonte '+id.slice(0,8),()=>source(id,card)));
if(kind==='pending')for(const [action,label] of [['approve','Aprovar nota'],['reject','Rejeitar nota']])card.append(button(label,async()=>{
await request('/api/'+action,{note_id:note.note_id,proposal_hash:note.proposal_hash,reviewer:el('reviewer').value});await refresh();message('Decisão registrada.');}));
card.append(button('Corrigir nota',async()=>{el('note').value=note.note_id;el('text').value=note.text;for(const box of el('sources').querySelectorAll('input'))box.checked=note.source_ids.includes(box.value);el('text').focus();message('Edite e crie uma nova proposta.');}));
for(const [action,label] of (kind==='active'?[['undo','Desfazer aprovação'],['forget','Esquecer todas as versões']]:[['forget','Esquecer todas as versões']]))card.append(button(label,async()=>{
if(action==='forget'&&!window.confirm('Apagar todas as versões desta nota do banco ativo?'))return;
await request('/api/'+action,{note_id:note.note_id,proposal_hash:action==='forget'?(note.latest_proposal_hash||note.proposal_hash):note.proposal_hash,actor:el('actor').value});await refresh();message('Alteração registrada.');}));parent.append(card);}}
async function refresh(){const data=await request('/api/state');el('sources').replaceChildren();
for(const item of data.sources){const label=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.value=item.id;
label.append(box,document.createTextNode('Documento '+item.document_id.slice(0,12)+' · página '+item.page+' · versão '+item.revision));
label.append(button('Ler fonte',()=>source(item.id,label)));el('sources').append(label);}
render(data.pending,'pending');render(data.active,'active');render(data.archived,'archived');}
el('propose').onclick=()=>guarded(async()=>{const source_ids=[...el('sources').querySelectorAll('input:checked')].map(box=>box.value);
await request('/api/propose',{note_id:el('note').value,text:el('text').value,proposer:el('proposer').value,source_ids});await refresh();message('Proposta pendente de revisão.');});
el('refresh').onclick=()=>guarded(refresh);guarded(refresh);
</script></html>'''.replace('__TOKEN__', token)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, project_memory, port=8002):
        self.project_memory = project_memory
        self.token = secrets.token_hex(32)
        self.work = threading.BoundedSemaphore(1)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(DocumentHandler):
    def do_GET(self):
        if not self.allowed(protected=self.path != "/"):
            return self.respond(403, {"error": "Acesso local inválido."})
        try:
            if self.path == "/":
                return self.respond(200, page(self.server.token).encode(), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self.respond(200, self.server.project_memory.state())
            if self.path.startswith("/api/source/"):
                return self.respond(200, self.server.project_memory.source(self.path.removeprefix("/api/source/")))
            return self.respond(404, {"error": "Página não encontrada."})
        except (LabError, ValueError, TypeError, sqlite3.Error):
            return self.respond(400, {"error": "Fonte ou memória mudou; recarregue e confira o registro."})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error": "Acesso local inválido."})
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Corpo inválido."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.respond(400, {"error": "Tamanho inválido."})
        if not 0 < length <= MAX_BODY:
            return self.respond(413, {"error": "Solicitação acima do limite."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.respond(415, {"error": "Use JSON."})
        if not self.server.work.acquire(blocking=False):
            return self.respond(429, {"error": "Há uma operação em andamento."})
        try:
            self.connection.settimeout(5)
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError
            data = json.loads(body)
            result = self.server.project_memory.apply(self.path.removeprefix("/api/"), data)
            return self.respond(200, result)
        except (LabError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error, TimeoutError):
            return self.respond(400, {"error": "Solicitação inválida ou versão mudou. Recarregue antes de revisar."})
        finally:
            self.server.work.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", default=".documentos")
    parser.add_argument("--porta", type=int, default=8002)
    args = parser.parse_args()
    memory = ProjectMemory(Store(args.pasta))
    memory.memory.purge_expired(now=memory.clock())
    server = Server(memory, args.porta)
    print(f"Memória local: http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
