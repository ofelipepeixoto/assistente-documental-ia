"""Bounded local HTTP parsing, without network or real documents."""
import io
from email.message import Message
import unittest
from unittest.mock import Mock
from demo_web import Handler


class DemoLimits(unittest.TestCase):
    def request(self, lengths, body=b"", transfer=None):
        handler = object.__new__(Handler)
        handler.path = "/"
        handler.headers = Message()
        for length in lengths:
            handler.headers.add_header("Content-Length", length)
        if transfer:
            handler.headers["Transfer-Encoding"] = transfer
        handler.rfile = Mock(wraps=io.BytesIO(body))
        handler.responder = Mock()
        handler.do_POST()
        return handler

    def test_invalid_framing_never_reads(self):
        for lengths in ([], ["-1"], ["abc"], ["+1"], ["1", "1"], ["9" * 5000], ["１２"]):
            with self.subTest(lengths=lengths[:1]):
                handler = self.request(lengths)
                self.assertEqual(handler.responder.call_args.args[0], 400)
                handler.rfile.read.assert_not_called()
        handler = self.request(["1"], transfer="chunked")
        self.assertEqual(handler.responder.call_args.args[0], 400)
        handler.rfile.read.assert_not_called()

    def test_oversize_never_reads(self):
        handler = self.request(["4097"])
        self.assertEqual(handler.responder.call_args.args[0], 413)
        handler.rfile.read.assert_not_called()

    def test_incomplete_and_invalid_utf8(self):
        for length, body in ((2, b"a"), (1, b"\xff")):
            handler = self.request([str(length)], body)
            self.assertEqual(handler.responder.call_args.args[0], 400)
            handler.rfile.read.assert_called_once_with(length)

    def test_valid_form(self):
        body = b"pergunta=pagamento"
        handler = self.request([str(len(body))], body)
        self.assertEqual(handler.responder.call_args.args[0], 200)
        handler.rfile.read.assert_called_once_with(len(body))

    def test_timeout_configured(self):
        self.assertEqual(Handler.timeout, 5)
