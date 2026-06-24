# CLAUDE.md — UBT OS

Этот файл — контекст проекта для Claude Code. Читается автоматически в начале каждой сессии в этой директории. Держать в актуальном состоянии: при изменении архитектуры/стека — обновлять этот файл, а не только Obsidian.

## О проекте

UBT OS — мультиагентная AI-система для генерации органического (UBT) трафика на партнёрские программы в двух вертикалях:
- **Betting**: 1win, Mostbet, Melbet, Pin-Up (RU/KZ)
- **Nutra**: Dr.Cash, 2500+ офферов, COD-модель (PL, RO, MX, BR, IN)

Параллельно UBT OS работает как **white-label агентство** на CPA-модели (без фикс-оплаты) для двух клиентов: корейский авто-импорт и тур-агентство.

**Монетизация:** 1win (RevShare до 60%, CPA до $250, cookie 365 дней), Mostbet (RevShare до 60%), Dr.Cash ($25–100 CPA COD, выплаты 2×/нед).

**Позиционирование:** Claude + Higgsfield MCP + direction-based workflow — нет у конкурентов (GeeLark, Conbersa, NoimosAI).

## Кто принимает решения

Сергей — единственный decision-maker. **Ничего не имплементируется без явного одобрения.** Работа блок за блоком: предлагаешь план → ждёшь approve → делаешь → следующий блок. Не расширять scope самостоятельно.

## Workflow Claude Code

### Режим планирования — обязателен, approval — не пропускается
- Для ЛЮБОЙ нетривиальной задачи (3+ шагов или архитектурное решение) сначала пиши план в `tasks/todo.md` с чекбоксами — никакого кода до этого.
- **Показывай план Сергею и жди явный approve, прежде чем начинать реализацию.** Это жёстче дефолтного plan mode Claude Code: здесь approve обязателен даже на простых задачах, если они меняют что-то на сервере/в БД/в проде.
- Если на исполнении что-то пошло не так (тест упал, лог показал не то) — СТОП, не чини на лету молча. Покажи, что увидел, предложи скорректированный план, жди реакции — особенно если фикс выходит за рамки утверждённого блока.
- Пиши детальные спеки заранее, убирай неоднозначность до старта, а не по ходу.

### Баг-репорты — диагностика автономна, фикс — под approve
- На баг-репорт: ищи root cause автономно (логи, трейсы, упавшие тесты) без переспрашивания «как чинить» — это не требует одобрения, это просто работа.
- Но **сам факт исправления — отдельный шаг с approve**, если патч трогает прод/БД/конфиги на FirstVDS. Формат: «нашёл причину → вот план фикса → жду ОК → применяю». Автономная починка без подтверждения допустима только для чисто локальных правок (например, синтаксис в файле, который ещё не задеплоен).
- После фикса — заносить в `tasks/lessons.md` (см. ниже), не только в этот файл.

### Субагенты
- Используй субагентов щедро для ресёрча, разведки, параллельного анализа — держи основной контекст чистым.
- Одна задача на одного субагента, для сложных задач — больше compute через параллельные субагенты.
- Subagent summary-only return rule: субагенты возвращают только сводку, не полный контекст — экономия токенов.

### Верификация до «готово»
- Никогда не помечай задачу завершённой без доказательства, что она работает: запусти тест, покажи лог, сравни поведение до/после патча.
- Вопрос перед сдачей: «одобрил бы это staff-инженер?» — если нет, не сдавай.

### Элегантность (в меру)
- На нетривиальных изменениях — пауза с вопросом «есть путь элегантнее?». Если фикс похож на костыль — переделай по-человечески.
- Для простых очевидных фиксов (одна строка, явная причина) — не оверинжинирь, это правило не для них.

### Цикл самоулучшения — `tasks/lessons.md`
- После любой правки, тем более если она исправляет повторяющийся класс ошибки — фиксируй паттерн в `tasks/lessons.md`: что случилось, почему, как не повторить.
- Перечитывать `tasks/lessons.md` в начале новой сессии по проекту — обязательно, до того как трогать код.

### Управление задачами
1. План → `tasks/todo.md` с чекбоксами
2. Approve у Сергея до старта реализации
3. Отмечать пункты по ходу выполнения
4. Краткое резюме на каждом шаге, не молча
5. Секция ревью в `tasks/todo.md` после завершения блока
6. Урок → `tasks/lessons.md`

