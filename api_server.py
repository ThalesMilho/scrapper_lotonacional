"""
api_server.py
═════════════════════════════════════════════════════════════════
FastAPI server for the lottery scraper microservice.

Reads directly from all.json (written by bicho_scraper.py).
Exposes rich /docs UI for the other dev to explore + integrate.

Install:
    pip install fastapi uvicorn python-dotenv

Run alongside the scraper:
    .\\venv\\Scripts\\python.exe api_server.py

Then open:
    http://localhost:8080/docs     ← Swagger UI
    http://localhost:8080/redoc    ← ReDoc UI
    http://localhost:8080/health   ← no auth needed

All other endpoints require:
    Authorization: Bearer <API_SECRET_KEY from .env>
═════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────

ALL_JSON_PATH   = os.getenv("SCRAPER_OUTPUT",  "all.json")
API_HOST        = os.getenv("API_HOST",        "0.0.0.0")
API_PORT        = int(os.getenv("API_PORT",    "8080"))
API_SECRET_KEY  = os.getenv("API_SECRET_KEY",  "change-me-api-key")
LOG_LEVEL       = os.getenv("LOG_LEVEL",       "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("api_server")

# ── Auth ──────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)

def _require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> None:
    if API_SECRET_KEY == "change-me-api-key":
        return  # dev mode — auth disabled
    if not credentials or credentials.credentials != API_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token. Set API_SECRET_KEY in .env",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── Data loader ───────────────────────────────────────────────────────────────

def _load_all_json() -> Dict[str, Any]:
    path = Path(ALL_JSON_PATH)
    if not path.exists():
        return {"_meta": {}, "draws": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error(f"Failed to read {ALL_JSON_PATH}: {exc}")
        return {"_meta": {}, "draws": []}

def _get_draws() -> List[Dict[str, Any]]:
    return _load_all_json().get("draws", [])

def _get_meta() -> Dict[str, Any]:
    return _load_all_json().get("_meta", {})

# ── Response models ───────────────────────────────────────────────────────────

class ResultEntry(BaseModel):
    pos:            int
    milhar:         str
    milhar_inv:     str
    centena:        str
    centena_esq:    str
    centena_inv:    str
    centena_inv_esq:str
    dezena:         str
    unidade:        str
    grupo:          int
    animal:         str
    animal_mismatch:bool

class Modalities(BaseModel):
    CENTENA:         Optional[str]
    CENTENA_INV:     Optional[str]
    CENTENA_INV_ESQ: Optional[str]
    CENTENA_ESQ:     Optional[str]
    MILHAR:          Optional[str]
    MILHAR_CT:       Optional[List[str]]
    MILHAR_INV:      Optional[str]
    UNIDADE:         Optional[str]
    DEZENA:          Optional[str]
    DUQUE_DEZ:       Optional[List[str]]
    TERNO_DEZ:       Optional[List[str]]
    SECO_TERNO_DEZ:  Optional[List[str]]
    GRUPO:           Optional[Dict[str, Any]]
    DUQUE_GP:        Optional[List[int]]
    TERNO_GP:        Optional[List[int]]
    QUADRA_GP:       Optional[List[int]]
    QUINA_GP:        Optional[List[int]]
    QUINA_GP_ESQ:    Optional[List[str]]
    QUINA_GP_MEIO:   Optional[List[str]]
    SENA_GP:         Optional[List[int]]
    SENA_GP_ESQ:     Optional[List[str]]
    SENA_GP_MEIO:    Optional[List[str]]
    PASSE_VAI:       Optional[int]
    PASSE_VAI_VEM:   Optional[bool]
    PALPITAO:        Optional[Dict[str, Any]]

class DrawResponse(BaseModel):
    source:          str
    lottery:         str
    variant:         str
    date:            str
    time:            str
    incomplete:      bool
    duplicate:       bool
    unknown_lottery: bool
    passe_pending:   bool
    results:         List[ResultEntry]
    modalities:      Modalities

class DrawsResponse(BaseModel):
    total:           int
    scraped_at:      Optional[str]
    draws:           List[DrawResponse]

class HealthResponse(BaseModel):
    status:          str
    server_time_utc: str
    last_scrape_at:  Optional[str]
    total_draws:     int
    sources_loaded:  List[str]
    sources_failed:  List[str]

class MetaResponse(BaseModel):
    date:               Optional[str]
    scraped_at:         Optional[str]
    total_draws_found:  Optional[int]
    sources_loaded:     List[str]
    sources_failed:     List[str]
    warnings:           List[str]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_draw_response(d: Dict[str, Any]) -> DrawResponse:
    results = [
        ResultEntry(
            pos=r["pos"],
            milhar=r["milhar"],
            milhar_inv=r.get("milhar_inv", ""),
            centena=r["centena"],
            centena_esq=r.get("centena_esq", ""),
            centena_inv=r.get("centena_inv", ""),
            centena_inv_esq=r.get("centena_inv_esq", ""),
            dezena=r["dezena"],
            unidade=r.get("unidade", ""),
            grupo=r["group_id"],
            animal=r["animal"],
            animal_mismatch=r.get("animal_mismatch", False),
        )
        for r in d.get("results", [])
    ]
    return DrawResponse(
        source=d["source"],
        lottery=d["lottery"],
        variant=d.get("variant", "NORMAL"),
        date=d["date"],
        time=d["time"],
        incomplete=d.get("incomplete", False),
        duplicate=d.get("duplicate", False),
        unknown_lottery=d.get("unknown_lottery", False),
        passe_pending=d.get("passe_pending", False),
        results=results,
        modalities=Modalities(**d.get("modalities", {})),
    )

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="🎰 Lottery Results API",
    description="""
