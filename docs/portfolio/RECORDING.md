# Reprodução da gravação / Recording reproduction

1. Gere `contrato_demo.pdf` com `python -m avaliacao.pdf_fixtures`.
2. Abra a interface PDF, selecione o arquivo e clique em **Extrair texto**.
3. Use o nome **Revisor fictício — demonstração** e confira/aprove as três páginas.
4. Pesquise **pagamento mensal**. O resultado deve apontar a página 2 e o trecho R$ 1.250,50.
5. Não apresente o rótulo de revisor como identidade autenticada.

## Captura desta entrega

Interface local real, viewport 1280×900; vídeo 960×675. Sessões novas e dados fictícios; requisições fora de loopback bloqueadas durante a gravação. Browser Chromium em modo headless. Vídeo sem narração e sem alterações do conteúdo da interface. Conversão WebM → MP4 por ffmpeg, mantendo a ordem temporal.

As capturas são arquivos gerados, não o código do aplicativo. Screenshots/vídeos podem variar com fonte, relógio e versão do navegador. Para regravar, siga a sequência acima e use uma ferramenta de gravação de tela. Não force snapshots locais, credenciais ou arquivos de estado para o Git.
