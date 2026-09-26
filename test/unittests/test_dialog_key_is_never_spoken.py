"""A locale with the intent and no dialog must not read the key aloud.

kab ships fuster_quotes.intent and no fuster_quotes.dialog. The renderer
this skill gets returns the KEY when a dialog is missing, so the device
said the word "fuster_quotes". OVOS-INTENT-2 4.2's reference renderer
raises for a missing dialog instead; neither behaviour is a sentence to
speak, so the skill answers in its own language or says nothing.
"""
import unittest

from ovos_utils.messagebus import FakeBus

from ovos_skill_fuster_quotes import JoanFusterQuotesSkill, DEFAULT_LANG

SKILL_ID = "ovos-skill-fuster-quotes.openvoiceos"
# kab has who_was_joan_fuster.dialog and lifespan.dialog, and no
# fuster_quotes.dialog. Both halves of the control live in one locale.
MISSING_IN_KAB = "fuster_quotes"
PRESENT_IN_KAB = "who_was_joan_fuster"


class TestDialogKeyIsNeverSpoken(unittest.TestCase):

    def _skill(self, lang):
        skill = JoanFusterQuotesSkill()
        skill._startup(FakeBus(), SKILL_ID)
        skill.config_core["lang"] = lang
        skill._lang_detector = None
        return skill

    def test_the_present_dialog_still_renders_in_kab(self):
        """Positive control: the helper returns kab text when kab has it."""
        skill = self._skill("kab")
        rendered = skill._render(PRESENT_IN_KAB)
        self.assertTrue(rendered)
        self.assertNotEqual(rendered, PRESENT_IN_KAB)
        with open("locale/kab/who_was_joan_fuster.dialog", encoding="utf-8") as f:
            kab_lines = [line.strip() for line in f if line.strip()]
        self.assertIn(rendered, kab_lines)

    def test_the_renderer_itself_returns_the_key(self):
        """The upstream behaviour this helper exists to absorb, asserted
        directly so it is visible without reading the helper: the renderer
        hands back the key, which is what the device used to say."""
        skill = self._skill("kab")
        self.assertEqual(
            skill.dialog_renderer.render(MISSING_IN_KAB, {}), MISSING_IN_KAB)

    def test_the_missing_dialog_never_returns_the_key(self):
        """The defect: kab has the intent and no fuster_quotes.dialog."""
        skill = self._skill("kab")
        rendered = skill._render(MISSING_IN_KAB)
        self.assertNotEqual(
            rendered, MISSING_IN_KAB,
            "the skill would read the resource key aloud")

    def test_the_missing_dialog_answers_in_the_default_lang(self):
        """And what it says instead is the skill's own language, not silence."""
        skill = self._skill("kab")
        rendered = skill._render(MISSING_IN_KAB)
        with open(f"locale/{DEFAULT_LANG}/{MISSING_IN_KAB}.dialog",
                  encoding="utf-8") as f:
            default_lines = [line.strip() for line in f if line.strip()]
        self.assertIn(rendered, default_lines)

    def test_a_handler_speaks_nothing_when_no_locale_has_the_dialog(self):
        """The last resort is silence, never the key."""
        skill = self._skill("kab")
        spoken = []
        skill.speak = lambda utt, *a, **kw: spoken.append(utt)
        skill.show_fuster = lambda utt: None
        skill._render = lambda key: ""
        skill._answer(MISSING_IN_KAB)
        self.assertEqual(spoken, [])


if __name__ == "__main__":
    unittest.main()