## Lottery Microservice — maiorbicho.com integration

Scrapes **5 sources** from resultadofacil.com.br and exposes the results here.

### Sources
| Key | Lottery | Draw times (BRT) |
|-----|---------|-----------------|
| `SRC_NACIONAL` | Nacional | 02h 08h 10h 12h 15h 17h |
| `SRC_BOA_SORTE` | Boa Sorte GO | 09h 11h 14h 16h 18h |
| `SRC_LOOK` | Look Loterias GO | 07h 09h 11h 14h 16h 18h |
| `SRC_PT_RIO` | PT-RIO RJ | 09h 11h 14h 16h 18h |
| `SRC_LOTEP` | LOTEP PB | 10:45 12:45 15:45 18h |

### Authentication
All endpoints except `/health` and `/meta` require:
```
Authorization: Bearer <API_SECRET_KEY>
```
Set `API_SECRET_KEY=change-me-api-key` in `.env` to disable auth during development.

### Modalities reference
Each draw exposes full modalities: `MILHAR`, `CENTENA`, `DEZENA`, `DUQUE_DEZ`,
`TERNO_DEZ`, `GRUPO`, `DUQUE_GP`, `TERNO_GP`, `QUADRA_GP`, `QUINA_GP`,
`QUINA_GP_ESQ`, `QUINA_GP_MEIO`, `PASSE_VAI`, `PASSE_VAI_VEM`, `PALPITAO`.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── GET /health ───────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Infra"],
    summary="Liveness probe — no auth required",
)
async def health() -> HealthResponse:
    meta = _get_meta()
    draws = _get_draws()
    return HealthResponse(
        status="ok",
        server_time_utc=datetime.utcnow().isoformat() + "Z",
        last_scrape_at=meta.get("scraped_at"),
        total_draws=len(draws),
        sources_loaded=meta.get("sources_loaded", []),
        sources_failed=meta.get("sources_failed", []),
    )

# ── GET /meta ─────────────────────────────────────────────────────────────────

@app.get(
    "/meta",
    response_model=MetaResponse,
    tags=["Infra"],
    summary="Last scrape metadata — no auth required",
)
async def meta() -> MetaResponse:
    m = _get_meta()
    return MetaResponse(
        date=m.get("date"),
        scraped_at=m.get("scraped_at"),
        total_draws_found=m.get("total_draws_found"),
        sources_loaded=m.get("sources_loaded", []),
        sources_failed=m.get("sources_failed", []),
        warnings=m.get("warnings", []),
    )

# ── GET /results ──────────────────────────────────────────────────────────────

