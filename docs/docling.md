# Docling opcional no contrato PDF existente

Este incremento depende do PR #1 (`feat/ingestao-pdf-revisavel`), sem reimplementar
upload, SQLite, hashes, revisão ou busca. `Store.ingest(..., parser="docling",
artifacts="/caminho/local")` e a CLI selecionam o adaptador; a interface web
continua usando pypdf por padrão. Os documentos Docling aparecem na mesma revisão.

```sh
# Em venv opcional separado, Python 3.11/3.12:
python -m pip install --require-hashes -r requirements-pdf.txt
python -m pip install -r requirements-docling.txt
# Provisione os modelos localmente, fora da ingestão; essa etapa precisa de rede:
docling-tools models download layout -o /caminho/modelos
python -m ingestion ingerir contrato_demo.pdf --parser docling --artefatos /caminho/modelos
# Após provisionar os pesos, validação real opcional:
DOCLING_ARTIFACTS=/caminho/modelos python -m unittest -v test_docling
```

Versão do motor: Docling 2.55.1, API consultada no código dessa tag. Não há lock de
todas as transitivas ou garantia de compatibilidade com versões futuras; valide
em ambiente separado antes de usar. Instalar Docling é pesado e não integra o CI
padrão. O teste real exige explicitamente modelos locais; nunca substitui ausência
de modelos por um teste falso de sucesso.

Padrões Docling: 10 MiB, 50 páginas, 100 mil caracteres/página, 500 mil/documento,
120 segundos de subprocesso (inclui importação, pré-validação e conversão), 4 GiB
de espaço de endereçamento no Linux. O limite nativo pypdf permanece 20 s/512 MiB.
O hash dos artefatos é calculado antes de iniciar o subprocesso; o prazo do parser
não cobre essa leitura do diretório local confiável. Não modifique os pesos durante
a ingestão. Sem diretório local não vazio ou dependência, a operação é recusada.

O manifesto inclui versão/configuração do parser, hash do conjunto de artefatos,
limites, SHA-256 do PDF, página e método. A identidade depende dessa configuração:
pypdf e Docling não compartilham aprovações; reenvio idêntico preserva revisão.
Texto novo sempre começa pendente. A proveniência permite reproduzir a extração,
mas não prova qualidade ou autenticidade jurídica.

O adaptador usa `DocumentConverter` com PDF permitido e exportação Markdown por
página. OCR, estrutura de tabelas e serviços remotos ficam desabilitados. Exige
conversão completa e conjunto exato de páginas. Texto excessivo é falha explícita;
não trunca silenciosamente. PDFs criptografados/fora do limite são recusados antes
de carregar modelos. Layout precisa dos pesos locais, mesmo sem OCR.

`HF_HUB_OFFLINE=1` e telemetria HF desabilitada são auxiliares. Não se afirma que
flags ou subprocesso sejam sandbox ou garantia universal de ausência de rede.
Para documentos hostis, isole o runtime no sistema operacional. Este incremento
não executa OCR, não chama API paga e não baixa pesos durante a ingestão.

## Evidência e limites desta execução

Quatro testes de contrato com doubles explícitos passaram: seleção/configuração,
identidade/hash de pesos, limites e timeout, páginas/falhas, revisão e busca no
Store real. O pacote Docling foi instalado e seus imports reais foram verificados.
A conversão com pesos não foi validada: o provisionamento no Hugging Face recebeu
403 do proxy deste executor. O teste opcional fica marcado como não executado.
Não há métricas de qualidade Docling ou alegação de melhoria sobre pypdf.

O baseline TXT continua 5/7 no corpus original. As falhas conhecidas e expectativas
não foram alteradas para obter testes verdes. O corpus PDF nativo continua 7/7;
esta taxa não se aplica ao Docling.

## Créditos

Adaptador e testes originais deste projeto, com assistência de IA.
[Docling](https://github.com/docling-project/docling/tree/v2.55.1) é dos autores
upstream (MIT); os pesos têm seus próprios termos. Nenhum trecho do motor foi
copiado como autoria do usuário. As licenças dos pacotes permanecem nos pacotes.
