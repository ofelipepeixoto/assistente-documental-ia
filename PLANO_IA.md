# Próxima etapa: geração com autorização e orçamento

A busca TXT e o fluxo PDF funcionam localmente sem LLM. `resposta_ia.py` mantém
as evidências e a abstenção; geração OpenAI está bloqueada inclusive quando há
chave, até existir integração com os controles abaixo. A presença de uma chave
não constitui aprovação de envio nem liberação de gasto.

## Antes de habilitar geração paga

1. Derivar identidade e escopo no consumidor autenticado; não aceitar identidade
   verificada ou autorização como booleanos do JSON de entrada.
2. Validar a revisão atual e os hashes no Store, com documentos autorizados pelo
   consumidor. Revisão local continua autodeclarada.
3. Configurar preços e limite explicitamente num domínio protegido. Não inferir
   tarifa ou orçamento a partir de instruções do usuário/documento.
4. Reservar o máximo de custo previsto atomicamente em armazenamento persistente,
   com idempotência, antes da chamada; falha na reserva impede inferência.
5. Reconciliar consumo e resultado, tratando timeout/resultado desconhecido sem
   duplicar chamadas ou liberar valores de forma insegura.
6. Avaliar resposta, suporte das citações e abstenção no corpus PT-BR autorizado.

Nenhuma peça é enviada, assinada ou publicada automaticamente. O módulo de
budget do Integration Hub não governa este consumidor Python por proximidade de
repositórios; a integração real precisa de contrato e testes próprios.

## Verificação atual

Testes locais cobrem a busca, fonte, ausência de trecho, chave configurada com
API bloqueada e integridade/revisão dos snapshots. Não há avaliação publicada de
resposta de modelo, chamada paga ou benchmark de inferência nesta entrega.
