"""Interface de uma pessoa, somente loopback. Não é um serviço autenticado."""

import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading

from ingestion.contracts import LabError
from ingestion.search import search
from ingestion.store import Store

MAX_REQUEST_BYTES = 14 * 1024 * 1024


def page(token):
    template = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conferir e pesquisar documentos</title>
<style>body{font:18px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#18232f}
section,article{border:1px solid #ccd3dd;border-radius:12px;padding:1rem;margin:1rem 0}
button,input,select,textarea{font:inherit;padding:.6rem}button{cursor:pointer;margin:.25rem}
textarea{box-sizing:border-box;width:100%;min-height:160px}pre{white-space:pre-wrap;overflow-wrap:anywhere}
.notice{background:#fff4d1;padding:1rem}#message{min-height:1.5rem;font-weight:600}button:disabled{opacity:.5}
a{color:#135ca2}small{display:block;overflow-wrap:anywhere}
input,select,button{max-width:100%;box-sizing:border-box}</style></head><body>
<h1>Conferir e pesquisar documentos</h1>
<p class="notice">Laboratório local. Use exemplos fictícios ou documentos autorizados.
O texto só entra na busca depois da sua revisão. Não é aconselhamento jurídico.
Seu nome é um registro local, não uma identidade autenticada.</p>
<p id="message" role="status" aria-live="polite"></p>
<section><h2>1. Abrir um PDF</h2>
<label for="file">Arquivo PDF (até 10 MiB e 50 páginas)</label><br>
<input id="file" type="file" accept=".pdf,application/pdf">
<button id="upload">Extrair texto</button>
<p>Scans sem texto precisam de OCR ou transcrição manual. Nada é enviado a provedores.</p></section>
<section><h2>2. Conferir as páginas</h2>
<label for="documents">Documento</label><br><select id="documents"></select>
<button id="original">Baixar original para conferir</button><br>
<label for="reviewer">Seu nome para registrar a revisão</label><br>
<input id="reviewer" maxlength="100" autocomplete="name">
<p>Confira a página no original. Corrija o texto se necessário e aprove ou rejeite cada página.</p>
<div id="pages"></div></section>
<section><h2>3. Pesquisar no que foi aprovado</h2>
<label for="question">Sua pergunta</label><br><input id="question" maxlength="500">
<button id="search">Buscar trechos</button>
<p>Os resultados são evidências para leitura. Termos parecidos não comprovam uma resposta jurídica.</p>
<div id="results"></div></section>
<script nonce="__TOKEN__">
const token="__TOKEN__";
const statusLabel={extracted:"texto extraído",partial:"extração parcial",failed:"extração não concluída",needs_ocr:"precisa de OCR ou transcrição",approved:"aprovada",rejected:"rejeitada"};
const errorLabel={encrypted_pdf:"PDF protegido por senha.",page_limit:"Documento vazio ou acima do limite de páginas.",pdf_parse_failed:"Não foi possível ler este PDF.",parser_timeout:"O tempo de processamento foi excedido.",parser_terminated:"O processamento falhou ou atingiu um limite.",invalid_parser_result:"A extração não retornou um resultado válido."};
let current=null;
const el=(id)=>document.getElementById(id);
function message(text){el("message").textContent=text;}
async function request(path,body){
 const options={headers:{"X-Lab-Token":token}};
 if(body!==undefined){options.method="POST";options.headers["Content-Type"]="application/json";options.body=JSON.stringify(body);}
 const response=await fetch(path,options);
 const data=await response.json();
 if(!response.ok)throw new Error(data.error||"Não foi possível concluir.");
 return data;
}
async function guarded(action){try{await action();}catch(error){message(error.message);}}
async function refresh(selected){
 const docs=await request("/api/documents");
 el("documents").replaceChildren();
 for(const doc of docs){const option=document.createElement("option");option.value=doc.id;option.textContent=doc.original_name+" · "+statusLabel[doc.extraction_status];el("documents").append(option);}
 if(selected)el("documents").value=selected;
 if(el("documents").value)await load();else{current=null;el("pages").textContent="Nenhum documento ainda.";}
}
async function load(){
 current=await request("/api/documents/"+el("documents").value);
 el("pages").replaceChildren();
 const details=document.createElement("details");const summary=document.createElement("summary");summary.textContent="Registro de origem e versão";
 const info=document.createElement("small");info.textContent="SHA256: "+current.source_sha256+" · versão "+current.revision;details.append(summary,info);el("pages").append(details);
 if(current.error){const warning=document.createElement("p");warning.textContent=errorLabel[current.error]||"Extração não concluída.";el("pages").append(warning);}
 for(const page of current.pages){
  const article=document.createElement("article");
  const title=document.createElement("h3");title.textContent="Página "+page.page_number;
  const status=document.createElement("p");status.textContent="Extração: "+statusLabel[page.status]+" · revisão: "+(page.review?statusLabel[page.review.decision]:"pendente");
  const label=document.createElement("label");label.htmlFor="page-"+page.page_number;label.textContent="Texto para conferir e corrigir";
  const text=document.createElement("textarea");text.id=label.htmlFor;text.value=page.text;
  article.append(title,status,label,text);
  for(const [decision,caption] of [["approved","Aprovar esta página"],["rejected","Rejeitar esta página"]]){
   const button=document.createElement("button");button.textContent=caption;
   button.onclick=()=>guarded(async()=>{
    await request("/api/review",{id:current.id,page_number:page.page_number,revision:current.revision,reviewer:el("reviewer").value,decision:decision,text:text.value});
    message("Revisão registrada. A busca usa somente páginas aprovadas.");
    el("results").replaceChildren();await load();
   });
   article.append(button);
  }
  el("pages").append(article);
 }
}
el("upload").onclick=()=>guarded(async()=>{
 const file=el("file").files[0];if(!file)throw new Error("Escolha um PDF.");
 if(file.size>10*1024*1024)throw new Error("O PDF excede 10 MiB.");
 el("upload").disabled=true;message("Extraindo o texto; aguarde.");
 try{
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=()=>reject(new Error("Não foi possível ler o arquivo."));reader.readAsDataURL(file);});
  const doc=await request("/api/ingest",{name:file.name,data:data});
  el("results").replaceChildren();await refresh(doc.id);
  message("Documento registrado. Confira as páginas antes de aprovar.");
 }finally{el("upload").disabled=false;}
});
el("documents").onchange=()=>guarded(load);
el("original").onclick=()=>guarded(async()=>{
 if(!current)throw new Error("Escolha um documento.");
 const response=await fetch("/api/original/"+current.id,{headers:{"X-Lab-Token":token}});
 if(!response.ok)throw new Error("Original indisponível.");
 const url=URL.createObjectURL(await response.blob());const link=document.createElement("a");
 link.href=url;link.download=current.original_name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
el("search").onclick=()=>guarded(async()=>{
 const matches=await request("/api/search",{question:el("question").value});el("results").replaceChildren();
 if(!matches.length){el("results").textContent="Não encontrei evidência aprovada para essa pergunta.";return;}
 for(const match of matches){const article=document.createElement("article");const title=document.createElement("h3");title.textContent=match.citation;const text=document.createElement("pre");text.textContent=match.text;article.append(title,text);el("results").append(article);}
});
guarded(()=>refresh());
</script></body></html>"""
    return template.replace("__TOKEN__", token)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, port=8001):
        self.store = store
        self.token = secrets.token_hex(32)
        self.work = threading.BoundedSemaphore(1)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Não escrever nomes, perguntas ou documentos no log HTTP.

    def allowed(self, protected=True):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in hosts}:
            return False
        candidate = self.headers.get("X-Lab-Token", "")
        return not protected or (
            len(candidate) == 64 and candidate.isascii()
            and secrets.compare_digest(candidate, self.server.token)
        )

    def respond(self, status, body, mime="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'nonce-{self.server.token}'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if mime == "application/pdf":
            self.send_header("Content-Disposition", 'attachment; filename="original.pdf"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed(protected=self.path != "/"):
            return self.respond(403, {"error": "Acesso local inválido."})
        try:
            if self.path == "/":
                return self.respond(200, page(self.server.token).encode(), "text/html; charset=utf-8")
            if self.path == "/api/documents":
                docs = self.server.store.list()
                return self.respond(200, [{k: doc[k] for k in ("id", "original_name", "extraction_status", "revision")} for doc in docs])
            if self.path.startswith("/api/documents/"):
                return self.respond(200, self.server.store.get(self.path.removeprefix("/api/documents/")))
            if self.path.startswith("/api/original/"):
                return self.respond(200, self.server.store.original(self.path.removeprefix("/api/original/")), "application/pdf")
            self.respond(404, {"error": "Página não encontrada."})
        except LabError as error:
            self.respond(400, {"error": str(error)})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error": "Acesso local inválido."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES or self.headers.get("Transfer-Encoding"):
                return self.respond(413, {"error": "Corpo ausente ou acima do limite."})
            if self.headers.get("Content-Type") != "application/json":
                return self.respond(415, {"error": "Envie JSON."})
        except ValueError:
            return self.respond(400, {"error": "Tamanho inválido."})
        if not self.server.work.acquire(blocking=False):
            return self.respond(429, {"error": "Uma operação está em andamento. Aguarde."})
        try:
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise LabError("Objeto de entrada inválido.")
            if self.path == "/api/ingest":
                data = base64.b64decode(body["data"], validate=True)
                result = self.server.store.ingest(data, body["name"])
            elif self.path == "/api/review":
                result = self.server.store.review(body["id"], body["page_number"], body["revision"], body["reviewer"], body["decision"], body.get("text"))
            elif self.path == "/api/search":
                result = search(self.server.store, body["question"])
            else:
                return self.respond(404, {"error": "Operação não encontrada."})
            self.respond(200, result)
        except LabError as error:
            self.respond(400, {"error": str(error)})
        except (ValueError, TypeError, KeyError, binascii.Error, RecursionError):
            self.respond(400, {"error": "Entrada inválida."})
        except OSError:
            self.close_connection = True
        finally:
            self.server.work.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Laboratório local de documentos.")
    parser.add_argument("--pasta", default=".documentos")
    parser.add_argument("--porta", type=int, default=8001)
    args = parser.parse_args()
    server = Server(Store(args.pasta), args.porta)
    print(f"Abra http://127.0.0.1:{server.server_port} — Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
