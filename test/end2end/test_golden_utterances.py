"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

Each locale must match at least ``MIN_MATCH_RATE`` of its golden rows, and at
least ``MIN_MATCHED_ROWS_PER_INTENT`` rows of each intent. A locale in
``GOLDEN_LOCALE_GAPS`` runs its rate as an expected failure with its measured
rate as a floor. All rows run,
including rows marked ``needs_manual`` or ``machine_generated``, and the test
prints every row that misses with the intent that matched instead.

``negative_utterances_<lang>.jsonl`` holds requests for other skills (weather,
timers, music, jokes, other people). In the same MiniCroft, each one must match
none of this skill's intents, unless ``NEGATIVE_KNOWN_CLAIMS`` names that
claim. A locale in ``NEGATIVE_ENGINE_GAPS`` runs its negatives as an expected
failure with the measured reason.
"""
import json
from functools import cache
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# A locale also fails when any of its intents has fewer matched rows than this.
MIN_MATCHED_ROWS_PER_INTENT = 1
# Locales that stay below MIN_MATCH_RATE after natural template lines and a
# machine-translated pass, as {lang: (measured_rate, reason)}. Such a locale
# is an expected failure on the rate only. It still fails when an intent
# matches no row, or when its rate falls more than GAP_TOLERANCE below the
# measured rate.
GOLDEN_LOCALE_GAPS = {
    "de-DE": (8 / 12, "m2v sends 4 of 12 rows to a sibling intent (who, "
                      "fuster_quotes and fuster_lifespan cross)"),
    "es-CO": (8 / 12, "m2v sends 4 of 12 rows to fuster_quotes (who and "
                      "fuster_lifespan rows that name Fuster)"),
    "fa-IR": (5 / 12, "m2v sends who rows to fuster_lifespan and fuster_quotes "
                      "rows to who and fuster_lifespan"),
}
GAP_TOLERANCE = 0.10
# Locales whose negatives the published m2v model cannot separate from this
# skill, as {lang: reason}. Their negatives run as a non-strict expected failure.
NEGATIVE_ENGINE_GAPS = {
    "ru-RU": "m2v claims 4 of 5 ru-RU requests for other skills (weather, timer, joke, "
             "a person), on the dev locale files too, while 9 of 10 ru-RU golden rows route",
}
# Negative rows that m2v claimed for this skill in two separate runs, as
# {lang: {utterance: claimed_intent}}. A listed claim is allowed, not required,
# so a row that flips between boots does not fail the test. Any other claim
# fails the locale.
NEGATIVE_KNOWN_CLAIMS = {}
END2END_DIR = Path(__file__).parent


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}_*.jsonl")):
        lang = path.stem.removeprefix(f"{prefix}_")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances")
NEGATIVE_ROWS = _rows_by_lang("negative_utterances")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


@cache
def _matches(lang):
    """Boot the skill on m2v in ``lang`` once and return the intent that each
    golden row and each negative row matches."""
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        golden = [_matched_intent(engine, row["utterance"], lang) for row in ROWS[lang]]
        negative = [_matched_intent(engine, row["utterance"], lang)
                    for row in NEGATIVE_ROWS.get(lang, [])]
        return golden, negative
    finally:
        minicroft.stop()


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    rows = ROWS[lang]
    matched, _ = _matches(lang)
    misses = []
    hits = {row["intent_label"]: 0 for row in rows}
    for row, got in zip(rows, matched):
        if got == f"{SKILL_ID}:{row['intent_label']}":
            hits[row["intent_label"]] += 1
        else:
            misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
    starved = sorted(label for label, count in hits.items()
                     if count < MIN_MATCHED_ROWS_PER_INTENT)
    rate = 1 - len(misses) / len(rows)
    print(f"[{lang}] {rate:.1%} of {len(rows)} rows match", *misses, sep="\n  ")
    if starved:
        print(f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}")
    assert not starved, (
        f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    )
    if lang in GOLDEN_LOCALE_GAPS:
        measured, reason = GOLDEN_LOCALE_GAPS[lang]
        assert rate >= measured - GAP_TOLERANCE - 1e-9, (
            f"[{lang}] {rate:.1%} of rows match, more than {GAP_TOLERANCE:.0%} below "
            f"the measured {measured:.1%}:\n  " + "\n  ".join(misses)
        )
        if rate < MIN_MATCH_RATE:
            pytest.xfail(f"[{lang}] {rate:.1%} of rows match: {reason}")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang], strict=False))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVE_ROWS)
])
def test_negative_rows_match_no_skill_intent(lang):
    rows = NEGATIVE_ROWS[lang]
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    _, matched = _matches(lang)
    claims = [(row["utterance"], got.removeprefix(f"{SKILL_ID}:"))
              for row, got in zip(rows, matched)
              if got and got.startswith(f"{SKILL_ID}:")]
    unknown = [f"{utterance!r}: matched {intent}" for utterance, intent in claims
               if known.get(utterance) != intent]
    print(f"[{lang}] {len(claims)} of {len(rows)} negative rows claimed, "
          f"{len(unknown)} not in NEGATIVE_KNOWN_CLAIMS", *claims, sep="\n  ")
    assert not unknown, f"[{lang}] negative rows matched this skill:\n  " + "\n  ".join(unknown)


def test_every_negative_file_has_a_golden_file():
    assert set(NEGATIVE_ROWS) <= set(ROWS), sorted(set(NEGATIVE_ROWS) - set(ROWS))


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.split("_", 2)[2] for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    locale_root = END2END_DIR.parents[1] / "locale"
    shipping = {d.name for d in locale_root.iterdir() if d.is_dir() and any(d.rglob("*.intent"))}
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"