### Базовые принципы
- Простота в приоритете — минимальное воздействие на код, без лишних абстракций.
- Без лени — искать корневую причину, не ставить временные фиксы.
- Минимальное воздействие — трогать только необходимое, без сайд-эффектов.

## Удалённый сервер

- Алиас: `ssh ubt-vds` — passwordless, ключ настроен в `~/.ssh/` среды, где запущен Claude Code (WSL).
- Все live-проверки (статус systemd, логи, состояние n8n, Supabase) — через `ssh ubt-vds "команда"`.
- Деплой изменений: закоммитить локально → `git push` → `ssh ubt-vds "cd /путь/до/ubt-os && git pull && systemctl restart ubt-agents"`.
- Это прод. Команды на чтение (логи, `systemctl status`, `ls`, `journalctl`) — можно без approve, это диагностика. Любое действие, которое МЕНЯЕТ состояние сервера (restart сервиса, миграция БД, запись/правка файла на сервере, изменение конфигов) — отдельный шаг с approve, как остальные правила Workflow выше.
- Хост за алиасом: `88.218.121.108` (`svovkcpa.fvds.ru`).

## Архитектура агентов

**UBT OS core (14):** ORCHESTRATOR, RESEARCH, TREND_HUNTER, FUNNEL_BUILDER, CONTENT_CREATOR, DESIGN_DIRECTOR, VIDEO_DIRECTOR, HIGGSFIELD_AGENT, SEO, SOCIAL_PLATFORM, PUBLISHING, ANALYTICS, OPTIMIZER, KNOWLEDGE_BASE

**v2 добавления (5):** A15 COMPETITOR_ANALYST, Risk Engine, Creative Vault, +2

**NUTRA.AUTO (7):** СТРАТЕГ, СЦЕНАРИСТ, РЕЖИССЁР, ДИКТОР, МОНТАЖЁР, ДИСТРИБЬЮТОР, АНАЛИТИК — цикл ~5 мин/видео

**Telegram-модуль (4, Phase 7, не начат):** T1-ACCOUNT_MANAGER, T2-WARMER, T3-COMMENTER, T4-REACTOR

**LiteLLM routing:** Sonnet 4.6 → тяжёлые агенты (Orchestrator, Research, Content, Optimizer); Haiku 4.5 → лёгкие (SEO, Publishing, Analytics, Knowledge Base). Экономия ~60–80% на API.

## Технический стек

| Слой | Технология |
|---|---|
| AI/LLM | Claude API (Sonnet 4.6 / Haiku 4.5) через LiteLLM Router (self-hosted) |
| Видео | Higgsfield.ai MCP (`mcp.higgsfield.ai/mcp`), ElevenLabs, Remotion + FFmpeg, short-video-maker (Docker) |
| Автоматизация | n8n (self-hosted), Blotato API ($97/мес) |
| Публикация | TikTokAutoUploader (Playwright, native upload), Blotato |
| Данные | Supabase + PostgreSQL + Redis |
| Anti-detect | GoLogin + residential proxies (3 уровня изоляции: device + network + behavior) |
| Трекинг | Keitaro (UTM + postback), TGStat |
| Knowledge base | Obsidian vault (PARA, 24 файла, hourly sync через obsidian-sync) |
| Dashboard | Next.js 14 + Vercel |
| Инфраструктура | FirstVDS Amsterdam (8 CPU / 12 GB RAM / NVMe, Ubuntu 22.04) — EU датацентр обязателен из-за гео-ограничений Claude/OpenAI API на российские IP |
| SSH | Termius (мобильный/desktop), плюс прямой алиас `ubt-vds` из WSL для Claude Code |

**GitHub репозитории:** `gyoridavid/short-video-maker`, `haziq-exe/TikTokAutoUploader`, `OSideMedia/higgsfield-ai-prompt-skill`, `babi0jon/shorts-automation-bot`, `Hikhakk/higgsfield-mcp-unified`, `LonamiWebs/Telethon`, `pyrogram/pyrogram`

**Этот репозиторий:** `github.com/SPRO100/ubt-os` (private)
**Cloud:** Supabase (`ricuoztdelapexfpqsux`), Upstash Redis (`becoming-narwhal-117304.upstash.io`), FirstVDS IP `88.218.121.108`

