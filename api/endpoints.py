"""
api/endpoints.py
────────────────
FastAPI application exposing lottery results to maiorbichoo.com (and any
other consumer). This is the INBOUND side — the scraper writes to storage,
these endpoints read from it and serve the data.

Authentication: Bearer token (same API_SECRET_KEY from .env)

Endpoints:
  GET  /health                           → liveness probe
  GET  /api/v1/results/latest            → latest result across all sources
  GET  /api/v1/results/{source_id}       → latest result for one source
  GET  /api/v1/results/{source_id}/today → all draws today for one source
  GET  /api/v1/results/all/today         → all draws today across all sources
  POST /api/v1/webhook/receive           → receive push from external source (optional)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from models.schemas import SourceID
from storage.storage_manager import StorageManager

log = logging.getLogger("api")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESPONSE SCHEMAS  (separate from scraper models — API contract)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EntryResponse(BaseModel):
    premio: int
    milhar: str
    centena: str
    dezena: str
    complemento: Optional[str]
    grupo: int
    bicho: str


class SessionResponse(BaseModel):
    source_id: str
    draw_date: str
    draw_time: str
    state: Optional[str]
    banca: Optional[str]
    entries: List[EntryResponse]
    super5: Optional[List[int]]
    scraped_at_utc: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"


class ResultsResponse(BaseModel):
    count: int
    sessions: List[SessionResponse]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APP FACTORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_security = HTTPBearer()


def _make_auth_checker(secret_key: str):
    def verify_token(
        credentials: HTTPAuthorizationCredentials = Security(_security),
    ) -> None:
        if credentials.credentials != secret_key:
            log.warning("API: Unauthorised request — invalid token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
    return verify_token


def _session_dict_to_response(s: dict) -> SessionResponse:
    entries = [
        EntryResponse(
            premio=e["premio"],
            milhar=e["milhar"],
            centena=e["centena"],
            dezena=e["dezena"],
            complemento=e.get("complemento"),
            grupo=e["grupo"],
            bicho=e["bicho"],
        )
        for e in s.get("entries", [])
    ]
    super5 = s.get("super5")
    super5_nums = super5["numbers"] if super5 else None

    return SessionResponse(
        source_id=s["source_id"],
        draw_date=s["draw_date"],
        draw_time=s["draw_time"],
        state=s.get("state"),
        banca=s.get("banca"),
        entries=entries,
        super5=super5_nums,
        scraped_at_utc=s.get("scraped_at_utc", ""),
    )


def create_app(storage: StorageManager, api_secret_key: str) -> FastAPI:
    app = FastAPI(
        title="Lottery Results API",
        description="Serves scraped lottery results to maiorbichoo.com",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    auth = _make_auth_checker(api_secret_key)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["Infra"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    # ── Latest across all sources ─────────────────────────────────────────────
    @app.get(
        "/api/v1/results/latest",
        response_model=ResultsResponse,
        tags=["Results"],
        dependencies=[Depends(auth)],
    )
    async def get_all_latest() -> ResultsResponse:
        sessions = []
        for source in SourceID:
            s = storage.get_latest_session(source.value)
            if s:
                sessions.append(_session_dict_to_response(s))
        return ResultsResponse(count=len(sessions), sessions=sessions)

    # ── Latest for one source ─────────────────────────────────────────────────
    @app.get(
        "/api/v1/results/{source_id}",
        response_model=ResultsResponse,
        tags=["Results"],
        dependencies=[Depends(auth)],
    )
    async def get_latest_by_source(source_id: str) -> ResultsResponse:
        _validate_source(source_id)
        s = storage.get_latest_session(source_id)
        if not s:
            raise HTTPException(status_code=404, detail=f"No results for {source_id!r}")
        return ResultsResponse(count=1, sessions=[_session_dict_to_response(s)])

    # ── Today's draws for one source ──────────────────────────────────────────
    @app.get(
        "/api/v1/results/{source_id}/today",
        response_model=ResultsResponse,
        tags=["Results"],
        dependencies=[Depends(auth)],
    )
    async def get_today_by_source(source_id: str) -> ResultsResponse:
        _validate_source(source_id)
        today = datetime.now().strftime("%d/%m/%Y")
        records = storage.get_today_sessions(source_id, today)
        sessions = [_session_dict_to_response(r) for r in records]
        return ResultsResponse(count=len(sessions), sessions=sessions)

    # ── Today's draws across ALL sources ─────────────────────────────────────
    @app.get(
        "/api/v1/results/all/today",
        response_model=ResultsResponse,
        tags=["Results"],
        dependencies=[Depends(auth)],
    )
    async def get_all_today() -> ResultsResponse:
        today = datetime.now().strftime("%d/%m/%Y")
        sessions = []
        for source in SourceID:
            records = storage.get_today_sessions(source.value, today)
            sessions.extend(_session_dict_to_response(r) for r in records)
        sessions.sort(key=lambda s: (s.draw_date, s.draw_time))
        return ResultsResponse(count=len(sessions), sessions=sessions)

    # ── Optional: receive push from an external scraper / trusted partner ─────
    @app.post(
        "/api/v1/webhook/receive",
        status_code=status.HTTP_202_ACCEPTED,
        tags=["Webhook"],
        dependencies=[Depends(auth)],
    )
    async def receive_webhook(payload: dict) -> dict:
        log.info(f"API: Received external webhook payload: {list(payload.keys())}")
        # Extension point — validate and store externally pushed results here
        return {"status": "accepted"}

    return app


def _validate_source(source_id: str) -> None:
    valid = {s.value for s in SourceID}
    if source_id not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source_id '{source_id}'. Valid: {sorted(valid)}",
        )
