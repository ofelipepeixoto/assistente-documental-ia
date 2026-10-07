# Memória revisável local — B / STUDY

Autoria Carlos Felipe com assistência de IA, MIT. Referência conceitual:
`EXXETA/exxperts@df52b073e5328221645bc0b0aeb63419b9bd4fa5`, sem código
copiado/runtime integrado. O contrato é original no Evidence Kit, PR #7.
Pins e versões de Evidence já usadas pelos fluxos existentes permanecem próprios.

## Usar o piloto

Em Python 3.11/3.12, venv privado:

```bash
python -m pip install --require-hashes -r requirements-pdf.txt
python -m pip install --no-deps -r requirements-memory.txt
python documentos_web.py --pasta .documentos
# Em outro terminal, mesma pasta e venv:
python memoria_web.py --pasta .documentos
```

Abrir interfaces loopback exibidas. Na documental (8001), ingerir PDF fictício
ou autorizado, conferir original e aprovar páginas. Na memória (8002), ler as
fontes, escrever nota e selecionar 1–8 páginas aprovadas. Criar proposta,
conferir texto completo e fontes e aprovar/rejeitar com nome distinto. Para
corrigir, criar nova proposta com mesmo identificador; não altera aprovação
anterior até a nova revisão. Desfazer retorna aprovação anterior elegível.
Esquecer exige confirmação e recibo da versão mais recente, inclusive após undo.
Notas rejeitadas ou retiradas ficam na área de gestão para correção/descarte.

Validade fixa de sete dias; notas vencidas não aparecem na leitura aprovada.
Ao iniciar servidor, `purge_expired` remove payload vencido. Durante uma sessão
longa, vencidas ficam na gestão até descarte/reinício. Não há cron, provider,
modelo, embedding, execução de instruções, n8n ou Supabase.

## Escopo, identidade e concorrência

Backend fixa `local-operator/documental-lab`; o Store inteiro é workspace de um
operador. Rótulos não representam isolamento físico de tenants nem autenticação.
Campos de escopo, identidade e status enviados pelo cliente são recusados.
Revisão documental e de nota sempre preservam `identity_verified=False`.
Nomes diferentes não comprovam pessoas diferentes; modo local é explícito.

Cada operação exporta páginas aprovadas e verifica bytes/hash do PDF original.
IDs cobrem revisão, texto, fonte e página. Alterar, rejeitar ou retirar qualquer
fonte bloqueia a próxima leitura/aprovação da nota. Um bloqueio SQLite
`BEGIN IMMEDIATE` no banco de fontes é mantido durante export + operação de
memória: escritores de outros processos aguardam. Ordem de locks: fonte,
depois memória. Não se faz alteração de fonte pela interface de memória.
Respostas são snapshots: uma mudança depois da resposta exige atualização da
tela; a decisão sempre verifica novamente. Fonte obsoleta não pode ser aprovada.

Loopback obrigatório, token efêmero de sessão, Host/Origin restritos, limite
64 KiB por POST, JSON com campos exatos, sem logs de conteúdo, CSP e rendering
com textContent. Token impede requisições acidentais de outra origem; não é
login. Não disponibilizar por proxy público ou como serviço multitenant.

## Persistência, backup e rollback

`.documentos/memory.sqlite3` é privado 0600, mas armazena texto em claro.
Limites do Kit: 4 KiB UTF-8/nota, 1.000 versões, 10.000 eventos. Quotas falham
fechado, sem limpeza silenciosa de recibos. Hashes não são assinaturas; o dono
do banco pode reescrever registros. Não há promessa de auditoria inviolável.

Parar ambos os servidores, usar backup SQLite para arquivo privado e validar
reabertura com fontes atuais. Descarte faz exclusão lógica/VACUUM no banco ativo;
backups, snapshots e SSD não são apagados fisicamente por esse mecanismo.
Rollback: parar servidor 8002, descartar banco/cópias conforme retenção e remover
dependência opcional. Não há migração do banco documental ou deployment.

## Verificar e próximos gates

```bash
python -m unittest discover -s memory_tests -v
# E2E opcional, habilitado na CI dedicada:
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
PDF_BROWSER_TESTS=1 python -m unittest discover -s memory_tests -v
```

Testes cobrem restart, hashes atuais, edição obsoleta, retirada da fonte,
original adulterado, escopo/flags injetados, concorrência entre Stores, TTL,
undo/descarte e guards HTTP. Browser real cobre fonte completa, revisão,
correção, undo, descarte e texto HTML inerte em viewport móvel.

A dependência fixada está em PR separada: revisar/merge do Kit antes de
homologação. Runtime Lab avalia 30 consultas PT-BR: 17/20 positivas recuperadas,
10/10 negativas bloqueadas; gate de qualidade 90% falhou, permanece STUDY.
Control Plane/Hub e qualquer execução paga dependem de utilidade real,
identidade, retenção e reserva preventiva. CI não substitui revisão humana.
