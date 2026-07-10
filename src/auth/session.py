"""Minimal live session token registry used by the Busleyden Guard proof."""


class SessionRegistry:
    def __init__(self) -> None:
        self._used_tokens: set[str] = set()

    def accept(self, token: str) -> bool:
        if token in self._used_tokens:
            return False
        self._used_tokens.add(token)
        return True