## Текущее состояние (Sprint 1 — задеплоен и пропатчен)

Стек запущен на FirstVDS: n8n (порт 5678), LiteLLM через systemd, `ubt-agents` systemd-сервис (`python -m ubt_os.main`). Все 7 SQL-схем применены в Supabase. Все 6 n8n-воркфлоу импортированы и опубликованы: `obsidian-sync`, `account-checker`, `health-monitor`, `knowledge-synthesizer`, `risk-engine-monitor`, `strategy-engine-weekly`. Telegram-бот настроен на алерты health-monitor.

**Архив:** `ubt-os-FULL-sprint1-fixed.zip` (167 файлов) + `CHANGELOG-sprint1-applied.md`

## Sprint 2 — согласован, код не написан

Порядок реализации:
1. **Compliance Gate** — проверка бан-слов/медицинских claims по GEO, на Haiku
2. **Warmup Automation** — расширение логики T2-WARMER на все платформы, Redis state machine для Days 1–8+
3. **Keitaro UTM + `revenue_events` интеграция**
4. **Higgsfield Queue** — Redis rate-limit очередь для генерации видео
5. **Cross-platform Repurposing** — Higgsfield reframe/outpaint вместо генерации с нуля под каждую платформу

**Video uniqualization module** — на холде до первого успешного запуска пайплайна. Спека сохранена в Obsidian (`status/on-hold`). Ключевая деталь: 4–6 одновременных FFmpeg-трансформов нужны для обхода pHash-детекции платформ (crop/zoom, цветокоррекция, speed shift ±3–5%, audio pitch shift, grain overlay, subtitle offset).

**Phase 7 — Telegram-модуль** (план, не начат): T1–T4 на Telethon + Pyrogram + Redis. Без парсер-компонента. Max 3–5 комментариев/день/аккаунт для T3-COMMENTER.

## Кандидаты на внедрение (готовые open-source решения вместо написания с нуля)

Из исследования каналов/конкурентов (20–23 июня), приоритет и порядок — за Сергеем, ничего не внедрять без approve:

1. **Postiz** (`github.com/gitroomhq/postiz-app`) — self-hosted паблишер, поддержка VK+Telegram, готовая n8n-нода и MCP-сервер. Заменяет/дополняет Blotato в PUBLISHING-агенте — экономия $97/мес.
2. **AgentOps** (`github.com/AgentOps-AI/agentops`) — open-source трейсинг вызовов агентов, latency, costs. Вешается на LiteLLM Router — закрывает слепую зону мониторинга расходов Sonnet/Haiku.
3. **Agent-Reach** (open-source, ~10k★) — соц-листенинг/трекинг конкурентов (Twitter/Reddit/YouTube/GitHub) без платных API. Питает TREND_HUNTER и A15 COMPETITOR_ANALYST взамен ручного парсинга.
4. **Атрибуция продажи к посту** (доработка, не новый инструмент) — расширить Keitaro-схему: `sub_id` на уровне `post_id`, а не только `campaign_id`. Правки в FUNNEL_BUILDER/ANALYTICS.
5. **Почасовая реаллокация приоритета публикаций** (доработка, не новый инструмент) — n8n cron раз в час сравнивает ER/конверсию связок и сдвигает приоритет публикаций. Правки в OPTIMIZER.

AliExpress-импорт (по аналогии с Afflow) — намеренно не нужен, пропущен.

Сырьё для дальнейшей обработки (требует объединения в финальный SOP, статус `pending-merge`): материалы по УБТ-трафику как термину арбитража, подборка ~53 AI-инструментов из канала «PRO трафик», пост с postback-конфигами Keitaro/Cpatify/Leadbit + COD-интеграция. Файлы лежат в Obsidian `00 Inbox`.

## Ключевые правила и грабли

### Инфраструктура
- LiteLLM запускать через pip (`litellm[proxy]==1.40.14` — именно эта версия), не Docker — новые версии требуют Prisma DB; Docker-конфиг перетирается встроенными Azure/GPT дефолтами
- Всегда `python -m ubt_os.main` (module invocation), не прямой запуск скрипта — критично для package imports
- n8n блокирует доступ к env-переменным в expressions — хардкодить IP сервера в webhook URL вместо `$env.AGENTS_WEBHOOK`
- `N8N_SECURE_COOKIE=false` обязателен для HTTP-доступа к n8n

