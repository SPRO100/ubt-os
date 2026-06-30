# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

UBT OS is a multi-agent AI system that generates organic traffic to affiliate
offers via short-form video and prelanders. It runs **19 agents (A12–A30)**
across TikTok, Facebook, Instagram, Pinterest, and YouTube Shorts, orchestrated
by n8n, powered by Claude Sonnet 4.6 (orchestrator) and Haiku 4.5 (routine
tasks), and deployed on a single Linux server (FirstVDS Amsterdam).

**Language:** Russian is used throughout — code comments, log messages, the
Obsidian vault, and n8n workflows. Keep that convention.

---

## Common Commands

```bash
# Install dev dependencies
pip install -r deploy/requirements-dev.txt

# Run all tests
pytest tests/ -v --tb=short

# Run a single test file
pytest tests/test_compliance_regex.py -v

# Lint (config in pyproject.toml)
ruff check ubt_os/

# Type check (config in pyproject.toml)
mypy ubt_os/ --ignore-missing-imports

# Security scan (excludes obsidian_cron.py intentionally)
bandit -r ubt_os/ -ll -x ubt_os/utils/obsidian_cron.py

# Start the agent server
python -m ubt_os.main

# Dashboard (React 18 + Vite)
cd dashboard && npm install && npm run dev

# Full stack
docker compose up -d
```

CI (`.github/workflows/ci.yml`) runs on every push: **ruff → mypy → pytest →
bandit**. All must stay green.

---

## Architecture

### Request Flow

n8n cron triggers → POST webhook → `ubt_os/main.py` (ThreadingHTTPServer on
port 8080) → pipeline handlers → agents/pipelines → Supabase + Redis.

Every pipeline handler wraps its work in `pipeline_lock()` (Redis SET NX EX) to
prevent duplicate execution when n8n fires again before the previous run
finishes.

### Authentication (main.py `_authorized`)

Two paths — a request passes if **either** succeeds:

| Source | Mechanism | Header | Env key |
|--------|-----------|--------|---------|
| n8n / server-to-server | HMAC-SHA256 | `X-Webhook-Signature` | `WEBHOOK_SECRET` |
| Dashboard / browser | Bearer token | `Authorization: Bearer …` | `AGENTS_API_TOKEN` |

If neither key is set, the server runs in **dev mode** (no auth) and logs a
warning. CORS origin is configurable via `CORS_ALLOW_ORIGIN` (default `*`;
restrict to the dashboard domain in production).

### Python Package Structure (`ubt_os/`)

```
ubt_os/
├── main.py                  # HTTP webhook server — all n8n routes + auth land here
├── core/
│   ├── agent_api_layer.py   # Single Source of Truth: Reader/Writer classes per table
│   ├── circuit_breaker.py   # CircuitBreaker + call_agent_with_retry + BREAKERS dict
│   ├── pipeline_lock.py     # Redis distributed lock (async context manager)
│   ├── budget_guard.py      # BudgetGuard + @budget_guarded decorator
│   ├── knowledge_base.py    # Append-only knowledge entries
│   ├── risk_engine.py       # Risk scoring for active accounts
│   ├── creative_vault.py    # Creative scoring and storage
│   ├── vertical_loader.py   # Loads vertical YAML configs
│   └── logging_config.py    # Structured JSON logging + request_id context var
├── agents/                  # A12–A30 (19 agents) — see table below
├── pipelines/
│   ├── higgsfield_queue.py  # Redis priority queue for video generation jobs
│   ├── higgsfield_worker.py # Worker that dequeues and calls Higgsfield API
│   └── blotato_dlq.py       # Dead Letter Queue with retry
└── utils/
    ├── llm_utils.py          # extract_json() — robust JSON parsing of Claude responses
    ├── attribution.py        # Attribution windows
    ├── obsidian_git_sync.py  # Git sync of the Obsidian vault
    └── obsidian_cron.py      # Hourly cron entry point for sync
```

### Agents (A12–A30)

| ID | File | Role |
|----|------|------|
| A12 | `warming_state_machine.py` | Account warming FSM |
| A13 | `telegram_jitter.py` | Human-like posting delays |
| A14 | `account_checker.py` | Account health, ER, proxy, ban detection |
| A15 | `strategy_engine.py` | Weekly strategy brief |
| A16 | `revenue_analyst.py` | Attribution, funnel leak detection |
| A17 | `failure_recovery.py` | Health checks, DLQ, fallback |
| A18 | `knowledge_synthesizer.py` | Daily/weekly knowledge synthesis |
| A19 | `text_humanizer.py` | Stop-Slop: strips AI markers |
| A20 | `trend_scraper.py` | Trends & competitor hooks (Firecrawl) |
| A21 | `content_creator.py` | Before/After, hooks, UGC by Brand Voice |
| A22 | `ads_auditor.py` | TikTok/Meta audit, Health Score |
| A23 | `youtube_creator.py` | Shorts/Long-form scripts |
| A24 | `obsidian_brain.py` | Self-organizing AI wiki |
| A25 | `compliance_gate.py` | Content check: regex L1 → Haiku L2/L3 |
| A26 | `publer_publisher.py` | Publer API publishing + UTM |
| A27 | `spy_analyzer.py` | PiPiAds/AdHeart creative analysis |
| A28 | `warmup_manager.py` | 14-day warmup, activity limits, infra validation |
| A29 | `prelanding_generator.py` | HTML prelanders (quiz/story/article/vsl) |
| A30 | `higgsfield_agent.py` | UGC video / Shorts / carousels |
| A31 | `competitor_analyst.py` | Competitor hook analysis (complements A27) |
| — | `transcription_agent.py` | Video transcription (Deepgram → Whisper) + hook extraction |
| — | `pipelines/social_publisher.py` | Direct native-API publishing to 8 platforms |

