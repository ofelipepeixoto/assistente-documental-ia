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

A busca local é funcional. `resposta_ia.py` também oferece geração opcional de rascunho pela API quando há trecho e chave configurada; esse caminho ainda não tem avaliação de qualidade publicada. Sem chave, retorna apenas a busca e a fonte. Ainda não há interface gráfica nem envio automático de peças.

## Critérios para a primeira versão

- Respostas acompanhadas dos trechos que as fundamentam.
- Indicação clara quando os documentos não contiverem a resposta.
- Nenhum envio ou publicação automática de peças.
- Testes com perguntas e respostas esperadas, usando dados fictícios.
## Como executar

Requer Python 3. A busca local não usa bibliotecas externas.

Na pasta principal do projeto, execute:

```bash
python exemplos/app.py
```

Digite uma pergunta, por exemplo: `Qual é o prazo?`

O programa mostrará o trecho encontrado e o nome do documento de origem.

Para executar as verificações manualmente:

```bash
python -m unittest -v test_busca.py test_resposta_ia.py test_avaliacao_demo.py
```

Os testes também rodam automaticamente na aba Ações a cada alteração.

## Resposta opcional com IA

O script `resposta_ia.py` usa o trecho da busca para pedir um rascunho ao modelo. Para executar sem chave, basta `python resposta_ia.py`: ele mostra a fonte e o trecho, sem instalar ou chamar a biblioteca `openai`. Perguntas sem correspondência mostram um aviso, mesmo com chave. Para habilitar a geração, crie um ambiente virtual e instale a dependência:

**Windows (PowerShell):**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install openai
python resposta_ia.py
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install openai
python resposta_ia.py
```

Configure `OPENAI_API_KEY` apenas no ambiente local caso queira usar a API; não é necessária nos testes ou no GitHub Actions. `OPENAI_MODEL` é opcional e o código usa `gpt-5-mini` como padrão. A chamada pode gerar custos e envia a pergunta e o trecho ao provedor. Não inclua chaves ou documentos reais de clientes no repositório. Um rascunho exige revisão humana e não constitui aconselhamento jurídico.

## Limites

A busca seleciona um único trecho por coincidência de palavras; não garante que a cláusula responda à pergunta. Não há avaliação publicada das respostas do modelo, interface gráfica ou publicação de peças. Os testes automatizados cobrem a busca, a fonte, a ausência de correspondência e o caminho sem chave, sem chamar API externa.

## Avaliação reproduzível

Execute `python avaliar.py` para comparar a cláusula encontrada com sete perguntas sobre o contrato fictício. O baseline medido foi **5/7 acertos**: a busca não encontrou a data de início quando a pergunta usou «começa» e mostrou a cláusula de rescisão para uma pergunta sobre multa, embora o contrato não informe multa. Encontrar um trecho relacionado **não prova** que ele responde à pergunta. O arquivo `avaliacao/casos.json` contém as expectativas; os testes impedem que o baseline seja descrito como sucesso completo.

## Interface local de demonstração

Execute `python demo_web.py` e abra `http://127.0.0.1:8000` no navegador. A página faz apenas a busca local e mostra o trecho e a fonte; não usa a API nem gera peça jurídica. O servidor escuta somente no computador local (`127.0.0.1`) e é uma demonstração, não um serviço de produção. Encerre com Ctrl+C.
