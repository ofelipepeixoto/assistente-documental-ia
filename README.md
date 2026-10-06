# Assistente documental com IA

Laboratório para consultar documentos com fontes e revisão humana. A nova etapa PDF funciona localmente: **abrir arquivo → conferir páginas → aprovar ou corrigir → pesquisar trechos citados**.

Há duas interfaces web locais: PDF em `documentos_web.py` (porta 8001) e TXT em `demo_web.py` (porta 8000). Os comandos de instalação e execução de cada caminho estão abaixo.

Use exemplos fictícios ou documentos que você tem autorização para processar. Não há publicação de peças, aconselhamento jurídico ou aprovação automática.

## Testar a interface PDF

Requer Python 3.11 ou 3.12. Na pasta do projeto:

**Windows / PowerShell**

~~~powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-pdf.txt
python documentos_web.py
~~~

**Linux / macOS**

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-pdf.txt
python documentos_web.py
~~~

Abra **http://127.0.0.1:8001** no navegador. Para criar um exemplo fictício, execute em outro terminal com o mesmo ambiente:

~~~bash
python -m avaliacao.pdf_fixtures
~~~

Escolha contrato_demo.pdf na tela. Confira o original, informe seu nome para o registro local e aprove, corrija ou rejeite cada página. Pesquise, por exemplo, “pagamento mensal” ou “prazo de vigência”. Uma página pendente ou rejeitada não entra nos resultados. O botão de download permite conferir o PDF original.

O servidor escuta somente em 127.0.0.1. Encerre com Ctrl+C. O token de sessão e as verificações de origem protegem o fluxo local; **não substituem login, identidade verificada ou isolamento entre clientes**. Não exponha esta aplicação pela internet ou por túnel. O nome do revisor é autodeclarado.

## O que foi implementado

- Extração de texto de PDFs digitais por página, com pypdf fixado por versão e hash.
- Original e manifesto persistidos em SQLite local, dentro de .documentos/ (ignorado pelo Git).
- Identificador por hash de origem + versão/configuração do parser; reenvio igual reutiliza o registro e preserva revisões.
- Falhas e páginas que precisam de OCR são explícitas, sem transformar descarte em sucesso.
- Revisão ligada ao hash do texto e do original; versão desatualizada é recusada.
- Correção preserva o texto extraído inicialmente e registra novo hash/decisão.
- Busca lexical conservadora somente no conteúdo aprovado, com documento, página e hashes de evidência.
- Interface em português, CLI, testes e avaliação sintética reproduzível.
- Adaptador opcional para importar saída local do olmOCR; não instala pesos, executa GPU ou chama provedores.

O caminho PDF não utiliza OpenAI, não lê chave de API e não envia documentos a serviços externos. O script opcional resposta_ia.py permanece separado.

## Limites e segurança

Padrões por documento: **10 MiB, 50 páginas, 100 mil caracteres por página, 500 mil por documento e 20 segundos de parser**. Workspace: até 50 documentos ou 128 MiB lógicos no banco; a cota lógica não é limite físico do arquivo SQLite. Não há ingestão pública de TAR/ZIP. PDFs protegidos por senha não são abertos.

O parser roda em subprocesso com prazo máximo. No Linux aplica limites de memória (512 MiB), CPU e arquivo de saída; em Windows/macOS esses limites de recurso não são aplicados e isso aparece no manifesto. **Subprocesso não é uma sandbox completa.** Antes de aceitar arquivos hostis ou dados de clientes em produção, exigir isolamento de runtime, autenticação, política de retenção e testes de autorização.

A extração pode perder estrutura, campos ou texto. Páginas com pouco texto são sinalizadas, mas esse indicador não mede precisão e não distingue perfeitamente scan, página vazia e conteúdo ilegível. Revisão humana continua obrigatória. A busca retorna evidências, não uma interpretação jurídica; todos os termos relevantes precisam estar na página e sinônimos podem gerar abstenção.

Documentos e banco são ignorados pelo Git; não os force para o repositório. O banco não é criptografado. O operador é responsável pelas permissões, retenção, backups e exclusão da workspace local. O serviço não autentica revisores nem oferece operação multitenant.

## olmOCR opcional

O contrato é a importação de **um registro Dolma JSON/JSONL** já produzido em ambiente externo autorizado. Ela valida fonte, hash declarado de origem, número de páginas, offsets, limites e ausência de fallback. Exige nome do modelo e revisão fixa (SHA de 40 caracteres). Nova importação invalida as aprovações; o conteúdo só fica disponível para busca após nova revisão.

Veja [docs/olmocr.md](docs/olmocr.md). **A inferência olmOCR não foi executada ou avaliada nesta entrega.** Não há dependência de vLLM/Transformers no laboratório. Código/adaptador original deste projeto não transfere a autoria do motor Ai2; os termos do motor, pesos e dados continuam independentes.

## Verificações reproduzíveis

~~~bash
python -m pip install --no-deps -r requirements-evidence.txt
python -m unittest discover -v
python avaliar_pdf.py --strict
python avaliar.py
~~~

A suíte completa inclui a exportação opcional e exige o kit fixado no comando acima. A busca, ingestão e revisão continuam funcionando sem o kit. O teste de browser é ignorado localmente salvo habilitação explícita. Para executar a mesma verificação do CI:

