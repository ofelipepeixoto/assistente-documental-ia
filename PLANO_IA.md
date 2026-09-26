# Próxima etapa: avaliar a resposta apoiada no documento

`resposta_ia.py` já contém um caminho opcional de geração via API. A qualidade dos rascunhos gerados ainda não foi avaliada; as verificações automatizadas não fazem chamadas externas.

## Entrada
Pergunta do usuário e trechos encontrados nos documentos fictícios.

## Saída
Um rascunho de resposta com:
- resposta em linguagem simples;
- nome do documento e trecho usado;
- aviso quando não houver informação suficiente;
- indicação de que o texto precisa de revisão humana.

## Limites
- A busca lê arquivos `.txt` da pasta de exemplos antes de enviar o trecho. Isso não garante que o trecho selecionado seja suficiente ou que o modelo não erre.
- Nenhuma peça será enviada, assinada ou publicada automaticamente.
- Chaves de API não serão colocadas no repositório.
- A busca atual continuará disponível como referência para comparação.

## Verificação
Comparar o rascunho com respostas esperadas para perguntas sobre prazo,
pagamento, rescisão e informações ausentes no documento.
