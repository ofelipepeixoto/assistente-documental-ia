# Provider Ollama opcional: laboratório local

Esta integração é código autoral do laboratório. Não copia o código do motor
Ollama, não instala servidor, não baixa pesos e não libera o caminho OpenAI
de `resposta_ia.py`, bloqueado até autorização e budget persistentes. É uma CLI separada: a busca continua funcionando sem LLM.

## Uso explícito

Busca dos exemplos TXT, sem chamadas de inferência, inclusive com OPENAI_API_KEY:
```bash
python resposta_ollama.py "Qual é o prazo?"
```

Busca de páginas PDF já aprovadas no workspace existente, sem LLM:
```bash
python resposta_ollama.py "vigência" --workspace .documentos
```

Somente após o operador instalar e validar um servidor/modelo local por conta
própria, o opt-in exige provider **e** modelo. Substitua NOME_LOCAL:TAG por um
modelo realmente disponível e permitido; este comando não instala nada:
```bash
python resposta_ollama.py "vigência" --workspace .documentos \
  --provider ollama --model NOME_LOCAL:TAG --timeout 20
```

`--endpoint` admite somente HTTP com IP literal `127.0.0.1` ou `[::1]`,
porta 1–65535 e caminho base. Default: `http://127.0.0.1:11434`.
DNS, localhost, IP privado/remoto, credenciais, HTTPS, query, fragment e caminhos
arbitrários são rejeitados. O cliente sempre chama `POST /api/chat`; ignora
proxies de ambiente por usar http.client, não segue redirects, não faz retry,
streaming, tool execution ou fallback pago.

**Endpoint loopback não comprova inferência offline.** Um daemon local pode
encaminhar aliases/modelos à nuvem. Tags terminadas em :cloud/-cloud são
rejeitadas pelo cliente, mas essa verificação não detecta todos os aliases.
O operador precisa confirmar o modelo efetivamente carregado, sua licença,
sua política de dados e configurar/verificar `OLLAMA_NO_CLOUD=1` no daemon
antes de dados reais. Consulte [a FAQ oficial](https://docs.ollama.com/faq)
e [a autenticação oficial](https://docs.ollama.com/api/authentication).
A API local do motor não fornece autenticação de produto; não publique 11434.

## Evidências, revisão e limites

- Sem resultado de busca: resposta de abstention e **zero chamadas LLM/HTTP**.
- Sem provider explícito: somente evidências, sem cliente LLM.
- PDF: ingestion.search retorna somente páginas aprovadas, preservando documento,
  revisão, página, hashes de origem/texto e citação. A integração não aprova
  páginas; workspace ausente é erro e não cria diretório/banco.
- TXT: preserva o trecho/fonte da busca lexical existente; não transforma
  correspondência de palavras em prova semântica.
- O resultado do modelo é identificado como rascunho probabilístico para revisão
  humana. A seção de evidências é anexada pelo programa, não escolhida pelo LLM.
  Isso não comprova que cada frase/citação do rascunho seja verdadeira ou
  suportada. Prompt injection e alucinação continuam possíveis; o operador deve
  conferir afirmações e citações antes de usar qualquer peça jurídica.
- Pergunta: até 500 caracteres; evidência: até 8.000 caracteres; request:
  até 24 KiB; response: até 64 KiB; saída textual: até 16.000 caracteres.
  Não há truncamento silencioso no cliente: acima do limite é erro.
- Deadline total: default 20 s, configurável entre 0,1 e 30 s, incluindo conexão
  e leitura; socket é interrompido ao vencer, mesmo com corpo lento.
- Uma requisição solicita num_ctx=4096, no máximo 512 tokens de saída,
  temperature=0 e keep_alive=0. O servidor/modelo precisa respeitar esses
  parâmetros; não são benchmark, SLA nem garantia de determinismo/qualidade.
  Limites de bytes/caracteres não medem tokens exatamente. Um modelo/servidor
  pode truncar contexto; isso deve ser avaliado no hardware/modelo escolhido.
- Resposta incompleta, JSON malformado, UTF-8 inválido, ferramenta, erro HTTP,
  redirect, excesso de tamanho ou timeout falha sem retry e sem exibir o corpo
  interno. Não há servidor web, auth de tenant, cobrança ou deploy nesta CLI.

Só use dados fictícios até validar licença dos pesos, RAM/CPU/GPU,
isolamento de processo, privacidade e custo por resposta aceita. Na VPS
compartilhada, preservar margem para Hermes; nenhum modelo/benchmark real foi
executado nesta implementação.

## Verificação automatizada

```bash
python -m unittest test_ollama -v
python -m unittest discover -v
ruff check ollama_provider.py resposta_ollama.py test_ollama.py
```

A suite usa respostas HTTP simuladas e um servidor fictício de teste em
loopback para o deadline; não usa Ollama, GPU, conta de provedor ou peso.
Testa sucesso/erro/timeout/redirect, tamanho, JSON/UTF-8, URLs não confiáveis,
opt-in, busca sem LLM, abstention sem chamada e páginas PDF aprovadas com
citação/hash. A qualidade do modelo e sua inferência offline real não foram
homologadas.

## Decisão de dependências

**LangChain adiado.** Um provider com uma operação HTTP e contratos locais já
é coberto pela biblioteca padrão Python. Adicionar framework agora aumentaria
dependências/superfície de atualização sem resolver um requisito demonstrado.
A interface generate(question, evidence, config) permite trocar a implementação
se futuros requisitos medidos exigirem mais provedores ou orquestração. Não há
roteador multi-modelo, agente autônomo ou MCP adicional neste passo.