### Платформенные алгоритмы
- **TikTok:** completion rate >70% триггерит boost; native upload (Playwright) >> API upload по охвату; 3-уровневая изоляция аккаунтов обязательна
- **YouTube Shorts:** replay count — ключевая метрика; SEO работает на долгий lifespan видео; алгоритм мягче TikTok
- **Instagram:** Saves >3% от просмотров — ключевой сигнал; после хита следующий пост получает boost; Trial Reels для тестирования аудитории
- **Telegram:** 100% реальный охват подписчиков, Open Rate 30–60% против 1–5% соцсетей — лучшая конверсия; роль — прогрев аудитории с TikTok/YouTube

### Прогрев аккаунтов (Days 1–8+)
- Дни 1–3: только просмотры/лайки, ноль постов
- Дни 4–5: 2 нейтральных видео, без CTA
- Дни 6–7: 2 нишевых видео, без ссылок
- День 8+: начало монетизации
- **Пропуск прогрева = shadow ban на первом CTA-посте**

### Контент-правила
- **Nutra:** не упоминать продукт в первые 15 сек, нативный стиль, мягкий CTA. Топ-форматы: transformation story, doctor revelation, antagonist («эти 3 продукта УБИВАЮТ суставы»), before/after
- **Betting:** нативный стиль, без прямой рекламы букмекера, CTA = «промокод в профиле». Топ-форматы: угадай счёт, голевой момент (момент гола = первый кадр), история выигрыша, ежедневный прогноз

### Higgsfield / MCSLA
- Формула: Model (Seedance 2.0 / Kling 3.0 / Sora 2 / Veo 3.1) · Camera · Subject · Look · Action
- Всегда три отдельных блока: IMAGE + IDENTITY + MOTION — никогда не смешивать

### Публикационный график
TikTok 08/12/19, YouTube 09/14/20, Instagram 09/13/20, Telegram 10/15/21/23

### Account checker
Пороги: ER <2% = алерт; ER <1% = стоп + ротация proxy. Проверка каждые 6ч: валидность, shadow ban, ER, видимость хэштегов, новые подписчики, ping proxy.

## Финансовые прогнозы (high-level)
NUTRA: M3 ~$12K, M6 ~$45K. UBT OS: M3 ~$10K, M6 ~$54K. Combined M6 ~$99K.
Инфраструктура: MVP старт ~$145/мес, полный стек ~$383/мес.

## Подход к работе

- **Block-by-block + approve-gate:** детали — см. раздел «Workflow Claude Code» выше. Без автономного расширения scope.
- **Patch-first:** баги фиксятся точечными патчами прямо на сервере, не полным рерайтом — но применение патча на проде проходит через approve (см. Workflow).
- **Obsidian как system memory:** vault — единственный источник правды по SOP, архитектурным решениям, спекам агентов. Новые ресурсные файлы → `50 Resources/SOPs`; YAML frontmatter с `type`, `status`, `project` (wikilink), `tags`, `created`, `updated`. Wikilinks — точные имена файлов.

## Git-конвенции

- Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- Первая строка коммита < 50 символов
- Без AI-attribution в commit message
- Перед коммитом — прогон через тестовое окружение, если есть тесты

## Требуемые API-ключи для запуска

Anthropic, Supabase, 1win Partners, Dr.Cash, Railway, Higgsfield.ai, ElevenLabs, Blotato, Keitaro, GoLogin, Telegram API (`api_id` + `api_hash` с my.telegram.org), GitHub (для obsidian-sync)

## Obsidian vault

24 файла, точка входа: `MOC — Мастер Проект.md`. Структура: MOC, Архитектура Агентов, Стек Инструментов, LiteLLM Роутер, Выбор Вертикали, УБТ Стратегия, Партнёрки и Офферы, Видео Пайплайн, Промпты-библиотека, Форматы Контента, Аккаунты и Чекер, Методы и Скиллы, Финансовые Модели, Дорожная Карта, GitHub Инструменты, Higgsfield-Интеграция, Анализ Рынка, Мастер Ресурс-Скиллы, Платформы-Алгоритмы + доп. файлы.

---

**При обновлении архитектуры, стека или правил — обновлять этот файл. Он заменяет необходимость пересказывать контекст проекта в начале каждой сессии.**
