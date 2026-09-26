# Assistente documental com IA

Protótipo em desenvolvimento para ajudar na consulta de documentos jurídicos fictícios, apresentando as fontes usadas em cada resposta.

## Objetivo

Permitir que uma pessoa faça uma pergunta sobre documentos e encontre os trechos relevantes antes de preparar um rascunho para revisão humana.

## Fluxo previsto

1. Adicionar documentos de exemplo, sem dados de clientes ou processos reais.
2. Buscar os trechos relacionados à pergunta.
3. Produzir uma resposta com referência aos documentos consultados.
4. Encaminhar o resultado para revisão humana.

## Estado do projeto

Em desenvolvimento. Ainda não há aplicação funcional nem resultados de avaliação publicados.

## Critérios para a primeira versão

- Respostas acompanhadas dos trechos que as fundamentam.
- Indicação clara quando os documentos não contiverem a resposta.
- Nenhum envio ou publicação automática de peças.
- Testes com perguntas e respostas esperadas, usando dados fictícios.
## Como executar

Requer Python 3. Não há bibliotecas externas nesta primeira versão.

Na pasta principal do projeto, execute:

```bash
python exemplos/app.py
