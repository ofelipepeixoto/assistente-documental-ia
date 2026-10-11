# Trechos revisados para o experimento de recuperação

Implementação original, opcional e local, motivada pelo estudo do Jevbox.
Não inclui parser, UI, ícones, MCP ou provedor externo do Jevbox. Mantém pypdf,
SQLite, revisão humana local e o contrato de evidência já existentes.

Instale `requirements-pdf.txt` com hashes e `requirements-evidence.txt`.
O kit está fixado no commit `a81f29b43f780d7f83be257be3de99213d2437ea`
da [PR de citações](https://github.com/ofelipepeixoto/radar-evidence-kit/pull/6).
Revisar essa dependência antes de integrar esta PR.

```sh
python exportar_evidencias.py --pasta .documentos --tenant local --projeto piloto \
  --documento ID_SHA256:REVISAO --trechos > trechos.json
```

Substitua ID/revisão pelos valores atuais da workspace já revisada. A opção
`--trechos` usa um novo `kind=documental_passage_snapshot`; sem a opção, o
contrato anterior permanece igual. Não compartilhe esse JSON publicamente:
ele contém o texto integral revisado, sem anonimização automática.

O export guarda cada página uma vez e referências de janela (512 caracteres,
64 de sobreposição). Hashes, revisão, origem e texto completo permanecem
vinculados; não são criadas aprovações independentes para trechos. Limites:
256 páginas aprovadas, 2048 referências e 2 MiB por snapshot. Nenhum excesso
é truncado. Páginas pendentes/rejeitadas são excluídas.

O consumidor abre o arquivo binário com `load_passage_snapshot`, que limita
bytes antes do parsing e rejeita campos duplicados e números não finitos.
Depois chama `validate_passage_snapshot` com seu Store e sua configuração
de tenant, projeto, IDs permitidos e janela. Esses valores não vêm do JSON.
A comparação integral com o Store atual bloqueia adulteração, revisão antiga,
mudança de original, identidade inventada e conjuntos incompletos de trechos.
Revalidar novamente após uma revisão concorrente e antes do uso.

Esse caminho é para pesquisa local: rótulos não autenticam pessoas e o Store
não é multitenant. `identity_verified` continua `False`, inclusive nos trechos.
Não há autorização para publicação, chamadas pagas ou ações externas. Não
expor a CLI como API. Identidade autenticada, ACL, isolamento de workers,
reserva financeira e reconciliação continuam gates separados de produção.

O laboratório `laboratorio-busca-rag` compara busca plana e hierárquica usando
esses contratos e um teste de integração com PDF/SQLite reais. Nenhum ganho
de recuperação, capacidade ou qualidade jurídica é presumido por esta mudança.
