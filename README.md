# Lottery Scraper Microservice v2

Production-grade, multi-source lottery results scraper with FastAPI integration endpoints for **maiorbichoo.com**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SCRAPER MICROSERVICE                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Nacional   │  │  Boa Sorte   │  │   Look   │  │ Bicho RJ │   │
│  │  Scraper     │  │  Scraper     │  │  Scraper │  │  Scraper │   │
│  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └────┬─────┘   │
│         └─────────────────┴───────────────┴─────────────┘         │
│                             │  (DrawSession[])                      │
│                    ┌────────▼────────┐                              │
│                    │  Pydantic        │  ← Schema validation        │
│                    │  models/schemas  │     (rejects bad data)      │
│                    └────────┬────────┘                              │
│              ┌──────────────┼───────────────┐                       │
│              ▼              ▼               ▼                       │
│      ┌───────────┐  ┌──────────────┐  ┌──────────────┐             │
│      │  JSON     │  │   CSV file   │  │  Webhook     │             │
│      │  storage  │  │  (flat rows) │  │  Dispatcher  │             │
│      └───────────┘  └──────────────┘  └──────┬───────┘             │
│                                               │ POST Bearer         │
└───────────────────────────────────────────────┼─────────────────────┘
                                                ▼
                                     maiorbichoo.com/api/webhooks/...

                FastAPI (inbound) ←── GET /api/v1/results/{source}
```

---

## Sources

| Source ID           | URL                                                                  | State |
|---------------------|----------------------------------------------------------------------|-------|
| `loteria_nacional`  | https://www.lotonacional.com.br/                                     | —     |
| `boa_sorte`         | https://www.resultadofacil.com.br/resultados-boa-sorte-de-hoje       | GO    |
| `look_loterias`     | https://www.resultadofacil.com.br/resultados-look-loterias-de-hoje   | GO    |
| `bicho_rj`          | https://www.resultadofacil.com.br/resultado-do-jogo-do-bicho/rj      | RJ    |

---

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set WEBHOOK_URL, WEBHOOK_API_KEY, API_SECRET_KEY
```

### 3. Run

```bash
# Scrape all sources once
python main.py oneshot

# Start scheduled service daemon
python main.py service

# Start API server only (for maiorbichoo.com to query)
python main.py api

# Scrape once then start API server
python main.py all
```

### 4. Test

```bash
pip install pytest
pytest tests/ -v
```

---

## API Endpoints

All endpoints (except `/health`) require:
```
Authorization: Bearer <API_SECRET_KEY>
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe (no auth) |
| GET | `/api/v1/results/latest` | Latest result per source |
| GET | `/api/v1/results/{source_id}` | Latest for one source |
| GET | `/api/v1/results/{source_id}/today` | All draws today |
| GET | `/api/v1/results/all/today` | All draws today, all sources |
| POST | `/api/v1/webhook/receive` | Receive external push |

**Valid `source_id` values:** `loteria_nacional`, `boa_sorte`, `look_loterias`, `bicho_rj`

Interactive docs: `http://localhost:8080/docs`

---

## Data Schema

Each draw session contains:

```json
{
  "source_id": "boa_sorte",
  "draw_date": "08/03/2026",
  "draw_time": "14:00",
  "state": "GO",
  "banca": null,
  "entries": [
    {
      "premio": 1,
      "milhar": "8086",
      "centena": "086",
      "dezena": "86",
      "complemento": "1913",
      "grupo": 22,
      "bicho": "Tigre"
    }
  ],
  "super5": null,
  "scraped_at_utc": "2026-03-08T17:30:00Z"
}
```

**Complemento rule:** `9999 - milhar`, zero-padded to 4 digits.  
Example: milhar `8086` → complemento `1913` (9999 - 8086 = 1913)

---

## Webhook Payload (outbound → maiorbichoo.com)

```json
{
  "source": "look_loterias",
  "draw_date": "18/02/2026",
  "draw_time": "14:00",
  "banca": null,
  "state": "GO",
  "numbers": ["3810", "1444", "5953", "4229", "9289"],
  "complementos": ["6189", "8555", "4046", "5770", "0710"],
  "super5": [2, 3, 9, 13, 22],
  "scraped_at_utc": "2026-02-18T17:30:00Z"
}
```

---

## Project Structure

```
lottery_scraper/
├── main.py                          # Entry point (oneshot/service/api/all)
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py                  # Pydantic settings (env-driven)
│   └── logging_setup.py             # Structured logging
├── models/
│   └── schemas.py                   # DrawEntry, DrawSession, ScrapedResult, WebhookPayload
├── scrapers/
│   ├── http_client.py               # Async httpx + stealth headers + retry
│   ├── base_scraper.py              # Abstract base class
│   ├── nacional_scraper.py          # lotonacional.com.br
│   └── resultado_facil_scraper.py   # Boa Sorte + Look + Bicho RJ
├── storage/
│   ├── storage_manager.py           # JSON + CSV persistence
│   └── webhook_dispatcher.py        # Outbound POST to maiorbichoo.com
├── api/
│   └── endpoints.py                 # FastAPI inbound endpoints
├── service/
│   └── orchestrator.py              # Run loop + APScheduler
└── tests/
    └── test_parsers.py              # Unit tests (no network required)
```
