"""Demonstração local da busca documental; nenhuma chamada à API externa."""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from exemplos.app import buscar


def pagina(pergunta="", resultado=""):
    pergunta_segura = escape(pergunta, quote=True)
    bloco = f"<h2>Trecho encontrado</h2><pre>{escape(resultado)}</pre>" if resultado else ""
    return ("<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Busca documental — demonstração</title>"
            "<style>body{font:18px system-ui;max-width:760px;margin:3rem auto;padding:0 1rem;line-height:1.5}"
            "input,button{font:inherit;padding:.6rem}input{width:70%}pre{white-space:pre-wrap;background:#f2f4f7;padding:1rem}"
            "</style><h1>Busca em contrato fictício</h1>"
            "<p>Esta demonstração exibe trechos do documento. Confira a fonte e revise qualquer interpretação.</p>"
            f"<form method='post'><label for='pergunta'>Sua pergunta</label><br>"
            f"<input id='pergunta' name='pergunta' maxlength='500' required value='{pergunta_segura}'>"
            "<button type='submit'>Buscar</button></form>" + bloco + "</html>")


class Handler(BaseHTTPRequestHandler):
    def responder(self, status, corpo):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path != "/":
            return self.responder(404, "Página não encontrada")
        self.responder(200, pagina())

    def do_POST(self):
        if self.path != "/":
            return self.responder(404, "Página não encontrada")
        tamanho = int(self.headers.get("Content-Length", "0"))
        if tamanho > 4096:
            return self.responder(413, "Pergunta muito longa")
        campos = parse_qs(self.rfile.read(tamanho).decode("utf-8"))
        pergunta = campos.get("pergunta", [""])[0].strip()[:500]
        self.responder(200, pagina(pergunta, buscar(pergunta) if pergunta else "Digite uma pergunta."))


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Abra http://127.0.0.1:8000 (Ctrl+C para encerrar)")
    servidor.serve_forever()
