"""m2v-multilingual candidate-default gate for ovos-skill-fuster-quotes (en-US).

Boots the skill under the candidate default engine -- the m2v multilingual
classifier (``OpenVoiceOS/ovos-m2v-intents-multi-128M-v5``) via ovoscope's
``get_m2v_minicroft`` -- and replays a representative slice of this skill's
own golden utterances (``golden_utterances.jsonl``). Padatious stays the
skill's deterministic floor (see ``test_golden_utterances.py``); this gate
validates the candidate model that may replace it as the shipping default.

Each row asserts both routing (the classifier picks this skill's registered
intent id) and effect (the rendered ``speak`` text carries real dialog
content, not the bare dialog name).

Run:
    uv run pytest test/end2end/test_m2v_gate.py -v
"""
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_m2v_minicroft

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"
LANG = "en-US"

# One representative utterance per intent, pulled from the skill's own golden set.
ROWS = [
    {"utterance": "Any Fusterian thoughts", "intent_label": "fuster_quotes", "dialog": "fuster_quotes"},
    {"utterance": "when was Fuster alive", "intent_label": "FusterLive", "dialog": "live"},
    {"utterance": "when was Fuster born", "intent_label": "FusterBirth", "dialog": "when_was_joan_fuster_born"},
    {"utterance": "when did Fuster die", "intent_label": "FusterDeath", "dialog": "when_did_joan_fuster_die"},
    {"utterance": "who is Joan Fuster", "intent_label": "who", "dialog": "who_was_joan_fuster"},
    {"utterance": "who was Fuster", "intent_label": "who", "dialog": "who_was_joan_fuster"},
]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_m2v_minicroft(skill_ids=[SKILL_ID], lang=LANG)
    pipe = mc.intents.pipeline_plugins["ovos-m2v-pipeline"]
    pipe._ensure_model(background_ok=False)
    yield mc
    mc.stop()


def _capture(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    return capture.finish()


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["utterance"])
def test_m2v_gate(minicroft, row):
    expected_intent = f"{SKILL_ID}:{row['intent_label']}"
    messages = _capture(minicroft, row["utterance"], f"m2v-{row['utterance']}")

    matched = [m for m in messages if m.msg_type == "ovos.intent.matched"]
    assert matched, (
        f"{row['utterance']!r}: expected ovos.intent.matched, got "
        f"{[m.msg_type for m in messages]!r}"
    )
    names = [m.data.get("intent_name") for m in matched]
    assert expected_intent in names, (
        f"{row['utterance']!r}: expected intent_name {expected_intent!r}, got {names!r}"
    )

    speaks = [m for m in messages if m.msg_type in ("speak", "ovos.utterance.speak")]
    assert speaks, f"{row['utterance']!r}: no speak message captured"
    spoken = speaks[0].data.get("utterance", "")
    assert spoken, f"{row['utterance']!r}: empty spoken text"
    assert spoken.strip().lower() != row["dialog"], (
        f"{row['utterance']!r}: spoken text is literally the dialog name: {spoken!r}"
    )
