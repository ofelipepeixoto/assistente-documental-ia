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
O export é histórico e não garante que vários documentos foram lidos no mesmo
instante. Uma revisão pode mudar após o retorno; o consumidor deve comparar
com o `Scope` atual antes de usar o snapshot. Evidência ou hash não autoriza
execução de ação, pagamento, envio de mensagem ou alteração de sistema.

As regressões usam PDF/Store locais, adulterações sintéticas de fixtures e
simulação da ausência do kit; não executam modelos ou serviços externos.
