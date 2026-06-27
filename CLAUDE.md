# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

UBT OS v2 is a multi-agent AI system that generates organic traffic to affiliate offers via short-form video. It runs 19 agents across 4 platforms (TikTok, YouTube Shorts, Instagram Reels, Telegram), orchestrated by n8n, powered by Claude Sonnet 4.6 / Haiku 4.5, and deployed on a single Linux server (FirstVDS Amsterdam).

Language: Russian is used throughout — in code comments, log messages, Obsidian vault, and n8n workflows. Keep that convention.

---

## Common Commands

```bash
# Install dev dependencies
pip install -r deploy/requirements-dev.txt

# Run all tests
pytest tests/ -v --tb=short

# Run a single test file
pytest tests/test_circuit_breaker.py -v

# Lint
ruff check ubt_os/

# Type check
mypy ubt_os/ --ignore-missing-imports

# Security scan (excludes obsidian_cron.py intentionally)
bandit -r ubt_os/ -ll -x ubt_os/utils/obsidian_cron.py

# Start full stack
make up

# View agent logs
make logs-agents

# Apply all DB schemas (run once against Supabase)
make db-init

# Test Redis lock (requires .env with REDIS_URL)
make test-lock

# Check LiteLLM budget usage (requires running LiteLLM)
make test-budget
```

CI runs on every push: lint (ruff) → type check (mypy) → pytest → bandit. All must pass.

---

## Architecture

### Request Flow

n8n cron triggers → POST webhook → `ubt_os/main.py` (ThreadingHTTPServer on port 8080) → pipeline handlers → agents/pipelines → Supabase + Redis

Every pipeline handler wraps its work in `pipeline_lock()` (Redis SET NX EX) to prevent duplicate execution when n8n fires again before the previous run finishes.

### Service Map (docker-compose.yml)

| Service | Image / Entry | Purpose |
|---------|--------------|---------|
| `postgres` | postgres:16-alpine | LiteLLM audit log and n8n storage |
| `redis` | redis:7-alpine | Distributed locks + Higgsfield priority queue |
| `litellm` | ghcr.io/berriai/litellm | LLM router with budget caps ($20/day global, per-team limits) |
| `n8n` | n8nio/n8n | Cron orchestration, 6 published workflows |
| `agents` | deploy/Dockerfile | Main HTTP server (`ubt_os.main`) |
| `higgsfield_worker` | deploy/Dockerfile | Separate worker consuming the video generation queue |
| `obsidian_sync` | deploy/Dockerfile | Hourly git sync of the Obsidian vault |

### Python Package Structure (`ubt_os/`)

```
ubt_os/
├── main.py                  # HTTP webhook server — all n8n routes land here
├── core/
│   ├── agent_api_layer.py   # Single Source of Truth: Reader/Writer classes per table
│   ├── circuit_breaker.py   # CircuitBreaker + call_agent_with_retry + BREAKERS dict
│   ├── pipeline_lock.py     # Redis distributed lock (async context manager)
│   ├── budget_guard.py      # BudgetGuard + @budget_guarded decorator
│   ├── knowledge_base.py    # Immutable append-only knowledge entries (versioned)
│   ├── risk_engine.py       # Risk scoring for active accounts
│   ├── creative_vault.py    # Creative scoring and storage
│   ├── vertical_loader.py   # Loads vertical YAML configs from Supabase
│   └── logging_config.py    # Structured JSON logging + request_id context var
├── agents/
│   ├── strategy_engine.py   # A15: weekly strategy brief
│   ├── revenue_analyst.py   # A16: attribution and funnel leak detection
│   ├── failure_recovery.py  # A17: health checks, fallback
│   ├── knowledge_synthesizer.py  # A18: daily/weekly knowledge synthesis
│   ├── warming_state_machine.py  # Account warming FSM (8-day schedule)
│   ├── account_checker.py   # Phase-aware account health checker
│   └── telegram_jitter.py   # Human-like posting delay (FIX #8)
├── pipelines/
│   ├── higgsfield_queue.py  # Redis priority queue for video generation jobs
│   ├── higgsfield_worker.py # Worker that dequeues and calls Higgsfield API
│   └── blotato_dlq.py       # Dead Letter Queue with retry for Blotato uploads
└── utils/
    ├── llm_utils.py          # extract_json() — strips ```json fences from Claude responses
    ├── attribution.py        # Attribution windows (FIX #12)
    ├── obsidian_git_sync.py  # Bidirectional git sync of Obsidian vault
    ├── obsidian_cron.py      # Hourly cron entry point for sync
    └── account_compat.py     # Account model compatibility shims
