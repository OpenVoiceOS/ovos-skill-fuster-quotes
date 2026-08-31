"""Golden-utterance end-to-end coverage for ovos-skill-fuster-quotes (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset, keyed by
``skill_id == "ovos-skill-fuster-quotes.openvoiceos"``. One shared
``MiniCroft`` (module-scoped fixture) is booted for the whole suite; every
row is its own parametrized test item.

Four rows shipped in the master corpus for this skill's ``who.intent``
label ("qui est Fuster", "qui est Joan Fuster", "qui était Fuster",
"qui était Joan Fuster") are French, not English -- this suite only
covers ``en-US``, and none of them exercise the skill's actual en-US
``.intent``/``.voc`` content (independently re-verified against the live
skill: they route to nothing). They are dropped from this vendored slice.

This suite exercises the real (native/swig) ``ovos-padatious`` pipeline --
the ``end2end`` CI job installs it via ``require_padatious`` -- with no
``padacioso`` fallback band. A padacioso rescue path would silently mask a
real padatious regression.

Intent match is asserted off the ``ovos.intent.matched`` bus event's
``data.intent_name`` field. Different ovos-workshop/pipeline plugin
versions have been observed to normalize the ``.intent`` filename suffix
differently on that field (current OVOS-INTENT-2 naming drops it, older
pinned versions keep it) -- candidates cover both so the suite isn't
pinned to whichever version happens to be installed, same rationale as
documented in ovos-skill-volume's end2end suite. Capture uses the
default eof (``ovos.utterance.handled``) with a shared, reused session id
(matching test_intents_en_us.py) rather than a fresh session per row: a
per-row unique session id was observed, directly against CI, to prevent
``ovos.intent.matched`` from ever being captured for a
padatious-matched utterance (root cause not fully understood -- see the
PR description).
"""
import json
import time
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession, get_minicroft

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"
LANG = "en-US"

_PIPELINE = [
    "ovos-adapt-pipeline-plugin-high",
    "ovos-padatious-pipeline-plugin-high",
    "ovos-adapt-pipeline-plugin-medium",
    "ovos-padatious-pipeline-plugin-medium",
    "ovos-adapt-pipeline-plugin-low",
]

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# utterances lifted verbatim from OTHER skills' golden-utterance slices,
# picked for lexical overlap with fuster-quotes' "who"/"quote"/"tell me
# about" vocabulary.
NEGATIVE_UTTERANCES = [
    ("what's the weather like today", "ovos-skill-weather.openvoiceos"),
    ("tell me a joke", "ovos-skill-icanhazdadjokes.openvoiceos"),
    ("who is the president", "ovos-skill-wikipedia.openvoiceos"),
    ("what is your cpu usage", "ovos-skill-diagnostics.openvoiceos"),
    ("where is the international space station", "ovos-skill-iss-location.openvoiceos"),
    ("set a timer for 5 minutes", "ovos-skill-alerts.openvoiceos"),
    ("play some music", "ovos-skill-music.openvoiceos"),
]


def _expected_names(skill_id: str, intent_label: str) -> set:
    """Candidate dispatched-message types for ``intent_label`` (eg.
    ``fuster_quotes.intent``), covering both the ``.intent``-suffixed and
    unsuffixed wire forms -- see the module docstring."""
    base = intent_label[:-len(".intent")] if intent_label.endswith(".intent") else intent_label
    return {f"{skill_id}:{base}", f"{skill_id}:{intent_label}"}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


GOLDEN_ROWS = [pytest.param(r, id=r["utterance"]) for r in _load_golden_rows()]


def _dispatched_types(mc, text, session_id):
    """Return every message type observed on the bus for *text*.

    Earlier versions of this suite filtered for the ``ovos.intent.matched``
    bus event and read its ``data.intent_name`` field. Verified directly
    against CI (not locally): for a padatious-matched utterance in this
    repo's real-padatious+adapt environment, that specific message was
    reproducibly absent from the capture even though the utterance
    genuinely matched and dispatched correctly -- the routing message
    (``<skill_id>:<intent>``) that fires immediately after it was always
    present. So this suite checks for that dispatch message directly,
    same strategy as test_intents_en_us.py, rather than parsing
    ovos.intent.matched.
    """
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = list(_PIPELINE)
    # blacklisted_intents defaults to None on a fresh Session, which crashes
    # some pipeline plugins (NoneType membership test) - force an empty list.
    session.blacklisted_intents = []
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    msgs = capture.finish()
    return [m.msg_type for m in msgs]


@pytest.fixture(scope="module")
def minicroft():
    # the padatious models for this skill's .intent files take a while to
    # train on CI runners, so allow a generous READY window (same as
    # test_intents_en_us.py).
    mc = get_minicroft([SKILL_ID], max_wait=300)
    # Real padatious trains its neural model in a background thread *after*
    # the skill/service report "ready" -- a query fired immediately after
    # boot can race that training. Poll with a real, disposable session
    # until a known-good utterance actually matches, instead of a blind
    # sleep -- a real readiness signal, not a fixed guess.
    deadline = time.monotonic() + 60
    warmed = False
    while time.monotonic() < deadline and not warmed:
        types = _dispatched_types(mc, "tell me a fuster quote", "test-session")
        warmed = f"{SKILL_ID}:fuster_quotes" in types or f"{SKILL_ID}:fuster_quotes.intent" in types
        if not warmed:
            time.sleep(1)
    assert warmed, "padatious model never finished warming up within 60s"
    yield mc
    mc.stop()


def _golden_id(row):
    return row["utterance"]


@pytest.mark.timeout(150)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=_golden_id)
def test_golden_utterance(minicroft, row):
    expected = _expected_names(SKILL_ID, row["intent_label"])
    types = _dispatched_types(minicroft, row["utterance"], "test-session")
    assert expected & set(types), (
        f"{row['utterance']!r}: expected one of {sorted(expected)!r}, got {types!r}"
    )


@pytest.mark.timeout(150)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    text, source_skill = negative
    types = _dispatched_types(minicroft, text, "test-session")
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}"
