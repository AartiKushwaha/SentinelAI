import base64
import binascii
import re
from collections.abc import Callable

from app.demo.data import PRIVATE
from app.targets.base import Interaction, Observation


class DemoTarget:
    """Small instruction interpreter. Fixture directives are data, never executable code."""

    def __init__(self, secured: bool, forbidden: set[str] | None = None):
        self.secured = secured
        self.forbidden = {"publish"} if forbidden is None else forbidden
        self.handlers: dict[str, Callable[[str], Observation]] = {}

    def interpret(self, text: str) -> Observation:
        directive = re.search(r"\[\[([a-z_]+):([^\]\n]{1,256})\]\]", text)
        if directive is None:
            return Observation(
                text="Ready to help with public support information.", decision="answered"
            )
        action, value = directive.groups()
        if action in self.handlers:
            return self.handlers[action](value)
        if action == "encoded":
            try:
                decoded = base64.b64decode(value, validate=True).decode()
            except (ValueError, UnicodeError, binascii.Error):
                return Observation(text="Invalid fixture encoding.", decision="denied")
            if "[[encoded:" in decoded:
                return Observation(text="Nested encoding denied.", decision="denied")
            return self.interpret(decoded)
        if action == "secret" and value in PRIVATE:
            if not self.secured:
                return Observation(text=PRIVATE[value], decision="answered")
        elif action == "publish" and (not self.secured or action not in self.forbidden):
            return Observation(text=value, decision="answered")
        return Observation(text="The support policy denied this request.", decision="denied")

    async def send(self, request: Interaction) -> Observation:
        text = request.messages[-1].content
        if text == "Apply my previous draft.":
            earlier = [m.content for m in request.messages[:-1] if m.role == "user"]
            text = earlier[-1] if earlier else ""
        elif text.startswith("Draft only:"):
            return Observation(text="Draft received.", decision="answered")
        return self.interpret(text)
