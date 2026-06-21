# UBT OS v2 — Multi-Agent AI System for Organic Traffic

> Мульти-агентная AI-система для генерации органического трафика на партнёрские офферы.
> 19 агентов · 2 вертикали · 4 платформы · самовосстанавливающаяся архитектура

---

## Структура репозитория

```
ubt-os/
├── ubt_os/                    # Python пакет
│   ├── core/                  # Ядро системы
│   │   ├── pipeline_lock.py   # FIX #3 — Redis distributed lock
│   │   ├── circuit_breaker.py # FIX #2 — Circuit breaker
│   │   ├── budget_guard.py    # FIX #6 — LiteLLM cost cap
│   │   ├── agent_api_layer.py # FIX #1 — Single source of truth
│   │   ├── knowledge_base.py  # FIX #9 — Immutable versioning
│   │   ├── creative_vault.py  # Блок 2 — Creative scoring
│   │   ├── risk_engine.py     # Блок 4 — Risk scoring
│   │   └── vertical_loader.py # Универсальность — Vertical configs
│   ├── agents/                # Агенты системы
│   │   ├── strategy_engine.py     # A15 — недельный бриф
│   │   ├── revenue_analyst.py     # A16 — attribution и доход
│   │   ├── failure_recovery.py    # A17 — health checks
│   │   ├── knowledge_synthesizer.py # A18 — синтез знаний
│   │   ├── warming_state_machine.py # FIX #4 — прогрев FSM
│   │   ├── account_checker.py     # FIX #5 — чекер по фазам
│   │   └── telegram_jitter.py     # FIX #8 — human delay
│   ├── pipelines/             # Пайплайны
│   │   ├── higgsfield_queue.py    # FIX #7 — priority queue
│   │   ├── blotato_dlq.py         # FIX #11 — DLQ retry
│   │   └── higgsfield_worker.py   # Worker сервис
│   ├── utils/                 # Утилиты
│   │   ├── obsidian_git_sync.py   # FIX #10 — git sync
│   │   ├── attribution.py         # FIX #12 — attribution windows
│   │   └── obsidian_cron.py       # Hourly cron
│   └── main.py                # HTTP сервер (webhook от n8n)
│
├── deploy/                    # Деплой
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── litellm_config.yaml        # FIX #6 — LiteLLM config
│   ├── 01_schema_sot.sql          # FIX #1 — базовая схема
│   ├── strategy_schema.sql        # Блок 1 — STRATEGY_ENGINE
│   ├── creative_vault_schema.sql  # Блок 2 — CREATIVE VAULT
│   ├── revenue_schema.sql         # Блок 3 — REVENUE_ANALYST
│   ├── risk_schema.sql            # Блок 4 — RISK ENGINE
│   ├── recovery_schema.sql        # Блок 5 — FAILURE_RECOVERY
│   ├── vertical_schema.sql        # Вертикали — конфиги
│   └── docker-compose-v2-additions.yml
│
├── n8n/workflows/             # n8n воркфлоу
│   ├── video-pipeline-nutra.json  # FIX #3
│   ├── account-checker.json       # FIX #3 + #5
│   ├── strategy-engine-weekly.json # Блок 1
│   ├── risk-engine-monitor.json   # Блок 4
│   ├── health-monitor.json        # Блок 5
│   └── knowledge-synthesizer.json # Блок 6
│
├── vertical_configs/          # Конфиги вертикалей
│   └── sample_configs.yaml    # Авто, инфо, недвига, крипто
│
├── obsidian-vault/            # База знаний (Obsidian)
│   ├── 50 Resources/          # SOPs, архитектура, стратегия
│   │   ├── MOC — Мастер Проект.md
│   │   ├── Архитектура Агентов.md
│   │   ├── SOPs/              # Документация агентов + код фиксов
│   │   └── ...
│   └── 60 Daily/              # Ежедневные отчёты (авто)
│
├── docker-compose.yml         # Полный стек
├── Makefile                   # make setup / make up / make deploy-railway
└── .env.template              # Все переменные окружения
```

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/YOUR_USERNAME/ubt-os.git
cd ubt-os

# 2. Настроить окружение
cp .env.template .env
# Заполни .env своими API ключами

# 3. Применить схему БД
make db-init

# 4. Запустить систему
make up

# 5. Проверить
make test-lock
make test-budget
```

---

## Стек

| Слой | Технология |
|------|-----------|
| AI Brain | Claude Sonnet 4.6 + Haiku 4.5 → LiteLLM Router |
| Video | Higgsfield.ai MCP + short-video-maker + ElevenLabs |
| Publishing | Blotato API + TikTokAutoUploader + YT Imperial |
| Automation | n8n self-hosted (Railway) |
| Database | Supabase + PostgreSQL + Redis |
| Tracking | Keitaro UTM + Postback |
| Anti-detect | GoLogin + Residential Proxies |
| Memory | Obsidian Vault + GitHub sync |
| Dashboard | Next.js 14 + Vercel |

---

## Агенты (A0–A18)

| ID | Агент | Модель | Роль |
|----|-------|--------|------|
| A0 | ORCHESTRATOR | Sonnet | CEO, протокол одобрений |
| A1–A13 | Core Agents | Sonnet/Haiku | Контент, публикация, аналитика |
| A14 | COMPETITOR_ANALYST | Sonnet | Мониторинг конкурентов |
| A15 | STRATEGY_ENGINE | Sonnet | Недельный стратегический бриф |
| A16 | REVENUE_ANALYST | Sonnet | Attribution, утечки воронки |
| A17 | FAILURE_RECOVERY | Service | Health checks 60s, fallback |
| A18 | KNOWLEDGE_SYNTHESIZER | Sonnet | Ежедневный синтез знаний |

---

## Переменные окружения

Все необходимые переменные в `.env.template`.
Обязательные для старта: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `REDIS_URL`.

---

## Статус: ~20% готовности

✅ Документация (40 файлов Obsidian)
✅ Архитектура (19 агентов)
✅ 12 архитектурных фиксов (код)
✅ Docker Compose + Python пакет
✅ n8n воркфлоу (6 файлов)
✅ Vertical Config система

❌ API ключи не зарегистрированы
❌ Инфраструктура не задеплоена
❌ Аккаунты не созданы

---

*User is always the final decision-maker. Nothing executes without explicit approval.*
