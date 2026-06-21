"""Environment-driven settings. One SEED drives all synthetic generators (reproducible demo).

Kept dependency-light on purpose: reads backend/.env via python-dotenv if present, else the
process environment. No hard failure if .env is missing — the scaffold must always boot.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../ClimateHack/backend
REPO_ROOT = _BACKEND_DIR.parent  # .../ClimateHack
DATA_DIR = REPO_ROOT / "data"

try:  # best-effort .env load; absence is fine. Load root .env first, backend/.env overrides it.
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(_BACKEND_DIR / ".env", override=True)
except Exception:  # pragma: no cover - dotenv optional at scaffold stage
    pass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # agent layer
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    agent_model: str = "claude-sonnet-4-6"

    # live feeds (B3)
    metoffice_api_key: str = field(default_factory=lambda: os.getenv("METOFFICE_API_KEY", ""))
    # hard daily cap on Met Office calls (Global Spot free tier = 360/day). Stay well under.
    metoffice_daily_cap: int = field(default_factory=lambda: _int("METOFFICE_DAILY_CAP", 300))
    live_data: bool = field(default_factory=lambda: _bool("LIVE_DATA", False))
    # DEMO_MODE: prefer committed pre-baked agent briefs (data/alerts.json) so the climax never
    # depends on a live Anthropic call (plan.md §13.10). Engine/feeds still run normally.
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", False))
    seed: int = field(default_factory=lambda: _int("SEED", 1337))
    refresh_seconds: int = field(default_factory=lambda: _int("REFRESH_SECONDS", 300))

    # agent ACT / dispatch (B5)
    dispatch_enabled: bool = field(default_factory=lambda: _bool("DISPATCH_ENABLED", False))
    gmail_user: str = field(default_factory=lambda: os.getenv("GMAIL_USER", ""))
    gmail_app_password: str = field(default_factory=lambda: os.getenv("GMAIL_APP_PASSWORD", ""))
    dispatch_to: str = field(default_factory=lambda: os.getenv("DISPATCH_TO", ""))

    # server
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:5174,http://localhost:5175",
            ).split(",")
            if o.strip()
        )
    )

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
