# Lottery Scraper Microservice

**What it does:**  
This Python script visits a lottery results website, extracts the 5 winning numbers, and sends them to your Laravel backend via a secure webhook. It can run once (for testing) or run as a background service that retries automatically if the results are delayed.

---

## 1️⃣ High‑level flow (easy to picture)

```
Scheduler (11:30, 14:30, 19:30) → Scrape → Validate → POST (Bearer token) → Laravel
```

- **Scheduler:** Starts at the times you set.
- **Scrape:** Opens a browser (Playwright), waits for the results table, reads the 5 numbers.
- **Validate:** Checks that we really got 5 numbers and they are in the expected range.
- **POST:** Sends a JSON payload to your Laravel API using a secret Bearer token.
- **Retry:** If the results aren’t ready yet, it tries again every 30 s for up to 15 min.

---

## 2️⃣ How to run it

### Install dependencies

```bash
python -m pip install -r requirements.txt
playwright install chromium
```

### Create a `.env` file

Copy `.env.example` to `.env` and edit:

```env
# Where to scrape
SCRAPER_TARGET_URL=https://www.resultadofacil.com.br/resultados-loteria-tradicional-de-hoje

# When to run (comma‑separated HH:MM)
SCRAPER_SCHEDULE_TIMES=11:30,14:30,19:30

# Retry behavior
SCRAPER_RETRY_INTERVAL_SECONDS=30
SCRAPER_RETRY_MAX_MINUTES=15

# Laravel webhook
WEBHOOK_URL=http://localhost:8000/api/webhooks/lottery-results
WEBHOOK_API_KEY=change-me

# Runtime
SCRAPER_HEADLESS=true
SCRAPER_DEBUG=false
LOG_LEVEL=INFO
```

### One‑shot (test)

```bash
set SCRAPER_MODE=oneshot
python phase2_stealth_scraper.py
```

You’ll see the JSON printed on the console.

### Service mode (production)

```bash
set SCRAPER_MODE=service
python phase2_stealth_scraper.py
```

It will stay running, wake up at the scheduled times, and log everything.

---

## 3️⃣ Derived numbers rule (the “9999 complement”)

**Why we do it:**  
Some lottery strategies ask for the “complement” of each winning number.  
For a 4‑digit milhar, the complement is `9999 - original`.  
We always keep 4 digits by zero‑padding.

**Example:**  
Original numbers scraped from the site: `[8069, 1527, 8398, 2121, 6570]`  
Derived numbers:
```
9999 - 8069 = 1930
9999 - 1527 = 8472
9999 - 8398 = 1601
9999 - 2121 = 7878
9999 - 6570 = 3429
```
Result: `["1930", "8472", "1601", "7878", "3429"]`

**In the code:**  
```python
def _derive_complements(self, numbers: list[int]) -> list[str]:
    # Derivation rule: complement of 9999 (derived = 9999 - original), zero-padded to 4 digits.
    return [f"{(9999 - n):04d}" for n in numbers]
```
The derived list is stored in `derived_numbers` and sent together with the originals in the webhook payload.

---

## 4️⃣ What the code actually does (step by step)

### a) Configuration (`.env` → Python objects)

- `ScraperConfig` holds URLs, timeouts, headless mode.
- `WebhookDispatcher` holds the Laravel URL and the secret Bearer token.
- All values come from environment variables, so you can change them without touching the code.

### b) Scraper (`LotonacionalScraper`)

- Launches a Chromium browser.
- Navigates to the target URL.
- Waits until the results table is visible.
- Reads the 5 “Milhar” numbers from the table.
- **Generates 5 derived numbers** using the rule: **`derived = 9999 - original`**  
  - Example: `9999 - 8069 = 1930`
  - Each result is zero‑padded to 4 digits (e.g., `"0756"` not `"756"`).
- Returns a `LotteryDraw` object (Pydantic model) that contains:
  - `source_url`
  - `extracted_at_utc`
  - `draw_id` / `draw_date` (text from the page)
  - `numbers` (original 5 ints)
  - `derived_numbers` (5 strings like `"0756"`)

### c) Retry wrapper (`LotteryScraperService.run_once_with_retry`)

- Calls the scraper.
- If the page isn’t ready (`TimeoutError`) → wait 30 s and try again.
- If the data is invalid (`ValidationError`) → stop (won’t fix by retrying).
- If Laravel returns 4xx/5xx → log and stop.
- Stops after 15 min of retries.

### d) Scheduler (`run_service`)

- Uses `APScheduler` with `CronTrigger`.
- For each time in `SCRAPER_SCHEDULE_TIMES`, it registers a job.
- Jobs run asynchronously (`asyncio.create_task`) so the service stays responsive.
- The service runs forever (`await asyncio.Event().wait()`).

### e) Webhook (`WebhookDispatcher.post_result`)

- Builds JSON payload from the `LotteryDraw` model.
- Sends `POST` with:
  - `Authorization: Bearer <API_KEY>`
  - `Content-Type: application/json`
- Checks response status; raises if it’s 4xx/5xx.

---

## 4️⃣ Logs you’ll see

```
2026-02-26 11:30:00 | INFO     | lotonacional.phase2 | Scheduled run started
2026-02-26 11:30:02 | INFO     | lotonacional.phase2 | Using User-Agent: Mozilla/5.0...
2026-02-26 11:30:05 | INFO     | lotonacional.phase2 | Extracted ResultadoFacil Loteria Tradicional numbers=3950,4113,4996,2820,3215
2026-02-26 11:30:06 | INFO     | lotonacional.phase2 | Webhook delivered successfully
```

If something goes wrong, you’ll see warnings/errors and the retry attempts.

---

## 5️⃣ Why it’s built this way

| Concern | How we solved it |
|---------|------------------|
| **Reliability** | Scheduler + retry loop (30 s × 15 min) |
| **Security** | Bearer token from `.env`; never hard‑coded |
| **Observability** | Structured logs; you can pipe to a file (`LOG_FILE=scraper_service.log`) |
| **Maintainability** | Core scraper unchanged; wrapped in service classes |
| **Flexibility** | All URLs, times, and behavior are env‑driven |

---

## 6️⃣ What you need to tell your team

- “We have a **microservice** that runs on a schedule, scrapes the lottery site, and pushes the results to our Laravel API.”
- “It retries automatically if the results are delayed, so we don’t miss a draw.”
- “All secrets and URLs are in `.env`; we can change the target site or schedule without code changes.”
- “The webhook uses a Bearer token, so only our Laravel backend can accept the payload.”
- “If Laravel is down, the scraper logs the error and keeps the scheduler running for the next run.”

---

## 7️⃣ Next steps (Phase 2)

Your Laravel side will need:
- `POST /api/webhooks/lottery-results`
- Middleware to verify the Bearer token
- FormRequest validation
- A Job (`ProcessLotteryResultJob`) that will run the settlement logic later

---

## 8️⃣ Quick checklist for today’s demo

- [ ] Show the `.env.example` and explain the variables.
- [ ] Run `SCRAPER_MODE=oneshot` and show the JSON output.
- [ ] Explain the **derived numbers rule** (`9999 - original`) and show how they appear in the JSON.
- [ ] Switch to `SCRAPER_MODE=service` and show the scheduler log.
- [ ] Explain the retry loop (you can trigger a failure by changing the URL to a bogus page).
- [ ] Mention the webhook payload format (draw_id, date, numbers, derived_numbers).

---

**That’s it!**  
You now have a clean, scheduled, secure scraper that talks to Laravel. 🚀