### Key Architectural Patterns

**Single Source of Truth (`agent_api_layer.py`):** Agents never write directly
to a foreign table. Each table has a dedicated `*Reader` (any agent) and
`*Writer` (only its owning agent). Tables: `accounts` (AccountWriter),
`content_plans` (ContentPlanWriter), `videos` (VideoWriter), `publications`
(PublicationWriter).

**Circuit Breaker (`circuit_breaker.py`):** `BREAKERS` dict holds named
`CircuitBreaker` instances. After 5 consecutive failures → OPEN (blocks calls
for 120s) → Telegram alert. Wrap Anthropic calls with `call_agent_with_retry()`:
30s timeout, 3 retries with exponential backoff, rate-limit aware.

**Pipeline Lock (`pipeline_lock.py`):** Use
`async with pipeline_lock("name", ttl) as acquired:` and `if not acquired: return`
immediately. Lock key: `pipeline_lock:{name}`. Atomic token-checked release via
Lua script.

**Budget Guard (`budget_guard.py`):** `@budget_guarded("AGENT_NAME")` checks
LiteLLM spend before each call. Global daily cap via `LITELLM_DAILY_BUDGET`
(default $20). Alert at 80%. Max chain depth = 10 iterations.

### Webhook Routes (main.py)

| Method | Path | Handler |
|--------|------|---------|
| POST | `/run/nutra`, `/run/ubt` | Video pipelines |
| POST | `/run/account-check` | Account checker |
| POST | `/run/obsidian-sync` | Obsidian vault git sync |
| POST | `/run/daily-report` | DLQ daily summary |
| POST | `/strategy/collect` | A15: collect data + write vault |
| POST | `/risk/run` | Risk scoring for active accounts |
| POST | `/knowledge/synthesize` | A18: daily or weekly (`mode` param) |
| POST | `/obsidian/write`, `/obsidian/append` | Write/append vault file |
| POST | `/orchestrator/chat` | Chat with orchestrator (vertical context) |
| POST | `/agents/run` | Run any A19–A30 agent directly (dashboard) |
| POST | `/competitor/analyze`, `/hooks/top` | A31 competitor hook analysis |
| POST | `/transcribe` | Video transcription + hook extraction |
| POST | `/publish/direct`, `/publish/bulk` | Direct native-API publishing |
| GET | `/health/check-all` | Supabase + Redis connectivity |
| GET | `/metrics` | Prometheus-format counters |

`_safe_vault_path()` protects against path traversal on the Obsidian routes.

### LLM Response Parsing

Use `extract_json()` from `ubt_os/utils/llm_utils.py`. It strips ` ```json `
fences, parses the whole string, and falls back to extracting the first
balanced `{…}` / `[…]` if the model wrapped the JSON in prose.

When reading Claude responses, prefer `getattr(resp.content[0], "text", "")` —
`content[0]` may be a `ToolUseBlock` without `.text`.

---

## Environment Variables

See `.env.template` for the full list. Required for all services:
`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL`.

Security: `WEBHOOK_SECRET`, `AGENTS_API_TOKEN`, `CORS_ALLOW_ORIGIN`,
`AGENTS_HOST` (default `0.0.0.0`).

Functionality: `HIGGSFIELD_API_KEY` (A30), `PUBLER_API_KEY` + profile IDs (A26),
`FIRECRAWL_API_KEY` (A20), `KEITARO_*`, `TELEGRAM_ALERT_*`, `OBSIDIAN_*`,
`LITELLM_*`.

---

## Database

Supabase (PostgreSQL). SQL schema files live in `deploy/` (`01_schema_sot.sql`
plus `strategy_`, `revenue_`, `risk_`, `vertical_`, `creative_vault_`,
`recovery_` schemas and incremental patches). Each owned table has an
`owned_by_agent` column; writers check ownership before mutating rows.

---

## Testing

Tests live in `tests/`. `pytest.ini` sets `asyncio_mode = auto`, so
`async def test_*` works without explicit decorators.

```bash
pytest tests/test_compliance_regex.py -v   # A25 L1 regex (nutra/betting/trademark)
pytest tests/test_extract_json.py -v       # LLM JSON parsing robustness
pytest tests/test_webhook_auth.py -v       # dual auth (HMAC + Bearer)
pytest tests/test_circuit_breaker.py -v    # circuit breaker state transitions
pytest tests/test_vault_path.py -v         # path traversal protection
```

Use `monkeypatch.setenv(...)` for env-dependent tests; don't hit real services
in unit tests.

---

## Deployment

Production: FirstVDS Amsterdam, Ubuntu 22.04, `docker compose up -d`.
`deploy/nginx.conf` is the reverse proxy (TLS via certbot once a domain is set).
The dashboard is a React 18 + Vite SPA in `dashboard/`. n8n workflows are JSON
files in `n8n/workflows/`, imported via the n8n UI.
