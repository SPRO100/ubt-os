<div align="center">

<img src="https://img.shields.io/badge/UBT-OS-8A2BE2?style=for-the-badge&labelColor=1a1a2e" alt="UBT OS" height="40"/>

# 🧠 UBT OS

### Автономная мульти-агентная AI-система для органического трафика на партнёрские офферы

*От генерации контента — до прогрева аккаунтов, compliance и публикации с трекингом. Никакого лишнего шума: только генерация видео и безопасная доставка. Под управлением Claude.*

<br/>

[![CI](https://github.com/spro100/ubt-os/actions/workflows/ci.yml/badge.svg)](https://github.com/spro100/ubt-os/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/AI-Claude_Sonnet_5_+_Haiku_4.5-8A2BE2?logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![React](https://img.shields.io/badge/Dashboard-React_18_+_Vite-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Lint](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![Types](https://img.shields.io/badge/types-mypy-2A6DB2)](https://mypy-lang.org/)
[![Security](https://img.shields.io/badge/security-bandit-yellow)](https://bandit.readthedocs.io/)

<br/>

**13 AI-агентов** · **8 платформ** · **5 GEO** · **Live Dashboard** · **Self-hosted**

`TikTok` · `Facebook` · `Instagram` · `YouTube` · `Pinterest` · `Threads` · `X` · `LinkedIn`

</div>

---

<div align="center">

| 🎬 Контент | 🛡 Безопасность | 📊 Аналитика | ⚙️ Надёжность |
|:---:|:---:|:---:|:---:|
| UGC-видео, Shorts, карусели | 3-уровневый compliance + двойная auth | Нативные метрики постов, risk-скоринг | Circuit breaker · DLQ · budget guard |

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

UBT OS — оркестрированная система из **13 AI-агентов**, закрывающая весь цикл
партнёрского маркетинга на органике: генерация контента → очистка от
AI-маркеров → проверка на compliance → производство видео → прогрев
аккаунтов → публикация с UTM-трекингом. Роль намеренно сужена до
**генерации + безопасной доставки** — никакого research/поискового слоя
(конкуренты, тренды) не запускается на каждом цикле.

Ядро — **Claude Sonnet 5** (оркестратор) и **Claude Haiku 4.5** (рутина).
Агенты связаны n8n-воркфлоу и общим HTTP-слоем; состояние живёт в Supabase +
Redis; база знаний — в Obsidian Vault с git-синхронизацией.

> 💡 **Принцип:** пользователь — всегда финальный принимающий решение.
> Ничего не публикуется без явного подтверждения.

---

## ⚡ Почему это работает

- **🤖 Лаконичный цикл, без шума** — 13 агентов покрывают путь от идеи до конверсии, без ручного труда и без лишних поисковых/аналитических прогонов.
- **🛡 Безопасность контента** — трёхуровневый Compliance Gate (regex L1 → Claude L2/L3) ловит запрещённые клеймы до публикации.
- **🔐 Защищённый API** — двойная аутентификация (HMAC для n8n + Bearer для dashboard), настраиваемый CORS.
- **♻️ Отказоустойчивость** — circuit breaker, distributed lock, dead-letter queue, budget guard против перерасхода токенов.
- **📈 Риски** — risk-скоринг аккаунтов в реальном времени, авто-пауза при критичных сигналах.
- **🧠 Синтез знаний раз в день** — A18 в конце дня (21:00) анализирует наши собственные результаты и пишет новое знание в `kb_entries`.
- **🎛 Управление без кода** — React-дашборд: запуск любого агента, чат с оркестратором, импорт аккаунтов.

---

## 🏗 Архитектура

```
                         ┌──────────────────────────┐
                         │   ORCHESTRATOR (Sonnet)  │
                         │  чат в контексте проекта │
                         └────────────┬─────────────┘
                                      │
        ┌──────────┬──────────┬──────┼──────┬──────────┬───────────┐
        ▼          ▼          ▼      ▼      ▼          ▼           ▼
     ┌──────┐ ┌────────┐ ┌────────┐ ┌────┐ ┌────────┐ ┌──────────┐ ┌────────┐
     │ Ядро │ │Контент │ │Compliance│Публик.│ │Медиа   │ │Прогрев+ │ │Знания  │
     │A13,14│ │A19,21,23│ │  A25   │ │A26+Dir│ │A30,34,35│ │Риск A28 │ │  A18   │
     └──────┘ └────────┘ └────────┘ └──────┘ └────────┘ └──────────┘ └────────┘
        │                                                                  │
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

Роль намеренно сужена в июле 2026: убран весь research/поисковый слой
(конкуренты, тренды, крипы) — агенты теперь делают только генерацию видео и
безопасную доставку. Итого **13 агентов**.

### Ядро

| ID | Файл | Роль |
|----|------|------|
| A13 | `telegram_jitter.py` | Случайные задержки, human-behavior |
| A14 | `account_checker.py` | Здоровье аккаунта, ER, прокси, бан |
| A18 | `knowledge_synthesizer.py` | Синтез знаний (ежедневно 21:00 + воскресенье) → `kb_entries` |
| A28 | `warmup_manager.py` | 14-дневный прогрев, лимиты, инфра-валидация (состояние в Supabase) |

### Контент

| ID | Файл | Роль |
|----|------|------|
| A19 | `text_humanizer.py` | Stop-Slop: очистка AI-маркеров |
| A21 | `content_creator.py` | Before/After, хуки, UGC по Brand Voice |
| A23 | `youtube_creator.py` | Shorts/Long-form, retention-инжиниринг |

### Compliance, публикация и медиа

| ID | Файл | Роль |
|----|------|------|
| A25 | `compliance_gate.py` | Проверка контента: Regex L1 → Claude L2/L3 |
| A26 | `publer_publisher.py` | Publer API — TikTok/FB/IG/Pinterest + UTM |
| A30 | `higgsfield_agent.py` | UGC 9:16/16:9 · Shorts · Карусели |
| A34 | `caption_agent.py` | Авто-субтитры (ASS/SRT, TikTok-style) + ffmpeg burn |
| A35 | `tts_agent.py` | Озвучка faceless-видео (self-hosted TTS → ElevenLabs) |
| — | `pipelines/social_publisher.py` | Прямая публикация на 8 платформ через нативные API |
| A36 | `post_analytics_agent.py` | Нативная аналитика постов (impressions/reach/likes/comments/shares) |

### Убрано в рамках пересборки (июль 2026)

A12 `warming_state_machine` (мёртвый код, слился в A28), A15 `strategy_engine`,
A16 `revenue_analyst` (мёртвый), A17 `failure_recovery` (мёртвый, DLQ живёт в
`blotato_dlq.py`), A20 `trend_scraper`, A22 `ads_auditor`, A24
`obsidian_brain`, A27 `spy_analyzer`, A29 `prelanding_generator`, A31
`competitor_analyst`, A32 `trend_radar`, A33 `competitor_scraper`,
`transcription_agent`.

---

## 🔄 Полный пайплайн

```
A21 content_creator (хуки, before/after, UGC)
                  ↓
A19 text_humanizer (Stop-Slop очистка)
                  ↓
A25 compliance_gate (regex L1 → LLM L2/L3)
                  ↓
A30 higgsfield_agent (UGC / Shorts / Карусель) ── A34 caption + A35 TTS при нужде
                  ↓
A26 publer_publisher  ──или──  social_publisher (прямые API, 8 платформ)
                  ↓
Keitaro postback (UTM → конверсии)
```

`output` в запросе к пайплайну (`text`/`native`/`script` vs
`video`/`carousel`/`full`) решает, доходит ли цепочка до Higgsfield — белая
текстовая кампания не тянет за собой видеогенерацию.

**Параллельно:** A28 warmup_manager (прогрев новых аккаунтов) · A18
knowledge_synthesizer (ежедневно 21:00 + воскресенье — синтез собственных
результатов, не конкурентов, → `kb_entries`).

---

## 🆕 Что нового

### ✂️ Пересборка агентов: только генерация + безопасная доставка (июль 2026)

Полный пересмотр состава агентов — убран весь research/поисковый слой
(конкуренты, тренды, крипы), система сфокусирована на «просто генерируй
видео и доставляй безопасно». **27 → 13 агентов** (A13–A36):

- Удалены как мёртвый код: A12 `warming_state_machine`, A16 `revenue_analyst`,
  A17 `failure_recovery`.
- Удалены как избыточный поисковый слой: A20 `trend_scraper`, A22
  `ads_auditor`, A24 `obsidian_brain`, A27 `spy_analyzer`, A29
  `prelanding_generator`, A31 `competitor_analyst`, A32 `trend_radar`, A33
  `competitor_scraper`, `transcription_agent`, A15 `strategy_engine`.
- **A18 `knowledge_synthesizer` — не удалён, а починен.** Раньше писал в
  мёртвую легаси-таблицу; теперь ежедневно в 21:00 (+ воскресенье) пишет
  сводный отчёт о **собственных** результатах системы прямо в `kb_entries`
  (через `save_kb_entry()`) — оркестратор и дашборд видят новое знание сразу,
  без ручной синхронизации. `entry_key` с датой в хвосте — знания
  накапливаются, не перезаписываются.
- **A28 `warmup_manager` — переведён на Supabase.** Раньше состояние прогрева
  хранилось в локальном JSON-файле и терялось при пересборке контейнера;
  теперь всё живёт в таблице `accounts` (новые колонки —
  `deploy/10_patch_warmup_accounts.sql`), с защитой
  `shadow_banned`/`hard_banned`/`replaced`/`paused` от перезаписи чужого
  решения.
- Дашборд (`Agents.jsx`, `Launch.jsx`, `App.jsx`) и оркестраторский каталог
  приведены в соответствие — раздел «Тренды» убран целиком.

### 🧠 База знаний ×99 + UX-правила дашборда (июль 2026)

**Глубокое обучение системы** — оркестратор и агенты теперь опираются на
профессиональную базу знаний в таблице `kb_entries` (версионируемая,
`entry_key` = `process.platform.vertical.scheme`, ~**99 записей**), загружаемую
аддитивными сид-скриптами `deploy/seed_kb*.py`:

- **Блок A — партнёрки** (`seed_kb_affiliate.py`, 30): карта CPA-сетей по всем
  вертикалям (гемблинг, беттинг, нутра, финансы, товарка, крипто, дейтинг, mVAS,
  EdTech), гайды «как лить» по каждой паре платформа×вертикаль, compliance-матрица
  Meta/TikTok, воронки, бенчмарки ставок/CPA/минбюджетов.
- **Блок B — белые направления** (`seed_kb_white.py`, 16): воронки по нишам
  (строительство, туризм, авто-пригон, недвижимость, красота, фитнес, e-commerce,
  B2B), органический рост Telegram-каналов + монетизация, YouTube Shorts/Rutube.
- **Контентная часть** (`seed_kb_content.py`, 13): хуки (5 типов + окно 3 сек),
  форматы 2025, копирайтинг, стоп-слоп (маркеры AI-текста), тренды (звуки/хэштеги),
  производство через нейросети (Higgsfield/ElevenLabs/Whisper).

**Дашборд:**
- Раздел **«База знаний»** переписан на живые данные `kb_entries` с фильтрами по
  вертикали / схеме (white/grey/black) / категории; счётчик на дашборде читает
  `kb_entries`, а не легаси `knowledge_entries`.
- Раздел **«Клиенты» → «Проекты»**: CRUD (создать / переименовать / удалить)
  через меню «···»; база знаний проекта подтягивается из `kb_entries` по
  распознанной вертикали (название + категория → slug).
- **Правило UX**: все карточки-списки сворачиваются в группы через общий
  компонент `CollapsibleCard` (зафиксировано в `CLAUDE.md`).
- Все вызовы API идут через nginx :80 (без порта `:8080` — мобильные сети его
  режут); `/orchestrator/chat` вынесен в публичные роуты (`_PUBLIC_PATHS`), чат
  работает без токена за файрволом.

### 🔧 Аудит системы + починка CI и трёх скрытых багов (июль 2026)

Полный ресерч проекта (код, CI/CD, деплой, безопасность) — отчёт в
[`docs/audit-2026-07-01.md`](docs/audit-2026-07-01.md). Починено:

- **CI на main был красный**: бамп `supabase` 2.31 сломал типизацию
  `resp.data` (226 ошибок mypy в 14 файлах). Добавлен
  `ubt_os/utils/supabase_utils.py` (`rows`/`first_row`/`one_row`) —
  единая типобезопасная точка извлечения данных postgrest.
- **A14: проверка прокси молча не работала** — httpx ≥ 0.28 удалил аргумент
  `proxies`, TypeError глотался и каждый прокси считался мёртвым.
- **Higgsfield-воркер падал на каждой задаче** — `zpopmin` возвращает пары
  `(member, score)`, в `VideoJob.from_json` уходил весь кортеж.
- **Webhook-сервер** теперь отвечает `400` на битый JSON и `500` с логом при
  ошибке обработчика (раньше — обрыв соединения без ответа n8n).
- **docker-compose не пробрасывал `WEBHOOK_SECRET`/`AGENTS_API_TOKEN`** —
  контейнер agents работал в dev-режиме без аутентификации; добавлены также
  Publer/Firecrawl/Deepgram/OpenAI/`MEDIA_BUCKET`/`TTS_SERVER_URL`/CORS.
- **Dockerfile** теперь копирует `vertical_configs/` (файловый fallback
  VerticalLoader не попадал в образ).

### 📊 A36 `post_analytics_agent` — нативная аналитика по постам

Разбор конкурента ([Postiz](https://github.com/gitroomhq/postiz-app)) показал
реальный пробел: воронка конверсии и A22 `ads_auditor` работали только с
`revenue_events` (деньги) или ручным вводом — ни одной живой метрики
вовлечённости с самих площадок не было. Новый A36 синхронизирует
impressions/reach/views/likes/comments/shares/saves нативно через API
TikTok/YouTube/Instagram/Facebook/Pinterest/Threads/Twitter/LinkedIn для
каждого опубликованного поста, используя те же credentials, что и publisher.
Пишет снапшотами в `post_metrics` ([`deploy/07_patch_post_metrics.sql`](deploy/07_patch_post_metrics.sql)) —
видно рост метрик со временем, не только точку. Route `POST /analytics/sync`
или `agent: "post_analytics"` в `/agents/run`. Dashboard: раздел «Аналитика»
теперь показывает реальные таблицы по платформам и последним постам + кнопка
синхронизации. Агентов **27** (A12–A36).

### 🐛 Фикс: добавление аккаунтов Facebook/Pinterest

Дашборд позволял добавлять аккаунты facebook/pinterest, а схема `accounts` их
запрещала (CHECK), не имела колонок `proxy`/`publer_profile_id`/`account_type`
и требовала UUID вместо человекочитаемого `id` — из-за чего «Добавить аккаунт»
падал с ошибкой Supabase. Схема приведена к продукту: `id` **TEXT**, платформы
+facebook/+pinterest, недостающие колонки. Миграция существующих БД —
[`deploy/06_patch_accounts_align.sql`](deploy/06_patch_accounts_align.sql)
(в `make db-init`, идемпотентная). Проверено на реальном Postgres.

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
DEEPGRAM_API_KEY=...           # A34 word-тайминги для субтитров
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

React 18 + Vite SPA с live-данными из Supabase. Списки-справочники во всех
разделах сворачиваются в группы (общий компонент `CollapsibleCard`).

| Раздел | Что показывает |
|--------|----------------|
| **Дашборд** | приоритеты, статистика в реальном времени (знания из `kb_entries`) |
| **Проекты** | список проектов + CRUD (создать / переименовать / удалить через меню «···»), чат с оркестратором → создание заданий, база знаний проекта по вертикали |
| **Аккаунты** | TikTok/FB/IG, добавление + запуск A28 прогрева |
| **Контент** | производственный пайплайн, история публикаций |
| **Запуск агентов** | веб-интерфейс для всех агентов без кода |
| **Агенты** | инвентарь, статусы, схема пайплайна |
| **Медиа** | TTS-озвучка, авто-субтитры |
| **Аналитика** | выручка, нативные метрики постов (A36), партнёрские условия |
| **База знаний** | ~99 записей `kb_entries` с фильтрами по вертикали / схеме / категории |
| **Инфраструктура** | сервер, сервисы, Supabase |

> 🖥 Собранный SPA лежит в `dashboard-static/` (в git, раздаётся nginx на :80).
> После правок: `cd dashboard && npm run build && cp -r dist/* ../dashboard-static/`,
> затем commit `dashboard/src` + `dashboard-static/`. На сервере — просто `git pull`.

---

## 🧰 Стек

| Слой | Технология |
|------|-----------|
| AI | Claude Sonnet 5 (оркестратор) + Claude Haiku 4.5 (рутина) |
| Видео | Higgsfield AI API · Deepgram (word-тайминги для субтитров) |
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
pytest tests/ -v                            # 109 тестов   ✅ зелёные
bandit -r ubt_os/ -ll                       # безопасность ✅ 0 предупреждений
```

Конфигурация ruff и mypy — в [`pyproject.toml`](pyproject.toml). Покрытие:
аутентификация (dual-auth), compliance-regex (L1), парсинг JSON из LLM,
circuit breaker, логирование, vault-path, warmup manager (A28, Supabase
state), knowledge synthesizer (A18, `kb_entries`), caption, TTS, post
analytics.

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
│   ├── agents/              # A13–A36, 13 агентов — генерация + доставка, без research
│   ├── core/                # circuit breaker, budget guard, pipeline lock, risk engine, kb_writer
│   ├── pipelines/           # Higgsfield queue/worker, DLQ, social_publisher
│   ├── utils/               # attribution, Obsidian git sync, LLM utils
│   └── main.py              # HTTP-сервер :8080, webhook от n8n, dual-auth
│
├── dashboard/               # React 18 + Vite SPA (src/components/CollapsibleCard.jsx)
├── dashboard-static/        # собранный SPA (в git, раздаётся nginx)
├── vertical_configs/        # 1win.yaml, dr_cash.yaml, sample_configs.yaml
├── .claude/skills/          # Claude Code скиллы (/publer, /prelanding, /higgsfield …)
├── obsidian-vault/          # База знаний (wiki-страницы)
├── deploy/                  # Dockerfile, SQL-схемы, nginx, LiteLLM config
│   ├── seed_kb*.py          # сиды kb_entries (base + affiliate + white + content)
│   └── 10_patch_warmup_accounts.sql # A28 инфра-колонки на accounts
├── n8n/workflows/           # воркфлоу (JSON)
├── docs/                    # аудиты и отчёты ресерча
├── tests/                   # pytest (109 тестов)
├── .env.template            # шаблон переменных окружения
├── pyproject.toml           # конфиг ruff + mypy
└── CLAUDE.md                # гайд для AI-ассистентов + UI-правила
```

---

<div align="center">

<br/>

**UBT OS** — *built with [Claude Code](https://claude.com/claude-code)*

*User is always the final decision-maker. Nothing executes without explicit approval.*

</div>