@app.get(
    "/api/v1/results",
    response_model=DrawsResponse,
    tags=["Results"],
    dependencies=[Depends(_require_auth)],
    summary="All draws — filterable by source, lottery, date, time",
)
async def get_results(
    source:   Optional[str] = Query(None, description="e.g. SRC_NACIONAL, SRC_PT_RIO"),
    lottery:  Optional[str] = Query(None, description="e.g. LT_NACIONAL, LT_PT_RIO"),
    date:     Optional[str] = Query(None, description="dd/mm/yyyy"),
    time:     Optional[str] = Query(None, description="HH:MM"),
    complete: Optional[bool]= Query(None, description="true = only complete draws (5 or 10 results)"),
) -> DrawsResponse:
    draws = _get_draws()
    meta  = _get_meta()

    if source:
        draws = [d for d in draws if d.get("source") == source.upper()]
    if lottery:
        draws = [d for d in draws if d.get("lottery") == lottery.upper()]
    if date:
        draws = [d for d in draws if d.get("date") == date]
    if time:
        draws = [d for d in draws if d.get("time") == time]
    if complete is not None:
        draws = [d for d in draws if not d.get("incomplete") == complete]

    return DrawsResponse(
        total=len(draws),
        scraped_at=meta.get("scraped_at"),
        draws=[_to_draw_response(d) for d in draws],
    )

# ── GET /results/today ────────────────────────────────────────────────────────

@app.get(
    "/api/v1/results/today",
    response_model=DrawsResponse,
    tags=["Results"],
    dependencies=[Depends(_require_auth)],
    summary="All draws from today (server date, BRT)",
)
async def get_today() -> DrawsResponse:
    today = datetime.now().strftime("%d/%m/%Y")
    draws = [d for d in _get_draws() if d.get("date") == today]
    return DrawsResponse(
        total=len(draws),
        scraped_at=_get_meta().get("scraped_at"),
        draws=[_to_draw_response(d) for d in draws],
    )

# ── GET /results/latest ───────────────────────────────────────────────────────

@app.get(
    "/api/v1/results/latest",
    response_model=DrawsResponse,
    tags=["Results"],
    dependencies=[Depends(_require_auth)],
    summary="Latest draw per source (most recent time per source)",
)
async def get_latest() -> DrawsResponse:
    draws = _get_draws()
    seen: Dict[str, Dict] = {}
    for d in draws:
        src = d.get("source", "?")
        if src not in seen or d.get("time", "") > seen[src].get("time", ""):
            seen[src] = d
    result = sorted(seen.values(), key=lambda d: d.get("source", ""))
    return DrawsResponse(
        total=len(result),
        scraped_at=_get_meta().get("scraped_at"),
        draws=[_to_draw_response(d) for d in result],
    )

# ── GET /results/{source} ─────────────────────────────────────────────────────

@app.get(
    "/api/v1/results/{source}",
    response_model=DrawsResponse,
    tags=["Results"],
    dependencies=[Depends(_require_auth)],
    summary="All draws for one source today",
)
async def get_by_source(source: str) -> DrawsResponse:
    valid = {"SRC_NACIONAL", "SRC_BOA_SORTE", "SRC_LOOK", "SRC_PT_RIO", "SRC_LOTEP"}
    if source.upper() not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Valid: {sorted(valid)}",
        )
    draws = [d for d in _get_draws() if d.get("source") == source.upper()]
    if not draws:
        raise HTTPException(status_code=404, detail=f"No draws found for source '{source}'")
    return DrawsResponse(
        total=len(draws),
        scraped_at=_get_meta().get("scraped_at"),
        draws=[_to_draw_response(d) for d in draws],
    )

# ── GET /results/{source}/latest ─────────────────────────────────────────────

@app.get(
    "/api/v1/results/{source}/latest",
    response_model=DrawsResponse,
    tags=["Results"],
    dependencies=[Depends(_require_auth)],
    summary="Most recent draw only for one source",
)
async def get_latest_by_source(source: str) -> DrawsResponse:
    draws = [d for d in _get_draws() if d.get("source") == source.upper()]
    if not draws:
        raise HTTPException(status_code=404, detail=f"No draws found for '{source}'")
    latest = max(draws, key=lambda d: d.get("time", ""))
    return DrawsResponse(
        total=1,
        scraped_at=_get_meta().get("scraped_at"),
        draws=[_to_draw_response(latest)],
    )

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"Starting API server on http://{API_HOST}:{API_PORT}")
    log.info(f"Docs: http://localhost:{API_PORT}/docs")
    log.info(f"Auth: {'DISABLED (dev mode)' if API_SECRET_KEY == 'change-me-api-key' else 'ENABLED'}")
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
    )
