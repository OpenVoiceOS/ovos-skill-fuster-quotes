"""Every locale ships every intent file that en-US ships.

The golden runner can only gate an intent that has rows, so a deleted
``.intent`` file in one locale would leave that intent untested there. This
test reads the files on disk and needs no MiniCroft.
"""
from pathlib import Path

import pytest

LOCALE_ROOT = Path(__file__).parents[2] / "locale"
REFERENCE = "en-US"


def _intent_names(locale_dir):
    return {path.name for path in locale_dir.rglob("*.intent")}


LOCALES = sorted(d.name for d in LOCALE_ROOT.iterdir()
                 if d.is_dir() and any(d.rglob("*.intent")))


def test_reference_locale_has_intents():
    assert _intent_names(LOCALE_ROOT / REFERENCE)


@pytest.mark.parametrize("lang", LOCALES)
def test_locale_has_every_reference_intent(lang):
    missing = _intent_names(LOCALE_ROOT / REFERENCE) - _intent_names(LOCALE_ROOT / lang)
    assert not missing, f"[{lang}] missing intent files: {sorted(missing)}"
