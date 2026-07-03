# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

UBT OS is a multi-agent AI system that generates organic traffic to affiliate
offers via short-form video and prelanders. It runs **27 agents (A12–A36)**
across TikTok, Facebook, Instagram, Pinterest, and YouTube Shorts, orchestrated
by n8n, powered by Claude Sonnet 5 (orchestrator) and Haiku 4.5 (routine
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

**Public routes (`_PUBLIC_PATHS` in `do_POST`):** `/orchestrator/chat`,
`/health/check-all`, `/metrics` bypass auth entirely — the dashboard chat must
work without a token (the server is firewalled, only nginx :80 is exposed). The
path is normalized (`split("?")[0].rstrip("/")`) before the check. Do not add
write/side-effecting routes to this set.

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
├── agents/                  # A12–A36 (27 agents) — see table below
├── pipelines/
│   ├── higgsfield_queue.py  # Redis priority queue for video generation jobs
│   ├── higgsfield_worker.py # Worker that dequeues and calls Higgsfield API
│   └── blotato_dlq.py       # Dead Letter Queue with retry
└── utils/
    ├── llm_utils.py          # extract_json() — robust JSON parsing of Claude responses
    ├── supabase_utils.py     # rows()/first_row()/one_row() — typed resp.data extraction
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
| A32 | `trend_radar.py` | Ranks trending sounds/hashtags per vertical/GEO → `trend_signals` |
| A33 | `competitor_scraper.py` | Scrapes crips into `competitor_signals` (feeds A31) |
| A34 | `caption_agent.py` | Styled subtitles (ASS/SRT) from word timings + ffmpeg burn |
| A35 | `tts_agent.py` | Voiceover: self-hosted TTS → ElevenLabs → Supabase Storage |
| — | `transcription_agent.py` | Video transcription (Deepgram → Whisper) + hook extraction |
| — | `pipelines/social_publisher.py` | Direct native-API publishing to 8 platforms |
| A36 | `post_analytics_agent.py` | Native per-post metrics (impressions/reach/likes/comments/shares) → `post_metrics` |

### Competitor analysis: A27 vs A31 (NOT duplicates)

Two competitor agents exist on purpose — they are **complementary**, не merge them:

- **A27 `spy_analyzer`** — *reactive, on-demand.* You feed it crips manually
  (PiPiAds/AdHeart text or URLs); it returns a creative brief +
  `a21_prompt_extension` that drives A21 `content_creator`.
- **A31 `competitor_analyst`** — *proactive, scheduled.* Pulls scraped videos
  from the `competitor_signals` table, classifies hooks (Claude Vision when a
  thumbnail is present), writes to `competitor_patterns` / `hook_templates`, and
  builds weekly aggregate hook-trend reports.

A27 = "analyse these specific crips now", A31 = "monitor the competitive field
over time". Keep both.

### Direct publishing credentials (`social_publisher.py`)

Per-account platform tokens (`access_token`, `page_id`, `ig_user_id`,
`board_id`, `threads_user_id`) live in the **`direct_publish_accounts`** table —
not in env vars (multi-account by design). `create_and_publish(platform,
account_id, …)` looks them up by `account_id`. To onboard an account, insert its
row into `direct_publish_accounts`. Only `MEDIA_BUCKET` (Supabase Storage) is
env-configured. All DB tables are created by `make db-init`
(`deploy/dohoo_features_schema.sql`).

### Post analytics (`post_analytics_agent.py`, `deploy/06_patch_post_metrics.sql`)

A36 pulls native per-post engagement (impressions/reach/views/likes/comments/
shares/saves) directly from each platform's API for every `direct_publish_jobs`
row with `status = 'published'`, using the same `direct_publish_accounts`
credentials as the publisher. Writes time-series snapshots to `post_metrics`
(one row per sync — lets you track growth over time, not just a point-in-time
count). `v_post_metrics_latest` and `v_platform_engagement` views give the
dashboard the latest snapshot and per-platform aggregates without re-deriving
DISTINCT ON logic client-side.

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
| POST | `/trends/radar` | A32 trend radar (ranks sounds/hashtags) |
| POST | `/competitor/scrape` | A33 scrape crips into `competitor_signals` |
| POST | `/caption` | A34 styled subtitles (ASS/SRT) + ffmpeg burn |
| POST | `/tts` | A35 voiceover (self-hosted TTS → ElevenLabs) |
| POST | `/transcribe` | Video transcription + hook extraction |
| POST | `/publish/direct`, `/publish/bulk` | Direct native-API publishing |
| POST | `/analytics/sync` | A36 sync native post metrics (impressions/reach/likes/comments/shares) |
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

**`accounts.id` is TEXT** (human-readable, e.g. `tiktok_us_001`), used as the
`account_id` string across warmup_manager / social_publisher /
`direct_publish_accounts`. `platform` allows tiktok/youtube/instagram/telegram/
**facebook/pinterest**. The dashboard also writes `proxy`, `publer_profile_id`,
`account_type`. Existing DBs are migrated by `06_patch_accounts_align.sql`
(part of `make db-init`) — it changes `id` UUID→TEXT (dropping/re-adding the
account_id FKs), expands the platform CHECK, and adds the missing columns.

### Knowledge base — `kb_entries` (versioned, `08_patch_kb_entries.sql`)

The professional knowledge library the orchestrator and agents draw on lives in
**`kb_entries`** — a versioned, append-only table. Columns: `entry_key,
category, vertical, title, content, tags, version, is_current, changed_by`.
There is **no `platform`/`scheme` column** — those are encoded in `entry_key`
and mirrored into `tags`.

- `entry_key` format: **`<process>.<platform>.<vertical>.<scheme>`**
  (e.g. `content.tiktok.betting.grey`, `white_funnel.telegram.auto.white`).
  Missing segments default to `any`.
- Partial unique index `WHERE is_current = TRUE` — you **cannot** use
  `upsert on_conflict`; seed scripts do `delete().eq("entry_key", key)` then
  `insert()`.
- This is a **different table** from the legacy `knowledge_entries` — the
  dashboard "Записи знаний" tile and Knowledge section read `kb_entries`
  (`is_current = true`).

**Seed scripts (`deploy/seed_kb*.py`)** — additive, each writes via
delete+insert, run with `docker compose exec agents python /tmp/<script>.py`:
- `seed_kb.py` — 40 base entries (process × platform × vertical × scheme).
- `seed_kb_affiliate.py` — 30, Block A: CPA-network maps, per-vertical guides,
  compliance matrix, funnels, benchmarks.
- `seed_kb_white.py` — 16, Block B: white-niche funnels, Telegram organic
  growth + monetization, YouTube/Shorts.
- `seed_kb_content.py` — 13: hooks, formats, copywriting, stop-slop, trends,
  neural production.

Total ≈ **99 entries**. To extend, add a new `seed_kb_*.py` following the same
`_e(key, title, content, tags)` shape and category taxonomy; add new category
labels to `dashboard/src/components/sections/Knowledge.jsx` (`CATEGORY_LABELS`).

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

---

## Dashboard UI Conventions

**RULE — collapsible lists everywhere.** Any card whose body is a list or
table (reference data, agent/skill listings, knowledge entries, service
tables, partner conditions, etc.) MUST be collapsible. Use the shared
`dashboard/src/components/CollapsibleCard.jsx` component — never hand-roll a
plain `<div className="card">` around a long list. This applies to every new
section and every existing one going forward.

Guidelines:
- Reference / static lists → `defaultOpen` **omitted** (collapsed by default).
- Primary live/interactive tables (accounts, post analytics, server status,
  n8n workflows) → `defaultOpen` (open, but still collapsible).
- Always pass `count={rows.length}` so the header shows how many items are
  hidden inside.
- Interactive controls in the header (sync buttons, links) go in the
  `headerRight` prop — clicks there don't toggle the card.
- For grouped lists inside a single card (e.g. Knowledge grouped by category),
  make each group header individually collapsible (see `Knowledge.jsx`).

**Dashboard deploy:** the built SPA is committed to `dashboard-static/` (tracked
in git, served by nginx). After any dashboard change: `cd dashboard && npm run
build && cp -r dist/* ../dashboard-static/`, then commit both `dashboard/src`
and `dashboard-static/`. On the server a plain `git pull` updates the live UI —
no rebuild needed. All dashboard API calls go through nginx on port 80
(`AGENTS_SERVER` has no `:8080`).

**Knowledge base:** the dashboard "Записи знаний" tile and the Knowledge section
read `kb_entries` (versioned, `is_current = true`), NOT the legacy
`knowledge_entries` table. Research is loaded via `deploy/seed_kb*.py` scripts
(`entry_key` = `process.platform.vertical.scheme`).
