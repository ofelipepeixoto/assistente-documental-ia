# Contribuir / Contributing

Contribuições pequenas e verificáveis são bem-vindas. Leia o README e, quando existir, `AGENTS.md` antes de alterar o projeto.

Small, reviewable contributions are welcome. Read the README and any `AGENTS.md` before changing the project.

## Começar / Start here

- Reproduza a demonstração local com dados fictícios / Run the local synthetic demo.
- Execute `python avaliar_pdf.py --strict`; informe o resultado real / Report the actual result.
- Faça uma mudança coerente por PR / Keep each PR focused on one coherent change.
- Descreva problema, comportamento anterior/posterior, verificação e limites / Describe the problem, before/after behavior, verification and limits.
- Use fixtures sintéticas; não envie documentos reais, `.env`, tokens ou dumps / Use synthetic fixtures; never submit real documents, credentials or dumps.
- Preserve revisão humana, autorização, regras versionadas e condições de uso / Preserve review, authorization, versioned rules and usage terms.

## Tarefa inicial proposta / Suggested starter task

Add a synthetic PDF fixture containing a two-column layout and record extraction failures without changing approval requirements.

**Aceite / Acceptance:** fixture reproduzível, resultado esperado explícito, documentação dos limites e verificações relevantes aprovadas. Não ampliar escopo, contratar serviços ou ativar provedores reais.

Report security concerns privately through an existing maintainer contact; do not post exploitable details or secrets in a public issue. A private reporting channel is not newly configured by this document.
