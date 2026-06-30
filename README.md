# UBT OS — Multi-Agent AI System for Organic Traffic

> Мульти-агентная AI-система для генерации органического трафика на партнёрские офферы.
> **19 агентов (A12–A30) · 3 платформы (TikTok / Facebook / Instagram) · 2 вертикали (Nutra + Betting)**

---

## Состояние на 30 июня 2026

### Готово и работает

| Компонент | Статус |
|-----------|--------|
| Сервер FirstVDS Amsterdam, 8 CPU / 12 GB / Ubuntu 22.04 | ✅ Развёрнут |
| n8n (5678), LiteLLM (4000), UBT Agents (8080), Dashboard (3000) | ✅ 4 сервиса live |
| Supabase — 25+ таблиц, Redis (Upstash) | ✅ Подключены |
| 6 n8n-воркфлоу (контент, аккаунты, стратегия, риски, здоровье, знания) | ✅ Активны |
| Dashboard → `http://88.218.121.108:3000` (live данные из Supabase) | ✅ Работает |
| Все 19 агентов A12–A30 написаны и протестированы | ✅ Готовы |
| Публикация через Publer API (TikTok + Facebook + Instagram) | ✅ A26 готов |
| Compliance Gate 3-уровневый (regex L1 + LLM L2/L3) | ✅ A25 готов |
| Spy-анализ крипов конкурентов (PiPiAds/AdHeart) | ✅ A27 готов |
| 14-дневный прогрев аккаунтов с валидацией инфраструктуры | ✅ A28 готов |
| HTML прелендинги (quiz/story/article/vsl) — COD/Trial/SS | ✅ A29 готов |
| UGC-видео 9:16/16:9, Shorts, Карусели через Higgsfield AI | ✅ A30 написан |
| Vertical configs: 1win (betting), Dr.Cash (nutra COD) | ✅ Готовы |
| Claude Code Skills: `/publer`, `/prelanding`, `/higgsfield` и 9 других | ✅ 11 скиллов |

### Требует ключей / регистрации

