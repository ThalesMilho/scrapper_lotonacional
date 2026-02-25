"""
================================================================================
  PHASE 1 — Advanced Reconnaissance & Payload Analysis Script
  Target : lotonacional.com.br
  Author : Senior Data Extraction Engineer
  Purpose: Profile the target before building the production scraper.
================================================================================
"""

import time
import json
import random
import urllib.robotparser
from urllib.parse import urljoin, urlparse
import logging

# ── Third-party (install with: pip install requests beautifulsoup4 colorama)
try:
    import requests
    from bs4 import BeautifulSoup
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
except ImportError as e:
    raise SystemExit(
        f"\n[FATAL] Missing dependency: {e}\n"
        "Run:  pip install requests beautifulsoup4 colorama\n"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_URL   = "https://www.lotonacional.com.br"
ROBOTS_URL = urljoin(BASE_URL, "/robots.txt")

# Representative pages to probe — adjust if you know specific result URLs
PROBE_URLS = [
    BASE_URL + "/",
    BASE_URL + "/resultados",
    BASE_URL + "/resultado",
]

# Randomised User-Agent pool (modern desktop browsers)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",

    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

ACCEPT_LANGUAGE_POOL = [
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.8,en;q=0.6",
    "en-US,en;q=0.9,pt;q=0.8",
]

REQUEST_TIMEOUT = 20   # seconds
INTER_REQUEST_DELAY = (1.5, 3.5)  # random sleep range (seconds)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGGING SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("recon_report.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("recon")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section(title: str) -> None:
    bar = "═" * 70
    log.info(Fore.CYAN + f"\n{bar}\n  {title}\n{bar}")


def random_headers() -> dict:
    return {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept-Language": random.choice(ACCEPT_LANGUAGE_POOL),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,"
                           "image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":  "document",
        "Sec-Fetch-Mode":  "navigate",
        "Sec-Fetch-Site":  "none",
        "Sec-Fetch-User":  "?1",
        "DNT":             "1",
    }


def safe_get(session: requests.Session, url: str, **kwargs) -> requests.Response | None:
    headers = random_headers()
    log.debug(f"GET {url}  UA={headers['User-Agent'][:40]}…")
    try:
        start = time.perf_counter()
        r = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT,
                        allow_redirects=True, **kwargs)
        elapsed = time.perf_counter() - start
        log.info(f"  → HTTP {r.status_code}  |  {elapsed*1000:.0f} ms  |  "
                 f"Content-Type: {r.headers.get('Content-Type','—')[:60]}")
        return r
    except requests.exceptions.SSLError as exc:
        log.error(f"  SSL error on {url}: {exc}")
    except requests.exceptions.ConnectionError as exc:
        log.error(f"  Connection error on {url}: {exc}")
    except requests.exceptions.Timeout:
        log.warning(f"  Timeout after {REQUEST_TIMEOUT}s on {url}")
    except Exception as exc:
        log.error(f"  Unexpected error on {url}: {exc}")
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE 1 — ROBOTS.TXT ANALYSIS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyse_robots(session: requests.Session) -> dict:
    section("MODULE 1 — robots.txt & Crawl Policy")
    result = {
        "robots_url":       ROBOTS_URL,
        "fetch_status":     None,
        "raw_content":      None,
        "sitemap_urls":     [],
        "crawl_delay":      None,
        "disallowed_paths": [],
        "allowed_paths":    [],
    }

    r = safe_get(session, ROBOTS_URL)
    if r is None:
        log.warning("Could not fetch robots.txt — proceeding with caution.")
        return result

    result["fetch_status"] = r.status_code

    if r.status_code == 404:
        log.info("  robots.txt → 404 (no file present — no explicit restrictions)")
        return result

    raw = r.text
    result["raw_content"] = raw
    log.info(f"\n{'─'*60}\n{raw[:2000]}\n{'─'*60}")

    # Parse with stdlib robotparser
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(ROBOTS_URL)
    rp.parse(raw.splitlines())

    # Extract Sitemaps, Disallow, Allow lines manually (robotparser ignores them)
    for line in raw.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("sitemap:"):
            url = stripped.split(":", 1)[1].strip()
            result["sitemap_urls"].append(url)
            log.info(f"  📍 Sitemap found: {url}")
        elif low.startswith("crawl-delay:"):
            delay = stripped.split(":", 1)[1].strip()
            result["crawl_delay"] = delay
            log.info(f"  ⏱  Crawl-Delay directive: {delay}s")
        elif low.startswith("disallow:"):
            path = stripped.split(":", 1)[1].strip()
            result["disallowed_paths"].append(path)
        elif low.startswith("allow:"):
            path = stripped.split(":", 1)[1].strip()
            result["allowed_paths"].append(path)

    # Check our target paths
    log.info("\n  Checking scraper access for key paths:")
    test_paths = ["/", "/resultados", "/resultado", "/api/", "/wp-json/"]
    for path in test_paths:
        full = urljoin(BASE_URL, path)
        allowed = rp.can_fetch("*", full)
        colour = Fore.GREEN if allowed else Fore.RED
        status = "ALLOWED" if allowed else "DISALLOWED"
        log.info(f"  {colour}{status}{Style.RESET_ALL}  →  {path}")

    log.info(f"\n  Total Disallow rules : {len(result['disallowed_paths'])}")
    log.info(f"  Total Allow rules    : {len(result['allowed_paths'])}")
    return result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE 2 — HEADER & CHALLENGE PROBING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Known anti-bot / CDN fingerprint headers
