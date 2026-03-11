"""
models/schemas.py
─────────────────
Pydantic v2 models that define the canonical schema for every scraped result.
Every scraper MUST produce one of these validated objects — nothing else
is allowed into the storage or API layer.

Hierarchy:
  DrawEntry        → a single premio row (1º, 2º … 5º or 1º-10º)
  DrawSession      → one complete extraction at a specific time from one source
  ScrapedResult    → the top-level envelope pushed to storage / webhook
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SourceID(str, Enum):
    LOTERIA_NACIONAL  = "loteria_nacional"
    BOA_SORTE         = "boa_sorte"
    LOOK_LOTERIAS     = "look_loterias"
    BICHO_RJ          = "bicho_rj"


class DrawType(str, Enum):
    MILHAR   = "milhar"    # 4-digit
    CENTENA  = "centena"   # 3-digit
    DEZENA   = "dezena"    # 2-digit
    SUPER5   = "super5"    # Look's 5-ball bonus draw


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ATOMIC ROW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DrawEntry(BaseModel):
    """A single prize row — e.g. '1º | 0535 | 09 | Cobra'."""

    premio: int = Field(..., ge=1, le=10, description="Prize position (1–10)")
    milhar: str = Field(..., description="4-digit milhar string, zero-padded")
    centena: str = Field(..., description="Last 3 digits")
    dezena: str = Field(..., description="Last 2 digits")
    grupo: int = Field(..., ge=1, le=25)
    bicho: str = Field(..., min_length=2)

    @field_validator("milhar")
    @classmethod
    def validate_milhar(cls, v: str) -> str:
        v = v.strip().zfill(4)
        if not v.isdigit() or len(v) != 4:
            raise ValueError(f"Invalid milhar '{v}' — must be 4 digits")
        return v

    @model_validator(mode="after")
    def derive_sub_fields(self) -> "DrawEntry":
        """Auto-derive centena and dezena from milhar."""
        self.centena = self.milhar[-3:]
        self.dezena  = self.milhar[-2:]
        return self


class Super5Entry(BaseModel):
    """Look Loterias Super 5 bonus numbers (5 integers 1-30)."""
    numbers: List[int] = Field(..., min_length=5, max_length=5)

    @field_validator("numbers")
    @classmethod
    def validate_range(cls, v: List[int]) -> List[int]:
        for n in v:
            if not (1 <= n <= 30):
                raise ValueError(f"Super5 number {n} out of range 1-30")
        return v


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DRAW SESSION  (one extraction block on one page)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DrawSession(BaseModel):
    """
    One complete draw block, e.g. 'BOA SORTE - GOIÁS, 14h - 08/03/2026'.
    A single page may contain multiple DrawSessions (one per extraction time).
    """

    source_id: SourceID
    source_url: str
    draw_date: str          = Field(..., description="dd/mm/yyyy")
    draw_time: str          = Field(..., description="HH:MM (local BRT)")
    draw_label: str         = Field("", description="Full section title from page")
    state: Optional[str]    = Field(None, description="2-letter state UF, e.g. RJ")
    banca: Optional[str]    = Field(None, description="Sub-banca name, e.g. PTM")

    # Prize entries
    entries: List[DrawEntry] = Field(..., min_length=1)

    # Optional bonus
    super5: Optional[Super5Entry] = None

    # Soma / Mult rows (extra derived values some pages show)
    soma:   Optional[str] = None
    mult:   Optional[str] = None

    # Metadata
    scraped_at_utc: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("draw_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        v = v.strip()
        try:
            datetime.strptime(v, "%d/%m/%Y")
        except ValueError:
            raise ValueError(f"draw_date '{v}' must be dd/mm/yyyy")
        return v

    @field_validator("draw_time")
    @classmethod
    def normalise_time(cls, v: str) -> str:
        v = v.strip()
        # Accept "09h", "09:20", "9h" → normalise to "HH:MM"
        v = v.replace("h", ":00").replace("H", ":00")
        if ":" not in v:
            v = v + ":00"
        parts = v.split(":")
        return f"{int(parts[0]):02d}:{parts[1][:2]}"

    @property
    def first_milhar(self) -> str:
        """Convenience: the 1st prize milhar."""
        return next((e.milhar for e in self.entries if e.premio == 1), "")

    @property
    def session_id(self) -> str:
        """Unique key: source + date + time."""
        return f"{self.source_id.value}_{self.draw_date.replace('/','')}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOP-LEVEL ENVELOPE  (what storage + webhook receive)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScrapedResult(BaseModel):
    """
    Complete output of one scraper run — may contain multiple DrawSessions
    (e.g. all draws from a single page across multiple hours).
    """

    scrape_run_id: str      = Field(description="UUID for this run")
    source_id: SourceID
    total_sessions: int     = Field(0)
    sessions: List[DrawSession] = Field(default_factory=list)
    errors: List[str]       = Field(default_factory=list)
    completed_at_utc: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def sync_count(self) -> "ScrapedResult":
        self.total_sessions = len(self.sessions)
        return self


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBHOOK PAYLOAD  (what we POST to maiorbichoo.com)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WebhookPayload(BaseModel):
    """
    Slimmed-down payload sent outbound to maiorbichoo.com.
    Consumer expects: source, date, time, numbers array.
    """

    source: str
    draw_date: str
    draw_time: str
    banca: Optional[str]
    state: Optional[str]
    numbers: List[str]           # 1st-5th milhar values
    super5: Optional[List[int]]
    scraped_at_utc: str          # ISO 8601

    @classmethod
    def from_session(cls, session: DrawSession) -> "WebhookPayload":
        top5 = sorted(session.entries, key=lambda e: e.premio)[:5]
        return cls(
            source=session.source_id.value,
            draw_date=session.draw_date,
            draw_time=session.draw_time,
            banca=session.banca,
            state=session.state,
            numbers=[e.milhar for e in top5],
            super5=session.super5.numbers if session.super5 else None,
            scraped_at_utc=session.scraped_at_utc.isoformat() + "Z",
        )