| Что | Где взять |
|-----|-----------|
| `HIGGSFIELD_API_KEY` | [higgsfield.ai](https://higgsfield.ai) — нужен для A30 видео/каруселей |
| `PUBLER_API_KEY` + Profile IDs | [app.publer.io](https://app.publer.io) — $12/мес |
| 1win Partners аккаунт | [1winpartners.com](https://1winpartners.com) |
| Dr.Cash аккаунт | [dr.cash](https://dr.cash) |
| TikTok/Facebook/Instagram аккаунты | Покупать Aged аккаунты → прогрев A28 |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://firecrawl.dev) — нужен для A20 trend_scraper |

---

## Архитектура агентов

### Ядро (A12–A18)

| ID | Файл | Роль |
|----|------|------|
| A12 | `warming_state_machine.py` | FSM прогрева аккаунтов, фазы активности |
| A13 | `telegram_jitter.py` | Случайные задержки, human-behavior |
| A14 | `account_checker.py` | Здоровье аккаунта, ER, прокси, бан |
| A15 | `strategy_engine.py` | Недельный стратегический бриф (воскр. 20:00) |
| A16 | `revenue_analyst.py` | Attribution, утечки воронки |
| A17 | `failure_recovery.py` | DLQ, Health check 60s, fallback |
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
| A26 | `blotato_publisher.py` | Publer API — TikTok / Facebook / Instagram + UTM |

### Affiliate Intelligence (A27–A29)

| ID | Файл | Роль |
|----|------|------|
| A27 | `spy_analyzer.py` | Анализ крипов PiPiAds/AdHeart → creative brief для A21 |
| A28 | `warmup_manager.py` | 14-дневный прогрев, лимиты активности, инфра-валидация |
| A29 | `prelanding_generator.py` | HTML прелендинги (quiz/story/article/vsl), мультиязычный |

### Медиа-генерация (A30)

| ID | Файл | Роль |
|----|------|------|
| A30 | `higgsfield_agent.py` | UGC 9:16/16:9 · Shorts · Карусели для белых офферов |

---

## Полный пайплайн

```
A27 spy_analyzer (PiPiAds/AdHeart крипы)
    ↓
A21 content_creator (хуки, before/after, UGC)
    ↓
A19 text_humanizer (Stop-Slop очистка)
    ↓
A25 compliance_gate (проверка клеймов)
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

## Структура репозитория

```
ubt-os/
├── ubt_os/
│   ├── agents/              # A12–A30 агенты
│   │   ├── warming_state_machine.py
│   │   ├── account_checker.py
│   │   ├── telegram_jitter.py
│   │   ├── text_humanizer.py
│   │   ├── trend_scraper.py
│   │   ├── content_creator.py
│   │   ├── ads_auditor.py
│   │   ├── youtube_creator.py
│   │   ├── obsidian_brain.py
│   │   ├── compliance_gate.py
│   │   ├── blotato_publisher.py  # A26, Publer API
│   │   ├── spy_analyzer.py
│   │   ├── warmup_manager.py     # state → ~/.ubt_os/warmup_state.json
│   │   ├── prelanding_generator.py
│   │   └── higgsfield_agent.py   # A30, UGC+Shorts+Carousel
│   ├── core/                # Circuit breaker, budget guard, pipeline lock
│   ├── pipelines/           # Higgsfield queue/worker, DLQ
│   ├── utils/               # Attribution, Obsidian git sync
│   └── main.py              # HTTP сервер :8080, webhook от n8n
│
├── dashboard-static/
│   └── index.html           # SPA: дашборд, чат с оркестратором, запуск агентов
│
├── vertical_configs/
│   ├── 1win.yaml            # Betting: 1win Partners, GEO BR/MX/TR, CPA $25
│   ├── dr_cash.yaml         # Nutra COD: Dr.Cash, GEO US/BR/MX/DE/PL
│   └── sample_configs.yaml  # Авто, инфопродукты, недвижимость, крипто
│
├── .claude/skills/          # Claude Code скиллы (11 штук)
│   ├── publer.md            # /publer — управление публикациями
│   ├── prelanding.md        # /prelanding — генерация прелендингов
│   ├── higgsfield.md        # /higgsfield — видеогенерация
│   ├── keitaro.md           # /keitaro — трекинг и UTM
│   ├── stop-slop.md         # /stop-slop — очистка AI-текста
│   ├── marketing.md         # /marketing — промпты для контента
│   ├── brand-voice.md       # /brand-voice — голос бренда по GEO
│   ├── seo-machine.md       # /seo-article — SEO статьи
│   ├── firecrawl-scraper.md # /firecrawl-audit — аудит конкурентов
│   ├── arcads.md            # /arcads — AI видео-реклама
│   └── market-research.md   # /market-report — конкурентный анализ
│
├── obsidian-vault/          # База знаний (11 wiki-страниц)
├── deploy/                  # Dockerfile, SQL схемы, LiteLLM config
├── n8n/workflows/           # 6 воркфлоу (JSON)
└── .env.template            # Все переменные окружения
```

---

## Стек

| Слой | Технология |
|------|-----------|
| AI | Claude Sonnet 4.6 (оркестратор) + Claude Haiku 4.5 (рутинные задачи) |
| Видео | Higgsfield AI API (seedance_2_0, image gen) |
| Публикация | Publer API $12/мес — TikTok ✅ + Facebook + Instagram |
| Автоматизация | n8n self-hosted |
| База данных | Supabase (PostgreSQL, 25+ таблиц) + Redis (Upstash) |
| Трекинг | Keitaro UTM + Postback |
| Прокси | IPRoyal (mobile, pay per GB) + Airalo eSIM |
| Браузеры | Dolphin Anty (multi-account, anti-detect) |
| Память | Obsidian Vault + GitHub sync |
| Dashboard | Ванильный JS SPA на :3000 (без фреймворков) |

---

## Переменные окружения

```bash
# Обязательны для старта
ANTHROPIC_API_KEY=...          # Claude API
SUPABASE_URL=...               # Supabase project URL
SUPABASE_SERVICE_KEY=...       # Supabase service role key
REDIS_URL=...                  # Upstash Redis

# Публикация (A26 Publer)
PUBLER_API_KEY=...
PUBLER_TIKTOK_PROFILE_IDS=id1,id2
PUBLER_FACEBOOK_PROFILE_IDS=id1,id2
PUBLER_INSTAGRAM_PROFILE_IDS=id1,id2

# Медиа-генерация (A30 Higgsfield)
HIGGSFIELD_API_KEY=...

# Тренды (A20)
FIRECRAWL_API_KEY=...

# A28 — состояние прогрева (по умолчанию ~/.ubt_os/warmup_state.json)
WARMUP_STATE_FILE=/var/lib/ubt_os/warmup_state.json

# Безопасность webhook
WEBHOOK_SECRET=...
```

---

## Dashboard

URL: `http://88.218.121.108:3000`

Разделы:
- **Дашборд** — приоритеты, статистика из Supabase в реальном времени
- **Чат с оркестратором** — Claude Sonnet 4.6 в контексте проекта, предлагает агентов, показывает quick_links на внешние сервисы
- **Аккаунты** — TikTok / Facebook / Instagram, форма добавления + запуск A28 прогрева
- **Контент** — производственный пайплайн, история публикаций
- **Запуск агентов** — веб-интерфейс для всех A19–A30 (без кода)
- **Агенты** — инвентарь, статусы, схема пайплайна
- **Аналитика** — выручка, партнёрские условия
- **Инфраструктура** — сервер, сервисы, Supabase

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/spro100/ubt-os.git
cd ubt-os

# 2. Окружение
cp .env.template .env
# Заполни ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

# 3. Установить зависимости
pip install -r deploy/requirements.txt

# 4. Запустить агентский сервер
python -m ubt_os.main

# 5. Dashboard (в отдельном терминале)
python -m http.server 3000 --directory dashboard-static
```

Или через Docker:
```bash
docker compose up -d
```

---

## GEO и вертикали

| GEO | Часовой пояс | TikTok лучшее время | Facebook лучшее время |
|-----|-------------|--------------------|-----------------------|
| US | ET (UTC-5) | 07:00, 12:00, 19:00 | 09:00, 13:00, 20:00 |
| BR | BRT (UTC-3) | 08:00, 13:00, 21:00 | 10:00, 14:00, 21:00 |
| MX | CST (UTC-6) | 07:00, 14:00, 20:00 | 09:00, 13:00, 19:00 |
| DE | CET (UTC+1) | 06:00, 12:00, 18:00 | 08:00, 12:00, 18:00 |
| PL | CET (UTC+1) | 07:00, 13:00, 20:00 | 09:00, 13:00, 19:00 |

---

*User is always the final decision-maker. Nothing executes without explicit approval.*
