"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the expected Padatious intent handler and produce a spoken response.
The quote text itself is random, so assertions cover the intent binding and the
presence of a ``speak`` response, not the dialog content.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"


class TestFusterIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _run(self, text):
        session = Session("test-session")
        session.pipeline = [
            "ovos-padatious-pipeline-plugin-high",
            "ovos-padatious-pipeline-plugin-medium",
        ]
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": "en-US"},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft)
        capture.capture(utterance, timeout=30)
        return capture.finish()

    def test_fuster_quote(self):
        messages = self._run("tell me a fuster quote")
        types = [m.msg_type for m in messages]
        self.assertIn(f"{SKILL_ID}:fuster_quotes.intent", types)
        self.assertTrue(any("speak" in t for t in types))

    def test_who_was_joan_fuster(self):
        messages = self._run("who was Joan Fuster")
        types = [m.msg_type for m in messages]
        self.assertIn(f"{SKILL_ID}:who.intent", types)
        self.assertTrue(any("speak" in t for t in types))
