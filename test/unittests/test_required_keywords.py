"""Every intent that names Fuster ships a ``.required`` in every locale.

An intent about one named person also matches the same question about any
other person on a sentence-embedding engine. Its ``.required`` lists the name
forms, and at least one must occur in the utterance (OVOS-INTENT-2 4.5). The
test reads the files on disk and derives every expectation from them.
"""
import json
from pathlib import Path

import pytest
from ovos_spec_tools import LocaleResources, utterance_contains

ROOT = Path(__file__).parents[2]
LOCALE_ROOT = ROOT / "locale"
GOLDEN_ROOT = ROOT / "test" / "end2end"
RESOURCES = LocaleResources(str(LOCALE_ROOT))

INTENT_LOCALES = sorted(
    (path.stem, locale.name)
    for locale in LOCALE_ROOT.iterdir() if locale.is_dir()
    for path in locale.rglob("*.intent"))


def _golden_rows():
    for path in sorted(GOLDEN_ROOT.glob("golden_utterances_*.jsonl")):
        lang = path.stem.removeprefix("golden_utterances_")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                yield lang, row["intent_label"], row["utterance"]


GOLDEN = sorted(set(_golden_rows()))


def test_intents_are_found():
    assert INTENT_LOCALES
    assert GOLDEN


@pytest.mark.parametrize("intent,lang", INTENT_LOCALES)
def test_locale_has_required_keywords(intent, lang):
    assert RESOURCES.load_required_keywords(intent, lang), \
        f"[{lang}] {intent}.required is missing or empty"


@pytest.mark.parametrize("lang,intent,utterance", GOLDEN)
def test_golden_row_contains_a_required_keyword(lang, intent, utterance):
    keywords = RESOURCES.load_required_keywords(intent, lang)
    assert utterance_contains(utterance, keywords), \
        f"[{lang}] {intent}: {utterance!r} has none of {keywords}"
