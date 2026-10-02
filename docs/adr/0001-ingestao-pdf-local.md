# ADR 0001 — Ingestão PDF local e revisável

Status: implementada como laboratório. Data: 2026-10-01.

## Contexto

O assistente existente busca trechos de arquivos TXT e oferece geração opcional separada. Precisamos introduzir PDFs sem criar outro repositório, contratar GPU ou presumir autenticação/multitenancy.

## Decisão

Manter os caminhos TXT. Acrescentar extração CPU com pypdf fixado por hash, em subprocesso limitado, armazenamento SQLite local e interface de três etapas em português. Persistir original/manifesto, páginas, falhas e decisões ligadas aos hashes. Busca PDF considera somente páginas aprovadas.

A workspace é de uma pessoa no computador local; revisores são autodeclarados. SHA256 e revisão otimista permitem rastreabilidade e bloqueiam aprovações desatualizadas, mas não são assinatura ou prova de identidade. Não expor a aplicação pela internet.

olmOCR entra como adaptador opcional de saída Dolma local. Importar exige origem e modelo/revisão declarados, valida a estrutura e invalida revisões. Nenhuma inferência paga ou instalação de GPU é acionada.

## Alternativas

- Incorporar todo o upstream/training/GPU: aumenta operação e importa dependências alertadas antes de qualidade/custo medidos.
- API OCR contratada imediatamente: exige termos, retenção e orçamento ainda não definidos.
- FastAPI/Supabase/MCP agora: não necessários para validar extração e revisão local. Entrar quando houver serviço autenticado e segundo consumidor real.
- Indexar extração automaticamente: rejeitado; formato válido não garante fidelidade jurídica.

## Consequências

Baixo custo de validação e reuso do laboratório existente. Dados ficam locais e fora do Git. Revisão humana é necessária; busca lexical pode abster-se demais ou recuperar contexto insuficiente. Scans e tabelas complexas precisam de OCR avaliado.

Os limites Linux não equivalem a sandbox; Windows/macOS têm somente prazo de processo e limites lógicos. O banco não é criptografado; permissões/retencão/backup dependem do operador. Produção exige auth/ACL, revisão verificada, isolamento de parser, custos/quotas, observabilidade, corpus PT-BR real e recovery.

## Provas e gates

Testes: origem/página, duplicidade, falha/scan, limite de bytes/páginas/texto, timeout real de subprocesso, versão antiga, concorrência de revisão, rejeição/correção, conteúdo não executável, importação Dolma inválida e fluxo HTTP/browser.

Avaliação sintética de três páginas e sete perguntas, sem extrapolar qualidade para PDFs reais. Corpus e resultados versionados. Baseline TXT anterior preservado. Aprovação em produção permanece pendente do corpus representativo e dos controles acima.

## Reversão

Sem migração de banco existente, implantação externa ou alteração no script TXT. Antes do merge, fechar o PR encerra a proposta. Após merge, reverter os commits da funcionalidade; dados locais devem ser preservados/exportados pelo operador antes de qualquer exclusão.
