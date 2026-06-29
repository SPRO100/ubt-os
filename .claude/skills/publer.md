---
description: Управление публикациями через Publer API ($12/мес). TikTok, Facebook Pages, Instagram. Расписание, мультиплатформенность, аналитика постов.
---

# Claude Skill — Publer Publisher

Управляет публикацией контента через Publer ($12/мес).
Работает в паре с A26 publer_publisher.py и A25 compliance_gate.py.
Publer уже прошёл TikTok Content Posting API audit — посты публикуются публично.

---

## Команды

`/publer schedule <платформа> <текст> <время>` — запланировать пост
`/publer batch <платформа> <csv-файл>` — массовая публикация из CSV
`/publer calendar <вертикаль> <geo>` — контент-календарь на месяц
`/publer status <post-id>` — статус публикации
`/publer analytics <платформа>` — аналитика по постам за 7/30 дней

---

## Поддерживаемые платформы

| Платформа | API | Ограничения |
|-----------|-----|-------------|
| TikTok | Publer (прошёл audit) | Публичные посты ✅ |
| Facebook Pages | Meta Graph API (бесплатно) | Нужна верифицированная Page |
| Instagram | Meta Graph API | Business/Creator аккаунт |

---

## Расписание публикаций по GEO

| GEO | Timezone | Лучшее время (TikTok) | Лучшее время (Facebook) |
|-----|----------|----------------------|-------------------------|
| US  | ET (UTC-5) | 07:00, 12:00, 19:00 | 09:00, 13:00, 20:00 |
| BR  | BRT (UTC-3) | 08:00, 13:00, 21:00 | 10:00, 14:00, 21:00 |
| MX  | CST (UTC-6) | 07:00, 14:00, 20:00 | 09:00, 13:00, 19:00 |
| DE  | CET (UTC+1) | 06:00, 12:00, 18:00 | 08:00, 12:00, 18:00 |
| PL  | CET (UTC+1) | 07:00, 13:00, 20:00 | 09:00, 13:00, 19:00 |

## Пайплайн публикации UBT OS

```
A27 spy_analyzer (PiPiAds/AdHeart крипы)
    ↓
A21 content_creator (генерация контента)
    ↓
A19 text_humanizer (Stop-Slop очистка)
    ↓
A25 compliance_gate (проверка клеймов)
    ↓
A29 prelanding_generator (HTML прелендинг для воронки)
    ↓
A26 publer_publisher (публикация → TikTok / Facebook / Instagram)
    ↓
Keitaro postback (трекинг конверсий)
```

## Структура CSV для массовой публикации

```csv
platform,text,schedule_time,affiliate_url,media_url
tiktok,"Caption здесь...",2026-07-01T19:00:00Z,https://1win.com/...,https://cdn.../video.mp4
facebook,"Caption здесь...",2026-07-01T13:00:00Z,https://dr.cash/...,
instagram,"Caption здесь...",2026-07-01T14:00:00Z,https://dr.cash/...,https://cdn.../reel.mp4
```

## Dry Run режим

Всегда тестируй через dry_run=True перед реальной публикацией:
```python
# В дашборде кнопка A26 по умолчанию = dry_run
# Чтобы опубликовать реально — убери dry_run из запроса или установи false
```

## Частота публикаций

Рекомендации UBT OS (антибан):
- TikTok: 1–2 поста/день в первую неделю, до 3/день после прогрева
- Facebook: 1–2 поста/день; Stories + Reels для охвата
- Instagram: 1 Reel/день + 3–5 Stories

Между постами минимум 4 часа (HumanJitter A13).

## Переменные окружения

```bash
PUBLER_API_KEY=your_key                        # Обязателен для реальной публикации
PUBLER_TIKTOK_PROFILE_IDS=id1,id2             # ID профилей TikTok
PUBLER_FACEBOOK_PROFILE_IDS=id1,id2           # ID профилей Facebook Pages
PUBLER_INSTAGRAM_PROFILE_IDS=id1,id2          # ID профилей Instagram
```

Как получить profile_ids: войди в Publer → Accounts → скопируй ID каждого подключённого аккаунта.
