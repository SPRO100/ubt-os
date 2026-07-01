<div align="center">

<img src="https://img.shields.io/badge/UBT-OS-8A2BE2?style=for-the-badge&labelColor=1a1a2e" alt="UBT OS" height="40"/>

# 🧠 UBT OS

### Автономная мульти-агентная AI-система для органического трафика на партнёрские офферы

*От анализа конкурентов и генерации контента — до прогрева аккаунтов, compliance и публикации с трекингом. Под управлением Claude.*

<br/>

[![CI](https://github.com/spro100/ubt-os/actions/workflows/ci.yml/badge.svg)](https://github.com/spro100/ubt-os/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/AI-Claude_Sonnet_5_+_Haiku_4.5-8A2BE2?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![React](https://img.shields.io/badge/Dashboard-React_18_+_Vite-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Lint](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![Types](https://img.shields.io/badge/types-mypy-2A6DB2)](https://mypy-lang.org/)
[![Security](https://img.shields.io/badge/security-bandit-yellow)](https://bandit.readthedocs.io/)

<br/>

**26 AI-агентов** · **8 платформ** · **5 GEO** · **Live Dashboard** · **Self-hosted**

`TikTok` · `Facebook` · `Instagram` · `YouTube` · `Pinterest` · `Threads` · `X` · `LinkedIn`

</div>

---

<div align="center">

| 🎬 Контент | 🛡 Безопасность | 📊 Аналитика | ⚙️ Надёжность |
|:---:|:---:|:---:|:---:|
| UGC-видео, Shorts, карусели, прелендинги | 3-уровневый compliance + двойная auth | Attribution, утечки воронки, risk-скоринг | Circuit breaker · DLQ · budget guard |

</div>

---

## 📋 Содержание

- [Что это](#-что-это)
- [Почему это работает](#-почему-это-работает)
- [Архитектура](#-архитектура)
- [Карта агентов](#-карта-агентов)
- [Полный пайплайн](#-полный-пайплайн)
- [Что нового](#-что-нового)
- [Быстрый старт](#-быстрый-старт)
- [Конфигурация](#-конфигурация-окружения)
- [Безопасность](#-безопасность)
- [Dashboard](#-dashboard)
- [Стек](#-стек)
- [Качество и CI](#-качество-и-ci)
- [GEO и вертикали](#-geo-и-вертикали)
- [Структура репозитория](#-структура-репозитория)

---

## 🎯 Что это

UBT OS — оркестрированная система из **26 AI-агентов**, закрывающая весь цикл
партнёрского маркетинга на органике: разведка крипов конкурентов → генерация
контента → очистка от AI-маркеров → проверка на compliance → производство видео
и прелендингов → прогрев аккаунтов → публикация с UTM-трекингом.

Ядро — **Claude Sonnet 5** (оркестратор) и **Claude Haiku 4.5** (рутина).
Агенты связаны n8n-воркфлоу и общим HTTP-слоем; состояние живёт в Supabase +
Redis; база знаний — в Obsidian Vault с git-синхронизацией.

> 💡 **Принцип:** пользователь — всегда финальный принимающий решение.
> Ничего не публикуется без явного подтверждения.

---

## ⚡ Почему это работает

- **🤖 Полная автоматизация цикла** — 26 агентов покрывают путь от идеи до конверсии без ручного труда.
- **🛡 Безопасность контента** — трёхуровневый Compliance Gate (regex L1 → Claude L2/L3) ловит запрещённые клеймы до публикации.
- **🔐 Защищённый API** — двойная аутентификация (HMAC для n8n + Bearer для dashboard), настраиваемый CORS.
- **♻️ Отказоустойчивость** — circuit breaker, distributed lock, dead-letter queue, budget guard против перерасхода токенов.
- **📈 Атрибуция и риски** — анализ утечек воронки и risk-скоринг аккаунтов в реальном времени.
- **🧠 Самоорганизующаяся память** — Obsidian Vault как AI-wiki с ежедневным синтезом знаний.
- **🎛 Управление без кода** — React-дашборд: запуск любого агента, чат с оркестратором, импорт аккаунтов.

---

## 🏗 Архитектура

```
                         ┌──────────────────────────┐
                         │   ORCHESTRATOR (Sonnet)  │
                         │  чат в контексте проекта │
                         └────────────┬─────────────┘
                                      │
   ┌──────────┬──────────┬───────────┼───────────┬──────────────┬───────────┐
   ▼          ▼          ▼           ▼           ▼              ▼           ▼
┌──────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐ ┌────────────┐ ┌────────┐
│ Ядро │ │Контент │ │Аналитика│ │Compliance│ Публикация│ │Медиа+Affil │ │ Спец.  │
│A12-18│ │A19-A21 │ │ A22-A24 │ │   A25   │ │ A26+Direct│ │  A27-A30   │ │A31+Trans│
└──────┘ └────────┘ └─────────┘ └────────┘ └──────────┘ └────────────┘ └────────┘
   │                                                                          │
   └────── Circuit Breaker · Budget Guard · Pipeline Lock · Dead Letter Queue ┘
                                      │
                ┌─────────────────────┼─────────────────────┐
                ▼                     ▼                     ▼
           ┌─────────┐          ┌──────────┐          ┌──────────┐
           │ Supabase│          │  Redis   │          │ Obsidian │
           │ 25+ табл│          │ (Upstash)│          │  Vault   │
           └─────────┘          └──────────┘          └──────────┘
```

---

## 🗺 Карта агентов

### Ядро (A12–A18)

| ID | Файл | Роль |
|----|------|------|
| A12 | `warming_state_machine.py` | FSM прогрева аккаунтов, фазы активности |
| A13 | `telegram_jitter.py` | Случайные задержки, human-behavior |
| A14 | `account_checker.py` | Здоровье аккаунта, ER, прокси, бан |
| A15 | `strategy_engine.py` | Недельный стратегический бриф |
| A16 | `revenue_analyst.py` | Attribution, утечки воронки |
| A17 | `failure_recovery.py` | DLQ, health-check, fallback |
| A18 | `knowledge_synthesizer.py` | Синтез знаний (ежедневно) |

### Контент и аналитика (A19–A24)

| ID | Файл | Роль |
|----|------|------|
| A19 | `text_humanizer.py` | Stop-Slop: очистка AI-маркеров |
| A20 | `trend_scraper.py` | Тренды и хуки конкурентов (Firecrawl) |
| A21 | `content_creator.py` | Before/After, хуки, UGC по Brand Voice |
| A22 | `ads_auditor.py` | Аудит TikTok/Meta, Health Score 0–100 |
| A23 | `youtube_creator.py` | Shorts/Long-form, retention-инжиниринг |
| A24 | `obsidian_brain.py` | Self-organizing AI wiki |

### Публикация, Affiliate Intelligence и медиа (A25–A30)

| ID | Файл | Роль |
|----|------|------|
| A25 | `compliance_gate.py` | Проверка контента: Regex L1 → Claude L2/L3 |
| A26 | `publer_publisher.py` | Publer API — TikTok/FB/IG/Pinterest + UTM |
| A27 | `spy_analyzer.py` | Анализ крипов PiPiAds/AdHeart → brief для A21 |
| A28 | `warmup_manager.py` | 14-дневный прогрев, лимиты, инфра-валидация |
| A29 | `prelanding_generator.py` | HTML прелендинги (quiz/story/article/vsl) |
| A30 | `higgsfield_agent.py` | UGC 9:16/16:9 · Shorts · Карусели |

### Расширения 🆕

| ID | Файл | Роль |
|----|------|------|
| A31 | `competitor_analyst.py` | Анализ хуков конкурентов (дополняет A27) |
| A32 | `trend_radar.py` | Ранжирование трендовых звуков/хэштегов → «на чём ехать» |
| A33 | `competitor_scraper.py` | Авто-сбор крипов в `competitor_signals` (кормит A31) |
| A34 | `caption_agent.py` | Авто-субтитры (ASS/SRT, TikTok-style) + ffmpeg burn |
| A35 | `tts_agent.py` | Озвучка faceless-видео (self-hosted TTS → ElevenLabs) |
| — | `transcription_agent.py` | Транскрипция видео (Deepgram → Whisper) + извлечение хука |
| — | `pipelines/social_publisher.py` | Прямая публикация на 8 платформ через нативные API |

---

## 🔄 Полный пайплайн

```
A27 spy_analyzer ─┐
A31 competitor_analyst ─┤→ анализ крипов и хуков конкурентов
                  ↓
A21 content_creator (хуки, before/after, UGC)
                  ↓
A19 text_humanizer (Stop-Slop очистка)
                  ↓
A25 compliance_gate (regex L1 → LLM L2/L3)
                  ↓
A30 higgsfield_agent (UGC / Shorts / Карусель)
                  ↓
A29 prelanding_generator (HTML прелендинг)
                  ↓
A26 publer_publisher  ──или──  social_publisher (прямые API, 8 платформ)
                  ↓
Keitaro postback (UTM → конверсии)
```

**Параллельно:** A20 trend_scraper (06:00) → A24 Obsidian Brain → A15 Strategy Engine (воскр.)

---

## 🆕 Что нового

### Оркестратор знает всех агентов

Каталог оркестратора и диспетчер `/agents/run` расширены: теперь **все on-demand
агенты A19–A35** (включая новые A31–A35, transcription, social_publisher)
доступны оркестратору — он предлагает их в чате и роутит запросы вроде
«собери тренды» → A32/A33, «сделай субтитры» → A34, «озвучь скрипт» → A35.

### Релиз — июль 2026 (медиа)

**🎬 Медиа-агенты для органики**
- **A34 `caption_agent`** — строит стилизованные субтитры (ASS/SRT, TikTok-style, фразами по 2–4 слова) из word-таймингов Deepgram + ffmpeg-команда burn. Субтитры резко поднимают удержание. Route `POST /caption`.
- **A35 `tts_agent`** — озвучка faceless-видео: self-hosted TTS (`TTS_SERVER_URL`, Kokoro/Chatterbox) → fallback ElevenLabs, аудио в Supabase Storage. Route `POST /tts`.
- Dashboard: раздел **«Медиа»** — озвучка скрипта (плеер) и генерация субтитров (ffmpeg-команда + SRT-превью). Агентов **24 → 26** (A12–A35).

### Релиз — июль 2026

**🧩 Два новых агента (из ресерча open-source)**
- **A32 `trend_radar`** — ранжирует трендовые звуки/хэштеги под vertical/GEO через Claude и говорит, «на чём ехать прямо сейчас» (окно 3–5 дней до пика). Источник: `TREND_SOURCE_URL` или данные в запросе. Route `POST /trends/radar`.
- **A33 `competitor_scraper`** — тонкий клиент к self-hosted TikTok-скраперу (`TIKTOK_SCRAPER_URL`, совместим с Douyin_TikTok_Download_API): тянет топ-видео по хэштегу, нормализует в `competitor_signals` — которые читает A31. Замыкает разрыв: раньше крипы заносили вручную. Route `POST /competitor/scrape`.

**🖥 Dashboard**
- Новый раздел **«Тренды»**: Trend Radar (ранжирование + бриф) и живая лента крипов конкурентов с кнопкой сбора.

### Релиз — июнь 2026

**🔐 Безопасность**
- Двойная аутентификация агентского API: HMAC-SHA256 (n8n) + Bearer-токен (dashboard).
- Настраиваемый CORS-origin и bind-host вместо хардкода.

**🧩 Новые возможности**
- **A31 competitor_analyst** — анализ хуков конкурентов на собственном LLM-пайплайне.
- **transcription_agent** — транскрипция видео через Deepgram с fallback на OpenAI Whisper + извлечение хука.
- **social_publisher** — прямая публикация на **8 платформ** (TikTok, YouTube, Instagram, Facebook, Pinterest, Threads, X, LinkedIn) через нативные API + presigned S3.

**🛠 Качество и устойчивость**
- Исправлен критический баг fallback-режима (битый импорт circuit breaker).
- Исправлен runtime-баг суточного отчёта DLQ.
- Устойчивый парсинг JSON из ответов LLM (даже с текстом вокруг).
- Все `datetime.utcnow()` → timezone-aware.

**🖥 Dashboard (React 18 + Vite)**
- Конфигурация через `VITE_*` env — деплой на любой сервер; `VITE_AGENTS_SERVER=""` → same-origin (**работает за nginx без порта**).
- Баннер ошибок API вместо молчаливых нулей; revenue считается серверным aggregate с fallback.
- Hash-роутинг (deep-link секций, кнопка «назад», сохранение при refresh).
- Доступность: `aria-current` / `aria-label` / `aria-hidden`.
- Актуализированы данные: 22 агента (A12–A31), платформы TikTok/Facebook/Instagram/Pinterest.
- ESLint + **9 Vitest-тестов**; пофикшены реальные баги (missing keys, `target=_blank`, кавычки).

**🗄 База данных и прямая публикация**
- `make db-init` применяет все **12 схем** (включая таблицы новых агентов: `hook_templates`, `competitor_signals`, `transcriptions`, `direct_publish_*`).
- Креды платформ для прямой публикации — per-account в таблице `direct_publish_accounts`.

**✅ CI стал зелёным (5 джобов)**
- `ruff` — 0 ошибок (было 80), добавлен конфиг под стиль проекта.
- `mypy` — 0 ошибок (было 130).
- `pytest` — 58 тестов (compliance regex, JSON-парсинг, dual-auth и др.).
- `bandit` — 0 предупреждений.
- `dashboard` — eslint + vitest + build на каждый push/PR.

**📚 Документация**
- Добавлены `.env.template`, `dashboard/.env.example`, `CLAUDE.md`, `pyproject.toml`.
- Полностью переоформлён README, changelog поддерживается в актуальном состоянии.

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

# 5. Dashboard (React 18 + Vite)
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
# Обязательны
ANTHROPIC_API_KEY=...          # Claude API
SUPABASE_URL=...               # Supabase project URL
SUPABASE_SERVICE_KEY=...       # service_role key (только сервер!)
REDIS_URL=...                  # Upstash Redis

# Безопасность
WEBHOOK_SECRET=...             # HMAC-подпись вебхуков n8n
AGENTS_API_TOKEN=...           # Bearer-токен для dashboard
CORS_ALLOW_ORIGIN=https://...  # домен dashboard (в проде НЕ "*")

# Возможности
PUBLER_API_KEY=...             # A26 публикация
HIGGSFIELD_API_KEY=...         # A30 видео
FIRECRAWL_API_KEY=...          # A20 тренды
DEEPGRAM_API_KEY=...           # транскрипция (OPENAI_API_KEY — fallback)
```

> ⚠️ Файл `.env` в `.gitignore` — секреты **никогда** не коммитятся.

---

## 🔐 Безопасность

Агентский HTTP-сервер использует **двойную аутентификацию** — запрос проходит,
если выполнен **любой** из путей:

| Источник | Механизм | Заголовок | Ключ |
|----------|----------|-----------|------|
| n8n / сервер | HMAC-SHA256 | `X-Webhook-Signature` | `WEBHOOK_SECRET` |
| Dashboard / браузер | Bearer-токен | `Authorization: Bearer …` | `AGENTS_API_TOKEN` |

Если не задан ни один ключ — сервер работает в **dev-режиме** (без auth) с
предупреждением в лог. **Чек-лист продакшена:**

- [ ] Заданы `WEBHOOK_SECRET` и `AGENTS_API_TOKEN`
- [ ] `CORS_ALLOW_ORIGIN` сужен до домена dashboard (не `*`)
- [ ] Трафик через nginx + TLS ([`deploy/nginx.conf`](deploy/nginx.conf), `certbot`)
- [ ] Порты 3000/5678/8080/4000 закрыты в firewall, наружу только 80/443
- [ ] На таблицах Supabase настроен RLS (фронт на anon-ключе)

---

## 🖥 Dashboard

React 18 + Vite SPA с live-данными из Supabase.

| Раздел | Что показывает |
|--------|----------------|
| **Дашборд** | приоритеты, статистика в реальном времени |
| **Чат с оркестратором** | Claude Sonnet 5 в контексте проекта + quick-links |
| **Аккаунты** | TikTok/FB/IG, добавление + запуск A28 прогрева |
| **Контент** | производственный пайплайн, история публикаций |
| **Запуск агентов** | веб-интерфейс для всех агентов без кода |
| **Агенты** | инвентарь, статусы, схема пайплайна |
| **Аналитика** | выручка, партнёрские условия |
| **Инфраструктура** | сервер, сервисы, Supabase |

---

## 🧰 Стек

| Слой | Технология |
|------|-----------|
| AI | Claude Sonnet 5 (оркестратор) + Claude Haiku 4.5 (рутина) |
| Видео | Higgsfield AI API · Deepgram / Whisper (транскрипция) |
| Публикация | Publer API + прямые нативные API (8 платформ) |
| Автоматизация | n8n self-hosted |
| База данных | Supabase (PostgreSQL, 25+ таблиц) + Redis (Upstash) |
| Трекинг | Keitaro UTM + Postback |
| Прокси | IPRoyal (mobile) + Airalo eSIM |
| Браузеры | Dolphin Anty (anti-detect, multi-account) |
| Память | Obsidian Vault + GitHub sync |
| Dashboard | React 18 + Vite |

---

## 🧪 Качество и CI

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) на каждый push:

```bash
pip install -r deploy/requirements-dev.txt

ruff check ubt_os/                          # линтинг      ✅ 0 ошибок
mypy ubt_os/ --ignore-missing-imports       # типы         ✅ 0 ошибок
pytest tests/ -v                            # 58 тестов    ✅ зелёные
bandit -r ubt_os/ -ll                       # безопасность ✅ 0 предупреждений
```

Конфигурация ruff и mypy — в [`pyproject.toml`](pyproject.toml). Покрытие:
аутентификация (dual-auth), compliance-regex (L1), парсинг JSON из LLM,
circuit breaker, логирование, vault-path.

---

## 🌍 GEO и вертикали

| GEO | Часовой пояс | TikTok | Facebook |
|-----|-------------|--------|----------|
| US | ET (UTC-5) | 07:00, 12:00, 19:00 | 09:00, 13:00, 20:00 |
| BR | BRT (UTC-3) | 08:00, 13:00, 21:00 | 10:00, 14:00, 21:00 |
| MX | CST (UTC-6) | 07:00, 14:00, 20:00 | 09:00, 13:00, 19:00 |
| DE | CET (UTC+1) | 06:00, 12:00, 18:00 | 08:00, 12:00, 18:00 |
| PL | CET (UTC+1) | 07:00, 13:00, 20:00 | 09:00, 13:00, 19:00 |

**Вертикали:** `1win.yaml` (betting, GEO BR/MX/TR, CPA $25) · `dr_cash.yaml`
(nutra COD, GEO US/BR/MX/DE/PL).

---

## 📁 Структура репозитория

```
ubt-os/
├── ubt_os/
│   ├── agents/              # A12–A31 + transcription
│   ├── core/                # circuit breaker, budget guard, pipeline lock, risk engine
│   ├── pipelines/           # Higgsfield queue/worker, DLQ, social_publisher
│   ├── utils/               # attribution, Obsidian git sync, LLM utils
│   └── main.py              # HTTP-сервер :8080, webhook от n8n, dual-auth
│
├── dashboard/               # React 18 + Vite SPA
├── vertical_configs/        # 1win.yaml, dr_cash.yaml, sample_configs.yaml
├── .claude/skills/          # Claude Code скиллы (/publer, /prelanding, /higgsfield …)
├── obsidian-vault/          # База знаний (wiki-страницы)
├── deploy/                  # Dockerfile, SQL-схемы, nginx, LiteLLM config
├── n8n/workflows/           # воркфлоу (JSON)
├── tests/                   # pytest (58 тестов)
├── .env.template            # шаблон переменных окружения
├── pyproject.toml           # конфиг ruff + mypy
└── CLAUDE.md                # гайд для AI-ассистентов
```

---

<div align="center">

<br/>

**UBT OS** — *built with [Claude Code](https://claude.com/claude-code)*

*User is always the final decision-maker. Nothing executes without explicit approval.*

</div>
