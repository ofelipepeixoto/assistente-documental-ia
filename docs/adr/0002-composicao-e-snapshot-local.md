# ADR 0002 — Composição explícita e snapshots locais

Status: integração de laboratório. Data: 2026-10-03.

## Decisão

A branch integra por merges reais as três linhas antes separadas: PDF revisável
`546cc61642832dbc7f420c5cdf1f9d7011654508`, Docling opcional
`60a549d640e79557a6255aea86dcd8d2ce33f075` e export de evidências
`d8cfc62b1a66995e9ddef8dcb59d98f6b3c82ecb`, sobre main
`22b96bd90bde737cfc5974f0c5d73cf1529f0c73`. Docling e export eram incrementos
irmãos; nenhum era presumido dentro do outro. Os commits e sua proveniência
permanecem ancestrais da integração.

Originais e manifestos escolhidos agora são lidos numa mesma transação SQLite.
O JSON exportado pode ser comparado contra revisão corrente, hashes, página e
decisão de revisão do Store com `validate_local_snapshot`. Sua política de
seleção vem do consumidor, não dos rótulos do JSON. Alterações posteriores à
leitura tornam o snapshot histórico e exigem nova verificação.

Identidade segue não verificada. Não existe login nesta interface loopback;
rótulo local, token de sessão e hash não autenticam um profissional. O adapter
força `identity_verified=False` e não concede autorização para efeitos externos.

A geração OpenAI legada, liberada apenas por variável de chave, foi bloqueada.
Ela preserva busca e abstenção. Não são criados orçamento ou tarifas fictícias;
o gate de runtime continua em PLANO_IA.md. Ollama é caminho opcional separado,
sem inferência real executada ou garantia de daemon offline.

## Validação e limites

Testes com PDFs fictícios cobrem export completo, replay após rejeição/correção,
hash recomputado de registro adulterado, revisão/escopo, original corrompido e
ausência de promoção de identidade. Testes padrão mantêm TXT e contrato Docling.
Docling com pesos e respostas jurídicas de LLM continuam não homologados.

A suíte completa local passou com o commit do kit indicado em
requirements-evidence.txt, incluindo o fluxo de browser. O executor precisou
usar Chromium 153.0.8010.0 temporário fora do repositório após o download padrão
Playwright retornar um arquivo inválido. Esse runtime de teste não é dependência
ou deploy do produto; o Actions mantém seu browser padrão fixado pelo Playwright.

Não há deploy, migração destrutiva, banco remoto, novo framework ou novo
repositório. Dependências opcionais preservam atribuição dos respectivos
autores e licenças; adaptar o contrato não transfere autoria dos motores.

## Gates posteriores

Produção exige consumidor autenticado, isolamento por cliente, revisão atribuída
a principal verificado, parser isolado, retenção/backup testados, corpus PT-BR
representativo e integração do budget antes de habilitar IA paga. A biblioteca
de evidências e esta validação local não implementam esses controles.
