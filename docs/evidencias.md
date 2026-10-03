# Exportar evidências documentais aprovadas

Este adapter opcional lê a workspace PDF já existente e gera um snapshot JSON
local. Não chama LLM, baixa modelo, usa rede ou executa ações. O fluxo de
ingestão/revisão existente continua independente da biblioteca opcional.

O adapter usa `radar-evidence-kit` 0.1.0, pacote original sem dependências
externas. A biblioteca tem seu próprio repositório autoral,
[ofelipepeixoto/radar-evidence-kit](https://github.com/ofelipepeixoto/radar-evidence-kit),
com autoria de Carlos Felipe e licença MIT. O commit exato utilizado pelo consumidor
fica fixado em `requirements-evidence.txt`; esse arquivo também é usado pelo CI.
Instale a biblioteca no mesmo ambiente Python que contém `requirements-pdf.txt`:

```sh
python -m pip install --no-deps -r requirements-evidence.txt
python -m unittest tests.test_evidence_adapter -v
```

A instalação usa a origem e a revisão registradas nesse arquivo, sem depender
de um checkout vizinho. A instalação da biblioteca pode acessar a rede; a
exportação documental continua local. Sem o kit, somente esta exportação
retorna um erro claro.

Liste os documentos com `python -m ingestion listar`. Depois de revisar uma
página, use o ID e a **revisão atual** do documento, que muda a cada revisão:

```sh
python exportar_evidencias.py --pasta .documentos \
  --tenant operador-local --projeto contratos-demo \
  --documento ID_SHA256:REVISAO > evidencias.json
```

Substitua `ID_SHA256:REVISAO` pelos valores listados; o exemplo é um placeholder.
Repita `--documento` para escolher outros documentos. A execução explícita
exporta o texto integral aprovado para stdout: escolha onde guardar esse
arquivo considerando o conteúdo dos documentos. A CLI não cria uma workspace
inexistente nem oferece gravação remota.

No código, `export_approved_evidence(store, tenant_id=..., project_id=...,
expected_revisions={id: revisao})` retorna `list[Evidence]`. O escopo e as
revisões são parâmetros de configuração do operador. O adapter obtém o texto
do `Store`; não recebe texto, revisão ou aprovação gerados por LLM.

Cada registro preserva ID/revisão do documento, SHA-256 do original validado,
número da página, texto completo, hash do texto revisado e limites `0:len(text)`
em posições Unicode. Só entram páginas extraídas, não vazias, aprovadas e com
hashes correspondentes ao texto e ao original. Pendentes, rejeitadas e
aprovações invalidadas ficam fora. Original adulterado, documento ausente ou
revisão divergente interrompem o export inteiro. Páginas maiores que o limite
de 16 KiB UTF-8 do kit são rejeitadas; não há truncamento para fazer caber.

O JSON contém `scope`, além de itens `evidence` com `evidence_id` e `record`.
Use `Evidence.from_dict(item["record"])` para reconstruir o contrato; o ID é
calculado sobre o registro inteiro. Hashes vinculam bytes e campos, mas não
provam a verdade do texto nem impedem que alguém com acesso de escrita ao banco
refaça documento e hashes.

O nome do revisor é um rótulo autodeclarado. O adapter mantém
`identity_verified=False`, inclusive se um manifesto local alegar o contrário.
A verificação padrão do kit exige identidade verificada e, por isso, não
aprova esses registros para essa política. Desativar essa exigência é uma
política explícita de laboratório; não autentica o revisor.

`tenant` e `projeto` são rótulos de escopo: não constituem login, ACL ou
isolamento multitenant. A workspace continua sendo de um operador local.
Originais e manifestos selecionados são lidos na mesma transação SQLite,
sem misturar revisões de documentos lidos em momentos diferentes. O export
continua histórico: uma revisão pode mudar depois que a transação termina. Evidência ou hash não autoriza
execução de ação, pagamento, envio de mensagem ou alteração de sistema.

As regressões usam PDF/Store locais, adulterações sintéticas de fixtures e
simulação da ausência do kit; não executam modelos ou serviços externos.


## Conferir um snapshot antes de leitura no consumidor

`validate_local_snapshot` compara o envelope JSON inteiro com os registros
aprovados atuais obtidos do Store: original, texto, página, revisão, nome local,
identidade não verificada e `evidence_id`. Revisão antiga, rejeição posterior,
correção, rótulo alterado ou tentativa de promover identidade fazem a validação
falhar. Recalcular o hash de um registro adulterado não o torna igual ao Store.

```python
from ingestion.evidence_adapter import validate_local_snapshot

# Estes valores vêm da configuração do consumidor local, não do payload.
itens = validate_local_snapshot(
    store, payload, tenant_id="operador-local", project_id="contratos-demo",
    document_ids=[id_documento_permitido],
)
```

O consumidor escolhe quais documentos e rótulos aceita; o código consulta as
revisões atuais no Store. O payload não escolhe sua própria política. A função
só devolve contratos de integridade para leitura de laboratório, sempre com
`identity_verified=False`. Ela não é login, verificação de revisão humana,
controle multitenant ou autorização para ferramentas. Não ligue seu retorno a
execução externa sem identidade e autorização reais no consumidor. Uma mudança
após o retorno exige nova verificação; esta função não promete serialização de
uma ação em outro sistema. São aceitos de 1 a 50 documentos por snapshot.