~~~bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
# Linux/macOS:
PDF_BROWSER_TESTS=1 python -m unittest discover -v
# PowerShell: $env:PDF_BROWSER_TESTS="1"; python -m unittest discover -v
~~~

Em Linux sem dependências do browser, instalar com playwright install --with-deps chromium em ambiente de testes apropriado.

[avaliacao/resultados_pdf.json](avaliacao/resultados_pdf.json) registra **7/7 casos**, CER/WER normalizados iguais a zero no PDF digital sintético de três páginas. O corpus cobre acentos, data, moeda, uma cláusula negativa e duas abstenções. Isso mede apenas esse exemplo controlado: **não comprova qualidade em scans, tabelas, documentos reais, inferência GPU ou respostas jurídicas**. O teste de revisão usa uma identidade fictícia; não equivale a uma avaliação por especialistas.

O baseline anterior TXT continua **5/7** no corpus anterior; não comparar diretamente as duas taxas, pois os documentos e casos diferem. GitHub Actions verifica Python 3.11/3.12, testes sem chave, browser, lint e alertas conhecidos da dependência PDF.

## Consulta TXT existente

A busca original não precisa instalar dependências:

~~~bash
python exemplos/app.py
python demo_web.py
~~~

A interface TXT fica em http://127.0.0.1:8000 e continua independente da interface PDF. Seu baseline e expectativas estão em avaliacao/casos.json.

## Busca TXT e geração paga bloqueada

`resposta_ia.py` consulta os arquivos TXT de `exemplos/`; ele não consulta o
SQLite nem as páginas PDF aprovadas. Sem `OPENAI_API_KEY`, devolve o trecho e a
fonte encontrados, sem instalar ou importar `openai`. Perguntas sem trecho
retornam abstenção.

```bash
python resposta_ia.py
```

Digite `Qual é o prazo?`. Sem chave, a resposta começa com `Chave de API não
configurada` e inclui a fonte `contrato_ficticio.txt` e a cláusula 2.

**Uma chave presente também não libera API paga nesta integração.** O programa
mostra as evidências e o motivo do bloqueio. O caminho antigo, habilitado somente
pela chave, foi removido: falta integrar autorização do consumidor, orçamento
persistente, reserva atômica antes da chamada e reconciliação após o resultado.
Nenhum valor de orçamento ou tarifa foi inventado. Flags ou nome autodeclarado
não substituem esses controles. Nenhum documento ou pergunta é enviado à OpenAI
por este script. Não coloque chaves no chat, código, argumentos ou commits.

## Ollama local opcional

`resposta_ollama.py "Qual é o prazo?"` retorna somente evidências. Inferência
local exige provider e modelo explicitamente selecionados; consulte
[docs/ollama.md](docs/ollama.md). O cliente restringe o transporte ao loopback,
mas não prova que o daemon/modelo não encaminha dados à nuvem. Só use exemplos
fictícios até validar isolamento, licença e configuração do executor.
Nenhuma inferência Ollama ou GPU foi executada nesta integração.

## Exportação opcional de evidências

O novo modo `--trechos` preserva a página revisada e exporta referências de
janela verificáveis no Store atual. Veja [contrato e limites](docs/trechos.md).

Para exportar um snapshot local das páginas aprovadas:

~~~bash
python -m pip install --no-deps -r requirements-evidence.txt
python exportar_evidencias.py --help
~~~

O commit exato da biblioteca autoral fica fixado em `requirements-evidence.txt`,
também usado pelo CI. A biblioteca vem do repositório separado
[ofelipepeixoto/radar-evidence-kit](https://github.com/ofelipepeixoto/radar-evidence-kit)
com autoria de Carlos Felipe e licença MIT. A instalação pode acessar a rede; a exportação é local.
O adapter lê originais e manifestos em uma transação SQLite e valida texto e revisão,
preserva o nome local como rótulo e mantém identidade não verificada.
Veja [docs/evidencias.md](docs/evidencias.md) para selecionar documentos/revisões
e guardar o JSON com texto integral. Escopo e snapshot não concedem autorização.

## Próximos critérios de evolução

1. Corpus PT-BR representativo e autorizado, incluindo scans/tabelas e campos críticos conferidos.
2. Escolha de executor/provedor e orçamento antes de rodar inferência real.
3. Runtime OCR com versões compatíveis corrigidas, revisões/digests fixos e nova análise de dependências.
4. Auth e revisão verificadas, isolamento por cliente, retenção e recuperação antes de serviço remoto.
5. Avaliação separada de extração, recuperação, citação, geração e abstenção.

A decisão de arquitetura está em [docs/adr/0001-ingestao-pdf-local.md](docs/adr/0001-ingestao-pdf-local.md).

## Docling opcional

O adaptador Docling reutiliza este mesmo fluxo de revisão PDF pela CLI, com pesos
locais, identidade por parser/configuração e limites explícitos. Veja
[docs/docling.md](docs/docling.md) para instalação, execução, créditos e limitações.
O teste de conversão real exige pesos locais; nesta execução seu download foi
bloqueado por HTTP 403. Testes de contrato não comprovam qualidade de extração.
