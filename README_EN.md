# Document Assistant — reviewed PDF evidence

[Português](README.md) · [Demo and case study](docs/portfolio/CASE_STUDY.md) · [Contributing](CONTRIBUTING.md)

Find passages in a document while keeping page references and human review visible.

## Workflow

Upload a synthetic digital PDF → inspect and approve its pages → search only approved text.

## Current status

Local laboratory. No public service, authenticated reviewers or legal advice.

## Run locally without an AI key

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-pdf.txt
python -m avaliacao.pdf_fixtures
python documentos_web.py
```

Open http://127.0.0.1:8001. For Windows commands, installation requirements, private-mode configuration and the full operational reference, see the [Portuguese README](README.md). This is an English onboarding guide; it does not replace that reference.

## Reproducible verification

```sh
python avaliar_pdf.py --strict
```

7/7 retrieval cases passed on a synthetic, three-page digital PDF. Normalized CER/WER were zero for this fixture. Two cases check abstention; unrevised text stays out of search.

Evidence was reproduced from commit `cae6e1e94d2ac4e70d10770b75cc52a839e97e3c`. See the case study for scope and the recording procedure.

## Project contribution and attribution

PDF ingestion, page-level review, version/hash checks, lexical retrieval and the local interface. Optional third-party parsers retain their own authorship and licenses.

## Limits

This does not measure OCR inference, scanned documents, tables, real legal documents or specialist review. Reviewer names are self-declared. The local server must not be exposed through a tunnel.

No real customer data, credentials, measured business ROI or production certification is implied by the screenshots or test counts. Existing project license terms remain unchanged; public availability does not itself grant unrestricted reuse.
