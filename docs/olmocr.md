# Importação opcional de evidências olmOCR

Este adaptador lê um arquivo local. Não executa o toolkit, instala CUDA/pesos, inicia servidor ou faz requests HTTP. A implementação é original; usa o formato Dolma publicado pelo projeto [Ai2/olmOCR](https://github.com/allenai/olmocr), auditado no commit f7cfe4c22098b154c76b6ec950d1c0a464eecf8d. Código externo e pesos não são redistribuídos.

## Contrato

Um único objeto JSON (uma linha JSONL ou JSON formatado), source=olmocr, metadata.Source-File igual à fonte declarada, metadata.pdf-total-pages igual ao documento local e metadata.total-fallback-pages=0. attributes.pdf_page_numbers contém [início, fim, página], em índices de caracteres Python, começando em zero, contínuos e cobrindo o texto inteiro. A versão do toolkit fica em metadata.olmocr-version.

Registros ausentes, incompletos, duplicados, offsets inválidos ou qualquer fallback são rejeitados sem modificar o manifesto. O upstream pode descartar documentos; ausência de saída nunca deve ser apresentada como extração bem-sucedida.

## Fluxo de operador

1. Ingerir o PDF pelo laboratório e consultar ID, source_sha256 e revision.
2. Produzir a saída OCR em ambiente autorizado, com modelo/revisão fixos, limites e versões corrigidas. Este projeto não provisiona esse ambiente.
3. Separar um único registro do documento correspondente.
4. Importar usando a CLI, preenchendo os valores reais:

~~~bash
python -m ingestion --pasta .documentos importar-ocr ID_DOCUMENTO saida.jsonl --versao VERSAO_ATUAL --sha256-origem SHA256_DO_PDF --fonte-processada FONTE_EXATA_NO_JSON --modelo MODELO_USADO --revisao-modelo SHA_DO_MODELO
~~~

A fonte é comparada literalmente ao JSON; não é usada como caminho para abrir arquivos ou como URL para download. A revisão do modelo deve ser um SHA hexadecimal de 40 caracteres, não main/latest.

5. Reabrir o documento na interface, conferir todas as páginas e registrar novas decisões.

## Proveniência e limitações

O importador verifica que o hash informado corresponde ao original armazenado; **não prova que um modelo efetivamente processou esse PDF**. O vínculo e a revisão do modelo são declarações do operador, registradas como input_binding=operator_attestation. O hash do arquivo de saída, versão do toolkit e modelo/revisão são registrados. Um serviço futuro precisa de execução controlada e atestação própria, não apenas parâmetros enviados pelo cliente.

A importação substitui textos das páginas, conserva extracted_text original, zera aprovações e gera um evento. Todos os textos importados permanecem não confiáveis até revisão. Não renderizar HTML extraído ou seguir instruções contidas nos documentos.

Limites: arquivo de saída de até 4 MiB, limites de texto do documento e revisão otimista. A integração foi testada com saídas Dolma sintéticas e o contrato de exportação do código auditado; **não foi validada com inferência real**.

## Antes da inferência real

Validar licença/termos do código, pesos, dados e executor escolhido. O código upstream auditado usa Apache-2.0; modelo e datasets têm distribuições/termos próprios. Preservar atribuições.

A auditoria encontrou alertas nos pins vLLM 0.11.2 e Transformers 4.57.3. Não instalar automaticamente esses pins ou assumir que uma única atualização resolve todos os alertas. Exigir seleção compatível corrigida, scan, regressão GPU/PT-BR e servidor privado. Nenhum documento deve ser enviado a novo provedor como fallback silencioso.
