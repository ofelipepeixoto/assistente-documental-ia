"""Contrato Docling com doubles explícitos; não equivale a validar os modelos reais."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

from avaliacao.pdf_fixtures import make_pdf
from ingestion.contracts import LabError, Limits
from ingestion.docling_adapter import configuration, parse_docling
from ingestion.native import extract
from ingestion.store import Store
from ingestion.search import search


class DoclingTests(unittest.TestCase):
    def test_artifacts_required_and_hash_changes(self):
        with self.assertRaises(LabError):
            configuration(None)
        with tempfile.TemporaryDirectory() as directory, patch('ingestion.docling_adapter.version', return_value='2.55.1'):
            with self.assertRaises(LabError):
                configuration(directory)
            file = Path(directory)/'weights'
            file.write_bytes(b'synthetic-a')
            before = configuration(directory)
            file.write_bytes(b'synthetic-b')
            self.assertNotEqual(before['artifacts_sha256'], configuration(directory)['artifacts_sha256'])

    def test_timeout_and_input_limits(self):
        with patch('ingestion.native.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 1)):
            self.assertEqual(extract(make_pdf(), parser='docling')['error'], 'parser_timeout')
        with self.assertRaises(LabError):
            extract(make_pdf(), Limits(max_bytes=2), parser='docling')
        self.assertEqual(parse_docling(make_pdf(), Limits(max_pages=1), '')['error'], 'page_limit')
        self.assertEqual(parse_docling(make_pdf(encrypted=True), Limits(), '')['error'], 'encrypted_pdf')

    @unittest.skipUnless(os.environ.get("DOCLING_ARTIFACTS"), "Exige pesos locais; download não faz parte da suíte")
    def test_real_docling_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            doc = Store(directory).ingest(make_pdf(), 'synthetic.pdf', parser='docling',
                                          artifacts=os.environ['DOCLING_ARTIFACTS'])
            self.assertIsNone(doc['error'])
            self.assertEqual(len(doc['pages']), 3)
            self.assertTrue(all(p['method'] == 'docling' for p in doc['pages']))
            self.assertIn('1.250,50', doc['pages'][1]['text'])
            self.assertTrue(all(p['review'] is None for p in doc['pages']))

    def fake_modules(self, text, status='success', pages=None):
        result = NS(status=status, document=NS(pages=pages or {1: {}, 2: {}, 3: {}},
                    export_to_markdown=lambda page_no: text))
        self.options = None
        self.convert_kwargs = None
        def options(**kwargs):
            self.options = kwargs
            return kwargs
        def convert(*args, **kwargs):
            self.convert_kwargs = kwargs
            return result
        modules = {}
        for name, attrs in {
            'docling.datamodel.base_models': dict(InputFormat=NS(PDF='pdf'), DocumentStream=lambda **kw: kw, ConversionStatus=NS(SUCCESS='success')),
            'docling.datamodel.pipeline_options': dict(PdfPipelineOptions=options),
            'docling.document_converter': dict(DocumentConverter=lambda **kw: NS(convert=convert), PdfFormatOption=lambda **kw: kw),
        }.items():
            module = ModuleType(name)
            module.__dict__.update(attrs)
            modules[name] = module
        return patch.dict(sys.modules, modules)

    def test_mapping_limits_and_no_remote_services(self):
        with self.fake_modules('Pagamento mensal sintético de cem reais.'):
            result = parse_docling(make_pdf(), Limits(), '/models')
            self.assertEqual([p['page_number'] for p in result['pages']], [1, 2, 3])
            self.assertFalse(self.options['enable_remote_services'])
            self.assertFalse(self.options['do_ocr'])
            self.assertEqual(self.convert_kwargs['max_num_pages'], 50)
        with self.fake_modules('x'*60):
            result = parse_docling(make_pdf(), Limits(max_page_chars=50), '/models')
            self.assertTrue(all(p['error'] == 'text_limit' for p in result['pages']))
        with self.fake_modules('', status='partial'):
            self.assertEqual(parse_docling(make_pdf(), Limits(), '/models')['error'], 'docling_conversion_failed')
        with self.fake_modules('', pages={1: {}}):
            self.assertEqual(parse_docling(make_pdf(), Limits(), '/models')['error'], 'docling_page_mismatch')

    def test_same_store_review_search_and_parser_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            native = store.ingest(make_pdf(), 'synthetic.pdf')
            fake = {'error': None, 'pages': [{'page_number': 1, 'text': 'Pagamento mensal sintético de cem reais.', 'method': 'docling', 'status': 'extracted', 'error': None}]}
            with patch('ingestion.docling_adapter.configuration', return_value={'parser': 'docling', 'parser_version': 'test-double'}), patch('ingestion.store.extract', return_value=fake):
                doc = store.ingest(make_pdf(), 'synthetic.pdf', parser='docling', artifacts='/models')
                self.assertNotEqual(native['id'], doc['id'])
                self.assertEqual(search(store, 'pagamento mensal'), [])
                store.review(doc['id'], 1, 1, 'Revisor fictício', 'approved')
                self.assertEqual(search(store, 'pagamento mensal')[0]['document_id'], doc['id'])
                self.assertEqual(store.ingest(make_pdf(), 'synthetic.pdf', parser='docling', artifacts='/models')['revision'], 2)
