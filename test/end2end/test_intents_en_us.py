"""End-to-end intent routing tests for the en-US locale.

Each canonical utterance is fired through a real MiniCroft and asserted to
route to the expected Padatious intent handler and produce a spoken response.
The quote text itself is random, so assertions cover the intent binding and the
presence of a canonical ``ovos.utterance.speak`` response, not the dialog
content.

This suite exercises the real (native/swig) ``ovos-padatious`` pipeline --
the ``end2end`` CI job installs it via ``require_padatious`` -- with no
``padacioso`` fallback band in the pipeline list. A padacioso rescue path
would silently mask a real padatious regression (padacioso is a separate,
pure-python re-implementation trained on the same ``.intent`` samples, so it
can keep matching even if the actual padatious plugin breaks).
"""
import time
import unittest

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_spec_tools import SpecMessage
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"


def _candidates(intent_file: str) -> set:
    """Different ovos-workshop/pipeline plugin versions normalize the
    ``.intent`` filename basename on the dispatched match-message type
    differently -- current OVOS-INTENT-2 naming drops it, older pinned
    versions keep it. Candidates cover both so the suite isn't pinned to
    whichever happens to be installed, same rationale as documented in
    ovos-skill-volume's end2end suite."""
    base = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
    return {f"{SKILL_ID}:{intent_file}", f"{SKILL_ID}:{base}"}


class TestFusterIntentsEnUS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # the padatious models for this skill's .intent files take a while
        # to train on CI runners, so allow a generous READY window
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=300)
        # Real padatious trains its neural model in a background thread
        # *after* the skill/service report "ready" -- a query fired
        # immediately after boot can race that training and see a
        # false-negative match. Poll with a real, disposable session
        # (never "test-session", which every real test below reuses) until
        # a known-good utterance actually matches, instead of a blind
        # sleep -- this is a real readiness signal, not a fixed guess.
        deadline = time.monotonic() + 60
        warmed = False
        inst = cls()
        while time.monotonic() < deadline and not warmed:
            msgs = inst._run("tell me a fuster quote", session_id="warmup")
            warmed = any(t in _candidates("fuster_quotes.intent") for t in (m.msg_type for m in msgs))
            if not warmed:
                time.sleep(1)
        assert warmed, "padatious model never finished warming up within 60s"

    @classmethod
    def tearDownClass(cls):
        cls.minicroft.stop()

    def _run(self, text, pipeline=None, session_id="test-session"):
        session = Session(session_id)
        session.pipeline = pipeline or [
            "ovos-padatious-pipeline-plugin-high",
            "ovos-padatious-pipeline-plugin-medium",
        ]
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

    def test_fuster_quote(self):
        messages = self._run("tell me a fuster quote")
        types = [m.msg_type for m in messages]
        self.assertTrue(_candidates("fuster_quotes.intent") & set(types))
        self.assertIn(SpecMessage.SPEAK, types)

    def test_who_was_joan_fuster(self):
        messages = self._run("who was Joan Fuster")
        types = [m.msg_type for m in messages]
        self.assertTrue(_candidates("who.intent") & set(types))
        self.assertIn(SpecMessage.SPEAK, types)

    def test_fuster_live(self):
        messages = self._run("when was Fuster alive")
        types = [m.msg_type for m in messages]
        self.assertTrue(_candidates("FusterLive.intent") & set(types))
        self.assertIn(SpecMessage.SPEAK, types)

    def test_fuster_birth(self):
        messages = self._run("when was Joan Fuster born")
        types = [m.msg_type for m in messages]
        self.assertTrue(_candidates("FusterBirth.intent") & set(types))
        self.assertIn(SpecMessage.SPEAK, types)

    def test_fuster_death(self):
        messages = self._run("when did Joan Fuster die")
        types = [m.msg_type for m in messages]
        self.assertTrue(_candidates("FusterDeath.intent") & set(types))
        self.assertIn(SpecMessage.SPEAK, types)