CHALLENGE_HEADERS = {
    "cf-ray":                  "Cloudflare",
    "cf-cache-status":         "Cloudflare",
    "__cf_bm":                 "Cloudflare Bot Management",
    "x-sucuri-id":             "Sucuri WAF",
    "x-distil-cs":             "Distil Networks",
    "x-datadome":              "DataDome",
    "x-protected-by":          "Generic WAF",
    "server-timing":           "Server Timing (possible CDN)",
    "x-akamai-transformed":    "Akamai",
    "x-px-client-uuid":        "PerimeterX",
    "perimeterx":              "PerimeterX",
    "x-imperva-session":       "Imperva",
}

RATE_LIMIT_HEADERS = [
    "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
    "x-ratelimit-reset", "ratelimit-limit", "ratelimit-remaining",
]


def probe_headers(session: requests.Session) -> list[dict]:
    section("MODULE 2 — Header Probing & Anti-Bot Detection")
    results = []

    for url in PROBE_URLS:
        log.info(f"\n  Probing: {url}")
        time.sleep(random.uniform(*INTER_REQUEST_DELAY))

        r = safe_get(session, url)
        if r is None:
            results.append({"url": url, "error": "request_failed"})
            continue

        probe = {
            "url":            url,
            "final_url":      r.url,
            "status_code":    r.status_code,
            "server":         r.headers.get("Server", "—"),
            "content_type":   r.headers.get("Content-Type", "—"),
            "content_length": r.headers.get("Content-Length", "—"),
            "all_headers":    dict(r.headers),
            "anti_bot":       {},
            "rate_limit":     {},
            "redirect_chain": [resp.url for resp in r.history],
        }

        log.info(f"  Final URL (after redirects): {r.url}")
        if r.history:
            log.info(f"  Redirect chain: {' → '.join(str(h.url) for h in r.history)}")

        # Check for anti-bot headers
        log.info("\n  [Anti-Bot / CDN Fingerprint Headers]")
        found_any = False
        for hdr, service in CHALLENGE_HEADERS.items():
            val = r.headers.get(hdr)
            if val:
                probe["anti_bot"][hdr] = val
                log.warning(f"  ⚠️  {Fore.YELLOW}{service}{Style.RESET_ALL}"
                             f"  detected via header '{hdr}': {val[:80]}")
                found_any = True
        if not found_any:
            log.info(f"  {Fore.GREEN}No common anti-bot headers detected.{Style.RESET_ALL}")

        # Check for rate-limit headers
        log.info("\n  [Rate-Limit Headers]")
        for hdr in RATE_LIMIT_HEADERS:
            val = r.headers.get(hdr)
            if val:
                probe["rate_limit"][hdr] = val
                log.warning(f"  ⚠️  Rate-limit header '{hdr}': {val}")
        if not probe["rate_limit"]:
            log.info("  No rate-limit headers found.")

        # Cloudflare challenge page detection (JS challenge or IUAM)
        if r.status_code in (403, 429, 503):
            body_lower = r.text.lower()
            if "just a moment" in body_lower or "checking your browser" in body_lower:
                log.error(f"  🚨 {Fore.RED}CLOUDFLARE JS CHALLENGE detected — "
                          "Phase 2 will require Playwright.{Style.RESET_ALL}")
                probe["cloudflare_challenge"] = True
            elif "access denied" in body_lower or "forbidden" in body_lower:
                log.error(f"  🚨 {Fore.RED}Access Denied / WAF block on {url}{Style.RESET_ALL}")
                probe["access_denied"] = True

        results.append(probe)

    return results

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE 3 — RENDER MODE DETECTION (SSR vs CSR / XHR / JSON API)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Patterns that hint at SPA / CSR frameworks
CSR_SIGNALS = [
    ("React",     ["__REACT_QUERY", "reactDOM", "react.development", "__reactFiber",
                   "data-reactroot", "_next/static", "__NEXT_DATA__"]),
    ("Vue.js",    ["vue.min.js", "__vue__", "data-v-app", "createApp"]),
    ("Angular",   ["ng-version", "angular.min.js", "ng-app"]),
    ("Nuxt",      ["__NUXT__", "_nuxt/"]),
    ("Ember",     ["ember.min.js", "Ember.Application"]),
    ("Svelte",    ["__svelte", "svelte/internal"]),
    ("jQuery AJAX", ["$.ajax", "$.getJSON", "jquery.ajax", "XMLHttpRequest"]),
]

