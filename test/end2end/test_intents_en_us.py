"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the expected intent handler AND to speak a dialog line
drawn from that intent's own ``.dialog`` file. The expected line set is read
directly from the locale file on disk, independent of the skill handler
under test, so a handler that speaks the wrong dialog (or the right dialog
for a different intent) fails here even though it still emits a
``ovos.utterance.speak`` message and still matches the correct intent name.
"""
import unittest
from pathlib import Path

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools import SpecMessage
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"
LOCALE_EN_US = Path(__file__).parent.parent.parent / "locale" / "en-US"


def _dialog_lines(name: str) -> set:
    path = LOCALE_EN_US / f"{name}.dialog"
    with open(path, encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


# Read once, directly from the shipped dialog files -- never from a captured
# bus message -- so these sets are independent of the code under test.
QUOTE_LINES = _dialog_lines("fuster_quotes")
LIFESPAN_LINES = _dialog_lines("lifespan")
WHO_LINES = _dialog_lines("who_was_joan_fuster")

_DIALOG_LINES = {
    "fuster_quotes.intent": QUOTE_LINES,
    "who.intent": WHO_LINES,
    "fuster_lifespan.intent": LIFESPAN_LINES,
}


class TestFusterIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang="en-US")

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _run(self, text):
        session = Session(f"e2e-{abs(hash(text))}")
        session.lang = "en-US"
        session.pipeline = PIPELINE
        # blacklisted_intents defaults to None on a fresh Session, which
        # crashes some pipeline plugins (NoneType membership test).
        session.blacklisted_intents = []
        utterance = Message(
            "recognizer_loop:utterance",
            {"utterances": [text], "lang": "en-US"},
            {"session": session.serialize(), "source": "A", "destination": "B"},
        )
        capture = CaptureSession(self.minicroft)
        capture.capture(utterance, timeout=30)
        return capture.finish()

    def test_dialog_sets_are_disjoint(self):
        # If two intents' dialog sets shared a line, speaking the wrong
        # dialog would still satisfy a membership check below and this
        # suite would silently degrade back into a routing-only test.
        names = list(_DIALOG_LINES)
        for i, name_a in enumerate(names):
            for name_b in names[i + 1:]:
                overlap = _DIALOG_LINES[name_a] & _DIALOG_LINES[name_b]
                self.assertFalse(
                    overlap,
                    f"{name_a} and {name_b} dialog files share lines: {overlap!r}",
                )

    def _assert_intent(self, text, intent):
        messages = self._run(text)
        types = [m.msg_type for m in messages]
        TALLY.assert_routed(text, f"{SKILL_ID}:{intent}", types)
        spoken = [
            m.data.get("utterance", "")
            for m in messages
            if m.msg_type == SpecMessage.SPEAK
        ]
        self.assertTrue(spoken, f"expected a spoken response for {text!r}, got {types!r}")
        expected_lines = _DIALOG_LINES[intent]
        self.assertTrue(
            all(utt in expected_lines for utt in spoken),
            f"expected only {intent}'s own dialog lines to be spoken for "
            f"{text!r}, got {spoken!r}",
        )

    def test_fuster_quote(self):
        self._assert_intent("tell me a fuster quote", "fuster_quotes.intent")

    def test_who_was_joan_fuster(self):
        self._assert_intent("who was Joan Fuster", "who.intent")

    def test_fuster_live(self):
        self._assert_intent("when was Fuster alive", "fuster_lifespan.intent")

    def test_fuster_birth(self):
        self._assert_intent("when was Joan Fuster born", "fuster_lifespan.intent")

    def test_fuster_death(self):
        self._assert_intent("when did Joan Fuster die", "fuster_lifespan.intent")

    def test_fuster_last_alive(self):
        self._assert_intent("when was Fuster last alive", "fuster_lifespan.intent")

    def test_fuster_still_alive(self):
        self._assert_intent("is Fuster still alive", "fuster_lifespan.intent")
