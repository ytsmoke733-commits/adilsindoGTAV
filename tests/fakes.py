from __future__ import annotations


class FakeLLM:
    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, dict]] = []

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls.append((system, user, schema))
        reply = self.replies.pop(0)
        return reply(user) if callable(reply) else reply