# Tags that indicate real server-rendered data
SSR_DATA_SELECTORS = [
    "table",           # result tables
    ".resultado",      # lottery result class
    "#resultado",
    "[class*='loto']",
    "[class*='loteria']",
    "[class*='result']",
    "[id*='result']",
    "dl", "dd", "dt",  # definition lists often used for draw numbers
]

# Potential XHR/Fetch endpoint patterns embedded in JS
XHR_PATTERNS = [
    "fetch(", "axios.", "XMLHttpRequest", "$.ajax",
    "$.get(", "$.post(", "/api/", "api/resultados",
    ".json", "wp-json", "rest/v", "/v1/", "/v2/",
]


def detect_render_mode(session: requests.Session) -> dict:
    section("MODULE 3 — Render Mode Detection (SSR vs CSR)")
    report = {}

    # Use the homepage and a likely results page
    pages = [BASE_URL + "/", BASE_URL + "/resultados"]

    for url in pages:
        log.info(f"\n  Analysing: {url}")
        time.sleep(random.uniform(*INTER_REQUEST_DELAY))

        r = safe_get(session, url)
        if r is None or r.status_code != 200:
            report[url] = {"error": f"HTTP {getattr(r,'status_code','—')}"}
            continue

        html  = r.text
        soup  = BeautifulSoup(html, "html.parser")
        body  = soup.get_text(separator=" ", strip=True)
        page_report = {}

        # ── CSR Framework Detection
        csr_found = []
        for framework, signals in CSR_SIGNALS:
            for sig in signals:
                if sig in html:
                    csr_found.append(framework)
                    log.warning(f"  ⚠️  {Fore.YELLOW}CSR signal detected:{Style.RESET_ALL} "
                                f"{framework}  (pattern: '{sig}')")
                    break
        page_report["csr_frameworks"] = list(set(csr_found))

        # ── SSR Data Detection
        ssr_hits = []
        log.info("\n  [SSR Data Selectors]")
        for sel in SSR_DATA_SELECTORS:
            nodes = soup.select(sel)
            if nodes:
                ssr_hits.append({"selector": sel, "count": len(nodes)})
                log.info(f"  ✅  '{sel}' → {len(nodes)} element(s) found")
        page_report["ssr_hits"] = ssr_hits

        # ── Inline <script> XHR / Fetch Pattern Scan
        log.info("\n  [Inline Script XHR/Fetch Endpoint Scan]")
        scripts   = soup.find_all("script")
        xhr_found = []
        for script in scripts:
            src = script.get("src", "")
            content = script.string or ""
            for pattern in XHR_PATTERNS:
                if pattern in content or pattern in src:
                    ctx = content[max(0, content.find(pattern)-30):
                                  content.find(pattern)+80].strip()
                    xhr_found.append({"pattern": pattern, "context": ctx[:120]})
                    log.info(f"  📡  XHR pattern '{pattern}' found in script: "
                             f"…{ctx[:80]}…")
        page_report["xhr_patterns"] = xhr_found

        # ── External script sources (API SDK / fetch libs)
        ext_scripts = [s["src"] for s in scripts if s.get("src")]
        log.info(f"\n  External scripts ({len(ext_scripts)}):")
        for s in ext_scripts:
            log.info(f"    {s}")
        page_report["external_scripts"] = ext_scripts

        # ── JSON-LD / Structured Data
        json_ld = soup.find_all("script", {"type": "application/ld+json"})
        if json_ld:
            log.info(f"\n  Found {len(json_ld)} JSON-LD block(s) — possible structured data:")
            for block in json_ld[:2]:
                try:
                    data = json.loads(block.string or "")
                    log.info(f"    @type: {data.get('@type','—')}")
                except Exception:
                    pass
        page_report["json_ld_blocks"] = len(json_ld)

        # ── Meta: Open Graph / Twitter cards (often reveal page structure)
        metas = {m.get("property", m.get("name", "")): m.get("content", "")
                 for m in soup.find_all("meta") if m.get("content")}
        page_report["og_title"]       = metas.get("og:title", "—")
        page_report["og_description"] = metas.get("og:description", "—")
        log.info(f"\n  OG Title: {page_report['og_title']}")
        log.info(f"  OG Desc : {page_report['og_description']}")

        # ── Verdict
        if ssr_hits and not csr_found:
            verdict = "LIKELY SSR — data is in static HTML"
            colour  = Fore.GREEN
        elif csr_found and not ssr_hits:
            verdict = "LIKELY CSR — need to intercept XHR/fetch calls"
            colour  = Fore.YELLOW
        elif csr_found and ssr_hits:
            verdict = "HYBRID — some SSR content + JS framework present"
            colour  = Fore.YELLOW
        else:
            verdict = "UNKNOWN — further manual inspection recommended"
            colour  = Fore.RED

        page_report["verdict"] = verdict
        log.info(f"\n  {colour}>>> VERDICT: {verdict}{Style.RESET_ALL}")
        report[url] = page_report

    return report

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODULE 4 — RESPONSE METRICS SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def measure_response_metrics(session: requests.Session) -> list[dict]:
    section("MODULE 4 — Response Time & Stability Metrics")
    metrics = []

    for url in PROBE_URLS:
        log.info(f"\n  Timing: {url}")
        times = []
        statuses = []

        for attempt in range(3):
            time.sleep(random.uniform(*INTER_REQUEST_DELAY))
            start = time.perf_counter()
            r = safe_get(session, url)
            elapsed = (time.perf_counter() - start) * 1000

            if r:
                times.append(elapsed)
                statuses.append(r.status_code)
                log.debug(f"    Attempt {attempt+1}: {r.status_code}  {elapsed:.0f}ms")
            else:
                statuses.append("ERROR")

        avg = sum(times) / len(times) if times else 0
        metrics.append({
            "url":          url,
            "statuses":     statuses,
            "avg_ms":       round(avg, 1),
            "min_ms":       round(min(times), 1) if times else None,
            "max_ms":       round(max(times), 1) if times else None,
        })
        log.info(f"  → Statuses: {statuses}  |  avg={avg:.0f}ms  "
                 f"min={min(times) if times else '—':.0f}ms  "
                 f"max={max(times) if times else '—':.0f}ms")

    return metrics

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN ORCHESTRATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    log.info(Fore.MAGENTA + Style.BRIGHT +
             "\n\n  ██████  RECON PHASE 1 — lotonacional.com.br  ██████\n")

    session = requests.Session()

    # Run all modules
    robots_data  = analyse_robots(session)
    header_data  = probe_headers(session)
    render_data  = detect_render_mode(session)
    metrics_data = measure_response_metrics(session)

    # ── Aggregate & dump full report to JSON
    full_report = {
        "target":          BASE_URL,
        "robots":          robots_data,
        "header_probes":   header_data,
        "render_analysis": render_data,
        "metrics":         metrics_data,
    }

    report_path = "recon_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False, default=str)

    section("FINAL SUMMARY")
    log.info(f"\n  Full machine-readable report → {report_path}")
    log.info(f"  Full human-readable log      → recon_report.log")
    log.info(
        "\n"
        "  ┌─────────────────────────────────────────────────────┐\n"
        "  │  WHAT TO SEND BACK FOR PHASE 2                      │\n"
        "  │  ─────────────────────────────────────────────────  │\n"
        "  │  1. The FULL terminal output (copy-paste)           │\n"
        "  │  2. The contents of recon_report.json               │\n"
        "  │  3. The contents of recon_report.log                │\n"
        "  │  (especially HTTP status codes, anti-bot headers,   │\n"
        "  │   render-mode verdict, and XHR patterns)            │\n"
        "  └─────────────────────────────────────────────────────┘\n"
    )


if __name__ == "__main__":
    main()
