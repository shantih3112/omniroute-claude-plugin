"""Konfigurasjon lest fra miljøvariabler.

Hemmeligheter (bot-token, API-nøkler) leses KUN fra miljøet eller en .env-fil
som ikke sjekkes inn. Se .env.example for alle variabler.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

MODEL_VERSION = "dc-poisson-0.1+markedsblanding-w{w} (uvalidert)"

# API-Football liga-ID-er. Kontroller mot /leagues hos leverandøren før produksjon.
DEFAULT_LEAGUES: dict[int, str] = {
    39: "Premier League",
    40: "Championship",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    88: "Eredivisie",
    94: "Primeira Liga",
    103: "Eliteserien",
    104: "OBOS-ligaen",
    113: "Allsvenskan",
    119: "Superligaen",
    2: "Champions League",
    3: "Europa League",
    848: "Conference League",
}


def _load_dotenv(path: Path) -> None:
    """Minimal .env-leser (ingen ekstra avhengighet). Overstyrer ikke eksisterende miljø."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _parse_time(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _parse_leagues(value: str | None) -> dict[int, str]:
    if not value:
        return dict(DEFAULT_LEAGUES)
    out: dict[int, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        lid = int(part.split(":")[0])
        out[lid] = part.split(":", 1)[1] if ":" in part else DEFAULT_LEAGUES.get(lid, f"Liga {lid}")
    return out


@dataclass
class Config:
    telegram_token: str | None = None
    owner_telegram_id: int | None = None
    publish_channel_id: int | None = None  # Av som standard. Settes kun etter uttrykkelig beslutning.

    data_provider: str = "demo"  # "demo" eller "apifootball"
    apifootball_key: str | None = None
    apifootball_daily_cap: int = 7000
    oddsapiio_key: str | None = None  # Valgfri tredjepartskilde for Norsk Tipping-odds (eksperimentell)
    oddsapiio_nt_bookmaker: str = "Norsk Tipping"

    db_path: str = "data/kampanalyse.db"
    timezone: str = "Europe/Oslo"
    research_time: time = time(6, 15)
    default_brief_time: time = time(8, 0)
    report_time: time = time(23, 30)
    leagues: dict[int, str] = field(default_factory=lambda: dict(DEFAULT_LEAGUES))

    # Analyseparametre
    model_weight: float = 0.25          # Andel av modellens avvik fra markedet som brukes (krymping)
    min_edge: float = 0.03              # Minste forventede verdi (konservativ) for kvalifisering
    min_quality: float = 0.55           # Minste datakvalitet (0–1)
    min_leg_odds: float = 1.25
    max_single_odds: float = 6.0
    max_odds_age_minutes: int = 180     # Eldre odds regnes som utdaterte
    enable_cards: bool = False          # Kortmarkeder krever dommer-/lagdata – av som standard
    enable_corners: bool = False
    enable_live_betting: bool = False   # Livespill av som standard (krav i spesifikasjonen)

    # Overvåking
    live_poll_seconds: int = 60
    settle_confirm_minutes: int = 15    # Ventetid etter slutt før resultat regnes som bekreftet
    correction_check_hours: int = 3
    max_extra_rounds_per_day: int = 1
    stale_data_alert_minutes: int = 6

    @property
    def model_version(self) -> str:
        return MODEL_VERSION.format(w=self.model_weight)

    @property
    def demo(self) -> bool:
        return self.data_provider == "demo"

    @classmethod
    def from_env(cls, dotenv: str | Path | None = ".env") -> "Config":
        if dotenv:
            _load_dotenv(Path(dotenv))
        c = cls()
        c.telegram_token = _env("TELEGRAM_BOT_TOKEN")
        owner = _env("OWNER_TELEGRAM_ID")
        c.owner_telegram_id = int(owner) if owner else None
        ch = _env("PUBLISH_CHANNEL_ID")
        c.publish_channel_id = int(ch) if ch else None
        c.data_provider = _env("DATA_PROVIDER", "demo")
        c.apifootball_key = _env("APIFOOTBALL_KEY")
        c.apifootball_daily_cap = int(_env("APIFOOTBALL_DAILY_CAP", "7000"))
        c.oddsapiio_key = _env("ODDSAPIIO_KEY")
        c.db_path = _env("DB_PATH", c.db_path)
        c.timezone = _env("TZ_NAME", c.timezone)
        c.research_time = _parse_time(_env("RESEARCH_TIME", "06:15"))
        c.default_brief_time = _parse_time(_env("BRIEF_TIME", "08:00"))
        c.report_time = _parse_time(_env("REPORT_TIME", "23:30"))
        c.leagues = _parse_leagues(_env("LEAGUES"))
        c.model_weight = float(_env("MODEL_WEIGHT", str(c.model_weight)))
        c.min_edge = float(_env("MIN_EDGE", str(c.min_edge)))
        c.min_quality = float(_env("MIN_QUALITY", str(c.min_quality)))
        c.enable_cards = _env("ENABLE_CARDS", "0") == "1"
        c.enable_corners = _env("ENABLE_CORNERS", "0") == "1"
        c.live_poll_seconds = int(_env("LIVE_POLL_SECONDS", str(c.live_poll_seconds)))
        c.max_extra_rounds_per_day = int(_env("MAX_EXTRA_ROUNDS", str(c.max_extra_rounds_per_day)))
        if c.data_provider == "apifootball" and not c.apifootball_key:
            raise ValueError("DATA_PROVIDER=apifootball krever APIFOOTBALL_KEY")
        if c.max_extra_rounds_per_day > 1:
            raise ValueError("MAX_EXTRA_ROUNDS kan ikke overstige 1 (ansvarlighetsgrense)")
        return c
