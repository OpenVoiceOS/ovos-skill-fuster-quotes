from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills.ovos import OVOSSkill


# TODO - make it a common query skill
class JoanFusterQuotesSkill(OVOSSkill):

    def show_fuster(self, utterance: str):
        self.gui.show_image("fuster.png",
                            caption=utterance,
                            override_idle=10,
                            override_animations=True,
                            fill='PreserveAspectFit')

    @intent_handler("fuster_quotes.intent")
    def handle_quote(self, message):
        utterance = self.dialog_renderer.render("fuster_quotes", {})
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()

    @intent_handler("FusterLive.intent")
    def handle_live(self, message):
        utterance = self.dialog_renderer.render("live", {})
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()

    @intent_handler("FusterBirth.intent")
    def handle_birth(self, message):
        utterance = self.dialog_renderer.render("when_was_joan_fuster_born", {})
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()

    @intent_handler("FusterDeath.intent")
    def handle_death(self, message):
        utterance = self.dialog_renderer.render("when_did_joan_fuster_die", {})
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()

    @intent_handler("who.intent")
    def handle_who(self, message):
        utterance = self.dialog_renderer.render("who_was_joan_fuster", {})
        self.show_fuster(utterance)
        self.speak(utterance, wait=True)
        self.gui.release()
