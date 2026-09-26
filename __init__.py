from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.ovos import OVOSSkill

# The language this skill is written in. A locale that ships the intent and
# not the dialog renders in this one instead of reading a key aloud.
DEFAULT_LANG = "en-US"


class JoanFusterQuotesSkill(OVOSSkill):

    def _render(self, key: str) -> str:
        """Render a dialog in the session language, and never return the key.

        OVOS-INTENT-2 4.2's reference renderer raises FileNotFoundError when a
        dialog does not exist for a language. The MustacheDialogRenderer this
        skill still gets returns the KEY instead, so a locale that ships
        fuster_quotes.intent and no fuster_quotes.dialog makes the device say
        the word "fuster_quotes" out loud. kab is that locale today.

        The session language comes first. When it has no such dialog, the
        skill's own language answers, which is a quote in another language and
        still an answer. When neither has it, the caller gets nothing and says
        nothing.
        """
        renderer = self.dialog_renderer
        if renderer is not None:
            rendered = renderer.render(key, {})
            if rendered and rendered != key:
                return rendered
        if self.lang != DEFAULT_LANG:
            fallback = self.load_lang(self.res_dir, DEFAULT_LANG).dialog_renderer
            if fallback is not None:
                rendered = fallback.render(key, {})
                if rendered and rendered != key:
                    self.log.warning(
                        f"no '{key}' dialog for {self.lang}; answered in "
                        f"{DEFAULT_LANG}")
                    return rendered
        self.log.error(f"no '{key}' dialog for {self.lang} or {DEFAULT_LANG}; "
                       f"saying nothing rather than the key")
        return ""

    def _answer(self, key: str):
        """Speak and show one dialog, or stay silent when it does not exist."""
        utterance = self._render(key)
        if not utterance:
            return
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()

    def show_fuster(self, utterance: str):
        self.gui.show_image("fuster.png",
                            caption=utterance,
                            override_idle=10,
                            override_animations=True,
                            fill='PreserveAspectFit')

    @intent_handler("fuster_quotes.intent")
    def handle_quote(self, message):
        self._answer("fuster_quotes")

    @intent_handler("fuster_lifespan.intent")
    def handle_lifespan(self, message):
        self._answer("lifespan")

    @intent_handler("who.intent")
    def handle_who(self, message):
        self._answer("who_was_joan_fuster")
