<div align="center">

# 🧠 UBT OS

### Мульти-агентная AI-система для генерации органического трафика на партнёрские офферы

**19 агентов (A12–A30)** · TikTok · Facebook · Instagram · Pinterest · YouTube Shorts · UGC-карусели

[![CI](https://github.com/spro100/ubt-os/actions/workflows/ci.yml/badge.svg)](https://github.com/spro100/ubt-os/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet%204.6%20%2B%20Haiku%204.5-8A2BE2.svg)](https://www.anthropic.com/)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

</div>

---

## 📋 Содержание

- [Что это](#-что-это)
- [Архитектура](#-архитектура)
- [Полный пайплайн](#-полный-пайплайн)
- [Состояние проекта](#-состояние-на-30-июня-2026)
- [Быстрый старт](#-быстрый-старт)
- [Конфигурация](#-конфигурация-окружения)
- [Безопасность](#-безопасность)
- [Dashboard](#-dashboard)
- [Стек](#-стек)
- [Разработка и качество](#-разработка-и-качество)
- [GEO и вертикали](#-geo-и-вертикали)
- [Структура репозитория](#-структура-репозитория)

---

## 🎯 Что это

UBT OS — это оркестрированная система из 19 AI-агентов, которая закрывает весь
цикл партнёрского маркетинга на органике: от анализа крипов конкурентов и
генерации контента до прогрева аккаунтов, проверки на compliance и публикации с
UTM-трекингом.

Ядро — **Claude Sonnet 4.6** (оркестратор) и **Claude Haiku 4.5** (рутинные
задачи). Агенты соединяются через n8n-воркфлоу и общий HTTP-слой, состояние
живёт в Supabase + Redis, база знаний — в Obsidian Vault с git-синхронизацией.

> **Принцип:** пользователь — всегда финальный принимающий решение. Ничего не
> публикуется без явного подтверждения.

---

## 🏗 Архитектура

```
                         ┌──────────────────────────┐
                         │   ORCHESTRATOR (Sonnet)  │
                         │  чат в контексте проекта │
                         └────────────┬─────────────┘
                                      │
        ┌─────────────────┬──────────┼───────────┬──────────────────┐
        ▼                 ▼          ▼           ▼                  ▼
   ┌─────────┐      ┌──────────┐ ┌────────┐ ┌──────────┐    ┌──────────────┐
   │  Ядро   │      │ Контент  │ │Аналитика│ │Публикация│    │ Медиа + Affil│
   │ A12–A18 │      │ A19–A21  │ │ A22–A24 │ │ A25–A26  │    │   A27–A30    │
   └─────────┘      └──────────┘ └────────┘ └──────────┘    └──────────────┘
        │                                                          │
        └──── Circuit Breaker · Budget Guard · Pipeline Lock · DLQ ┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                ▼                     ▼                     ▼
           ┌─────────┐          ┌──────────┐          ┌──────────┐
           │ Supabase│          │  Redis   │          │ Obsidian │
           │ 25+ табл│          │ (Upstash)│          │  Vault   │
           └─────────┘          └──────────┘          └──────────┘
```

### Ядро (A12–A18)

| ID | Файл | Роль |
|----|------|------|
| A12 | `warming_state_machine.py` | FSM прогрева аккаунтов, фазы активности |
| A13 | `telegram_jitter.py` | Случайные задержки, human-behavior |
| A14 | `account_checker.py` | Здоровье аккаунта, ER, прокси, бан |
| A15 | `strategy_engine.py` | Недельный стратегический бриф (воскр. 20:00) |
| A16 | `revenue_analyst.py` | Attribution, утечки воронки |
| A17 | `failure_recovery.py` | DLQ, health-check 60s, fallback |
| A18 | `knowledge_synthesizer.py` | Синтез знаний (ежедн. 23:45) |

### Контент-пайплайн (A19–A21)

| ID | Файл | Роль |
|----|------|------|
| A19 | `text_humanizer.py` | Stop-Slop: очистка AI-маркеров, оценка 0–50 |
| A20 | `trend_scraper.py` | Тренды и хуки конкурентов через Firecrawl |
| A21 | `content_creator.py` | Before/After, хуки, UGC по Brand Voice (5 GEO) |

### Аналитика и база знаний (A22–A24)

| ID | Файл | Роль |
|----|------|------|
| A22 | `ads_auditor.py` | Аудит TikTok/Meta, Health Score 0–100 |
| A23 | `youtube_creator.py` | Shorts/Long-form, retention-инжиниринг |
| A24 | `obsidian_brain.py` | Self-organizing AI wiki (Obsidian Vault) |

### Публикация (A25–A26)

| ID | Файл | Роль |
|----|------|------|
| A25 | `compliance_gate.py` | Проверка контента: Regex L1 → Claude Haiku L2/L3 |
| A26 | `publer_publisher.py` | Publer API — TikTok / Facebook / Instagram / Pinterest + UTM |

### Affiliate Intelligence + Медиа (A27–A30)

| ID | Файл | Роль |
|----|------|------|
| A27 | `spy_analyzer.py` | Анализ крипов PiPiAds/AdHeart → creative brief для A21 |
| A28 | `warmup_manager.py` | 14-дневный прогрев, лимиты активности, инфра-валидация |
| A29 | `prelanding_generator.py` | HTML прелендинги (quiz/story/article/vsl), мультиязычный |
| A30 | `higgsfield_agent.py` | UGC 9:16/16:9 · Shorts · Карусели через Higgsfield AI |

---

## 🔄 Полный пайплайн

```
A27 spy_analyzer (PiPiAds/AdHeart крипы)
    ↓
A21 content_creator (хуки, before/after, UGC)
    ↓
A19 text_humanizer (Stop-Slop очистка)
    ↓
A25 compliance_gate (проверка клеймов: regex L1 → LLM L2/L3)
    ↓
A30 higgsfield_agent (UGC видео / Shorts / Карусель)
    ↓
A29 prelanding_generator (HTML прелендинг)
    ↓
A26 publer_publisher (TikTok / Facebook / Instagram)
    ↓
Keitaro postback (UTM трекинг → конверсии)
```

**Параллельно:** A20 trend_scraper (06:00 ежедн.) → A24 Obsidian Brain → A15 Strategy Engine (воскр.)

---

## 📊 Состояние на 30 июня 2026

| Компонент | Статус |
|-----------|--------|
| Сервер FirstVDS Amsterdam, 8 CPU / 12 GB / Ubuntu 22.04 | ✅ Развёрнут |
| n8n (5678), LiteLLM (4000), UBT Agents (8080), Dashboard (3000) | ✅ 4 сервиса live |
| Supabase — 25+ таблиц, Redis (Upstash) | ✅ Подключены |
| 6 n8n-воркфлоу (контент, аккаунты, стратегия, риски, здоровье, знания) | ✅ Активны |
| Все 19 агентов A12–A30 написаны и протестированы | ✅ Готовы |
| Двойная аутентификация API (HMAC + Bearer) | ✅ Включена |
| CI: ruff + mypy + pytest + bandit | ✅ Зелёный |
| Vertical configs: 1win (betting), Dr.Cash (nutra COD) | ✅ Готовы |

### Требует ключей / регистрации

| Что | Где взять |
|-----|-----------|
| `HIGGSFIELD_API_KEY` | [higgsfield.ai](https://higgsfield.ai) — A30 видео/карусели |
| `PUBLER_API_KEY` + Profile IDs | [app.publer.io](https://app.publer.io) — $12/мес |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://firecrawl.dev) — A20 trend_scraper |
| 1win Partners / Dr.Cash аккаунты | [1winpartners.com](https://1winpartners.com) · [dr.cash](https://dr.cash) |
| TikTok/Facebook/Instagram аккаунты | Aged-аккаунты → прогрев A28 |

---

## 🚀 Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/spro100/ubt-os.git
cd ubt-os

# 2. Окружение — скопировать шаблон и заполнить ключи
cp .env.template .env
#   минимум: ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, REDIS_URL

# 3. Зависимости
pip install -r deploy/requirements.txt

# 4. Запустить агентский сервер (:8080)
python -m ubt_os.main

# 5. Dashboard в отдельном терминале
cd dashboard && npm install && npm run dev
```

Через Docker:

```bash
docker compose up -d
```

---

## ⚙️ Конфигурация окружения

Все переменные описаны в [`.env.template`](.env.template). Ключевые:

```bash
# Обязательны для старта
ANTHROPIC_API_KEY=...          # Claude API
SUPABASE_URL=...               # Supabase project URL
SUPABASE_SERVICE_KEY=...       # service_role key (только сервер!)
REDIS_URL=...                  # Upstash Redis

# Безопасность
WEBHOOK_SECRET=...             # HMAC-подпись вебхуков n8n
AGENTS_API_TOKEN=...           # Bearer-токен для dashboard → /agents/run
CORS_ALLOW_ORIGIN=https://...  # домен dashboard (в проде НЕ "*")

# Публикация / медиа / тренды
PUBLER_API_KEY=...             # A26
HIGGSFIELD_API_KEY=...         # A30
FIRECRAWL_API_KEY=...          # A20
```

> ⚠️ Файл `.env` в `.gitignore` — секреты **никогда** не коммитятся.

---

## 🔐 Безопасность

UBT OS использует **двойную аутентификацию** для агентского HTTP-сервера —
любой запрос к защищённым маршрутам должен пройти один из путей:

| Источник | Механизм | Заголовок | Ключ |
|----------|----------|-----------|------|
| n8n / серверные вызовы | HMAC-SHA256 подпись | `X-Webhook-Signature` | `WEBHOOK_SECRET` |
| Dashboard / браузер | Bearer-токен | `Authorization: Bearer …` | `AGENTS_API_TOKEN` |

Если не задан ни один ключ — сервер работает в **dev-режиме** (без auth) и
пишет предупреждение в лог. В проде задавайте оба ключа.

**Настройка токена dashboard** (в консоли браузера):

```js
localStorage.setItem('agents_api_token', 'ваш-AGENTS_API_TOKEN')
```

**Чек-лист продакшена:**

- [ ] Заданы `WEBHOOK_SECRET` и `AGENTS_API_TOKEN`
- [ ] `CORS_ALLOW_ORIGIN` сужен до домена dashboard (не `*`)
- [ ] Трафик идёт через nginx + TLS (см. [`deploy/nginx.conf`](deploy/nginx.conf), `certbot`)
- [ ] Порты 3000/5678/8080/4000 закрыты в firewall, наружу только 80/443
- [ ] На таблицах Supabase настроен RLS (фронт работает на anon-ключе)

---

## 🖥 Dashboard

React 18 + Vite SPA. Live-данные из Supabase, чат с оркестратором, запуск
агентов без кода.

| Раздел | Что показывает |
|--------|----------------|
| **Дашборд** | приоритеты, статистика из Supabase в реальном времени |
| **Чат с оркестратором** | Claude Sonnet 4.6 в контексте проекта, предлагает агентов и quick-links |
| **Аккаунты** | TikTok / Facebook / Instagram, добавление + запуск A28 прогрева |
| **Контент** | производственный пайплайн, история публикаций |
| **Запуск агентов** | веб-интерфейс для всех A19–A30 |
| **Агенты** | инвентарь, статусы, схема пайплайна |
| **Аналитика** | выручка, партнёрские условия |
| **Инфраструктура** | сервер, сервисы, Supabase |

---

## 🧰 Стек

| Слой | Технология |
|------|-----------|
| AI | Claude Sonnet 4.6 (оркестратор) + Claude Haiku 4.5 (рутина) |
| Видео | Higgsfield AI API (seedance_2_0, image gen) |
| Публикация | Publer API — TikTok + Facebook + Instagram + Pinterest |
| Автоматизация | n8n self-hosted |
| База данных | Supabase (PostgreSQL, 25+ таблиц) + Redis (Upstash) |
| Трекинг | Keitaro UTM + Postback |
| Прокси | IPRoyal (mobile) + Airalo eSIM |
| Браузеры | Dolphin Anty (anti-detect, multi-account) |
| Память | Obsidian Vault + GitHub sync |
| Dashboard | React 18 + Vite |

---

## 🧪 Разработка и качество

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) гоняет на каждый push:

```bash
pip install -r deploy/requirements-dev.txt

ruff check ubt_os/                          # линтинг
mypy ubt_os/ --ignore-missing-imports       # типы
pytest tests/ -v                            # юнит-тесты
bandit -r ubt_os/ -ll                       # безопасность
```

Конфигурация ruff и mypy — в [`pyproject.toml`](pyproject.toml).
Покрытие тестами: аутентификация вебхуков, compliance-regex (L1), парсинг JSON
из LLM-ответов, circuit breaker, логирование, vault-path.

---

## 🌍 GEO и вертикали

| GEO | Часовой пояс | TikTok | Facebook |
|-----|-------------|--------|----------|
| US | ET (UTC-5) | 07:00, 12:00, 19:00 | 09:00, 13:00, 20:00 |
| BR | BRT (UTC-3) | 08:00, 13:00, 21:00 | 10:00, 14:00, 21:00 |
| MX | CST (UTC-6) | 07:00, 14:00, 20:00 | 09:00, 13:00, 19:00 |
| DE | CET (UTC+1) | 06:00, 12:00, 18:00 | 08:00, 12:00, 18:00 |
| PL | CET (UTC+1) | 07:00, 13:00, 20:00 | 09:00, 13:00, 19:00 |

**Вертикали:** `1win.yaml` (betting, GEO BR/MX/TR, CPA $25), `dr_cash.yaml`
(nutra COD, GEO US/BR/MX/DE/PL).

---

## 📁 Структура репозитория

```
ubt-os/
├── ubt_os/
│   ├── agents/              # A12–A30 агенты
│   ├── core/                # circuit breaker, budget guard, pipeline lock, risk engine
│   ├── pipelines/           # Higgsfield queue/worker, DLQ
│   ├── utils/               # attribution, Obsidian git sync, LLM utils
│   └── main.py              # HTTP-сервер :8080, webhook от n8n, auth
│
├── dashboard/               # React 18 + Vite SPA
├── vertical_configs/        # 1win.yaml, dr_cash.yaml, sample_configs.yaml
├── .claude/skills/          # Claude Code скиллы (/publer, /prelanding, /higgsfield …)
├── obsidian-vault/          # База знаний (wiki-страницы)
├── deploy/                  # Dockerfile, SQL-схемы, nginx, LiteLLM config
├── n8n/workflows/           # 6 воркфлоу (JSON)
├── tests/                   # pytest
├── .env.template            # шаблон переменных окружения
└── pyproject.toml           # конфиг ruff + mypy
```

---

<div align="center">

*User is always the final decision-maker. Nothing executes without explicit approval.*

</div>
