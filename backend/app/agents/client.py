"""Thin Anthropic wrapper (claude-sonnet-4-6). Lazy import so the app boots without the SDK.

Always degrades gracefully: no key / SDK missing / timeout -> caller uses templated fallback,
so the live thinking log and the brief never go blank during a demo.
"""
from __future__ import annotations

from collections.abc import Iterator

from ..config import settings


class AgentClient:
    @property
    def available(self) -> bool:
        if not settings.has_anthropic:
            return False
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return True

    def _client(self):
        import anthropic

        return anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str | None:
        """Non-streaming completion. Returns None on any failure (caller falls back)."""
        if not self.available:
            return None
        try:
            resp = self._client().messages.create(
                model=settings.agent_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        except Exception:
            return None

    def stream(self, system: str, user: str, max_tokens: int = 1024) -> Iterator[str] | None:
        """Token stream. Returns None if unavailable (caller streams the template instead)."""
        if not self.available:
            return None

        def _gen() -> Iterator[str]:
            with self._client().messages.stream(
                model=settings.agent_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as s:
                for text in s.text_stream:
                    yield text

        try:
            return _gen()
        except Exception:
            return None


agent_client = AgentClient()
