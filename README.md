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

Requer Python 3. Esta versão não usa bibliotecas externas.

Na pasta principal do projeto, execute:

```bash
python exemplos/app.py
```

Digite uma pergunta, por exemplo: `Qual é o prazo?`

O programa mostrará o trecho encontrado e o nome do documento de origem.

Para executar as verificações manualmente:

```bash
python test_busca.py
```

Os testes também rodam automaticamente na aba Ações a cada alteração.

## Estado atual

- Busca por palavras com indicação da fonte: implementada e verificada.
- Respostas geradas por modelo de IA: ainda não implementadas.
- Interface para usuários: ainda não implementada.