```

### Key Architectural Patterns

**Single Source of Truth (agent_api_layer.py):** Agents never write directly to a foreign table. Each table has a dedicated `*Reader` (any agent can use) and `*Writer` (only its owning agent). Tables: `accounts` (AccountWriter), `content_plans` (ContentPlanWriter), `videos` (VideoWriter), `publications` (PublicationWriter).

**Circuit Breaker (circuit_breaker.py):** `BREAKERS` dict holds named `CircuitBreaker` instances. After 5 consecutive failures → OPEN state (blocks calls for 120s) → sends Telegram alert. Use `call_agent_with_retry()` to wrap any Anthropic API call: 30s timeout, 3 retries with exponential backoff, rate-limit aware.

**Pipeline Lock (pipeline_lock.py):** Use `async with pipeline_lock("name", ttl_seconds) as acquired:` and check `if not acquired: return` immediately. Lock key format: `pipeline_lock:{name}`. Lua script for atomic release (token-checked). Named locks and TTLs are defined in `PIPELINE_LOCKS` dict.

**Budget Guard (budget_guard.py):** `@budget_guarded("AGENT_NAME")` decorator checks LiteLLM spend before each call. Global $20/day cap configured in `deploy/litellm_config.yaml`. Per-team budgets: ORCHESTRATOR $5, CONTENT_CREATOR $4, RESEARCH $3, others $2 each. Alert at 80% usage. Max chain depth = 10 iterations.

**Account Warming FSM (warming_state_machine.py):** 8-day warming schedule: days 1-3 `views_only` → days 4-5 `neutral_content` → days 6-7 `niche_content` → day 8+ `monetization`. State transitions are validated against `VALID_TRANSITIONS` dict. Persisted in Supabase `accounts` table columns `warming_day` + `warming_phase`.

### Webhook Routes (main.py)

| Method | Path | Handler |
|--------|------|---------|
| POST | `/run/nutra` | Video pipeline for nutra vertical |
| POST | `/run/ubt` | Video pipeline for UBT vertical |
| POST | `/run/account-check` | Phase-aware account checker |
| POST | `/run/obsidian-sync` | Obsidian vault git sync |
| POST | `/run/daily-report` | DLQ daily summary |
| POST | `/strategy/collect` | A15: collect data + write vault |
| POST | `/risk/run` | Risk scoring for all active accounts |
| POST | `/knowledge/synthesize` | A18: daily or weekly (`mode` param) |
| POST | `/obsidian/write` | Write/append file in vault (path + content in body) |
| POST | `/obsidian/append` | Alias for write with `append=true` |
| POST | `/orchestrator/chat` | Chat with orchestrator (vertical context) |
| GET | `/health/check-all` | Check Supabase + Redis connectivity |
| GET | `/metrics` | Prometheus-format counters |

Webhook HMAC-SHA256 authentication via `X-Webhook-Signature` header (skipped if `WEBHOOK_SECRET` env var not set). Correlation IDs via `X-Request-Id` header.

### LLM Routing

All agent LLM calls go through LiteLLM at `LITELLM_BASE_URL` (port 4000). Two model aliases:
- `sonnet-heavy` → `claude-sonnet-4-6` (4096 tokens, 30s timeout)
- `haiku-light` → `claude-haiku-4-5-20251001` (2048 tokens, 15s timeout)

The `/orchestrator/chat` route calls `AsyncAnthropic()` directly (not through LiteLLM) and uses `claude-sonnet-4-6`.

### LLM Response Parsing

Use `extract_json()` from `ubt_os/utils/llm_utils.py` to parse JSON from Claude responses — it strips ` ```json ``` ` fences automatically.

### Obsidian Vault

The vault at `OBSIDIAN_VAULT_PATH` (default `/app/obsidian-vault`) is a git repo synced hourly to `OBSIDIAN_REMOTE_URL`. Agents write daily synthesis and strategy briefs here. Vault path traversal is protected in `_safe_vault_path()` in `main.py`.

### Verticals

Four supported verticals defined in `vertical_configs/sample_configs.yaml` and stored in Supabase `vertical_configs` table: `cars`, `info`, `realestate`, `crypto`. Each has its own funnel, monetization model, and platform sensitivity configuration.

---

## Environment Variables

Required for all services: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL` (or `REDIS_PASSWORD` for compose), `LITELLM_MASTER_KEY`.

Required for full functionality: `HIGGSFIELD_API_KEY`, `ELEVENLABS_API_KEY`, `BLOTATO_API_KEY`, `KEITARO_DOMAIN`, `KEITARO_API_KEY`, `TELEGRAM_ALERT_BOT_TOKEN`, `TELEGRAM_ALERT_CHAT_ID`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `OBSIDIAN_REMOTE_URL`, `N8N_WEBHOOK_URL`, `N8N_ENCRYPTION_KEY`.

Optional: `LITELLM_DAILY_BUDGET` (default `20.0`), `WEBHOOK_SECRET`, `OBSIDIAN_BRANCH` (default `main`), `AGENTS_PORT` (default `8080`).

---

## Database

Supabase (PostgreSQL). Seven SQL schema files in `deploy/` applied via `make db-init`:

1. `01_schema_sot.sql` — core tables: `accounts`, `content_plans`, `videos`, `publications`
2. `strategy_schema.sql` — strategy briefs
3. `revenue_schema.sql` — revenue attribution
4. `risk_schema.sql` — risk scores
5. `vertical_schema.sql` — vertical configs
6. `creative_vault_schema.sql` — creative scoring
7. `recovery_schema.sql` — health check history + DLQ

Each table has an `owned_by_agent` column; writers check ownership before mutating rows.

---

## Testing

Tests live in `tests/`. `pytest.ini` sets `asyncio_mode = auto` so `async def test_*` functions work without explicit decorators.

```bash
pytest tests/test_circuit_breaker.py -v    # circuit breaker state transitions
pytest tests/test_webhook_auth.py -v       # HMAC signature verification
pytest tests/test_llm_utils.py -v          # JSON extraction from LLM responses
pytest tests/test_vault_path.py -v         # path traversal protection
pytest tests/test_logging_config.py -v     # structured logging
```

Mock `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL` env vars in tests that touch infrastructure — don't hit real services in unit tests.

---

## Deployment

Production: FirstVDS Amsterdam, Ubuntu 22.04. `make up` starts all 7 Docker services. `make deploy-railway` deploys via Railway CLI.

The `higgsfield_worker` service runs as a separate Docker container consuming `python -m ubt_os.pipelines.higgsfield_worker`. The `obsidian_sync` service runs `python -m ubt_os.utils.obsidian_cron` on an hourly schedule.

n8n workflows are JSON files in `n8n/workflows/`. Import them via n8n UI; they are read-only bind-mounted in the container.
