---
description: Управление публикациями через Blotato API. Расписание, мультиплатформенность, аналитика постов.
---

# Claude Skill — Blotato Publisher

Управляет публикацией контента через Blotato.
Работает в паре с A26 blotato_publisher.py и A25 compliance_gate.py.

---

## Команды

`/blotato schedule <платформа> <текст> <время>` — запланировать пост
`/blotato batch <платформа> <csv-файл>` — массовая публикация из CSV
`/blotato calendar <вертикаль> <geo>` — контент-календарь на месяц
`/blotato status <post-id>` — статус публикации
`/blotato analytics <платформа>` — аналитика по постам за 7/30 дней

---

## Расписание публикаций по GEO

| GEO | Timezone | Лучшее время (TikTok) | Лучшее время (IG) |
|-----|----------|----------------------|-------------------|
| US  | ET (UTC-5) | 07:00, 12:00, 19:00 | 11:00, 14:00 |
| BR  | BRT (UTC-3) | 08:00, 13:00, 21:00 | 12:00, 18:00 |
| MX  | CST (UTC-6) | 07:00, 14:00, 20:00 | 12:00, 17:00 |
| DE  | CET (UTC+1) | 06:00, 12:00, 18:00 | 11:00, 15:00 |
| PL  | CET (UTC+1) | 07:00, 13:00, 20:00 | 12:00, 17:00 |

## Пайплайн публикации UBT OS

```
A21 content_creator
    ↓
A19 text_humanizer (Stop-Slop)
    ↓
A25 compliance_gate (проверка)
    ↓
A26 blotato_publisher (публикация)
    ↓
Keitaro postback (трекинг конверсий)
```

## Структура CSV для массовой публикации

```csv
platform,text,schedule_time,affiliate_url,media_url
tiktok,"Caption здесь...",2026-07-01T19:00:00Z,https://1win.com/...,https://cdn.../video.mp4
instagram,"Caption здесь...",2026-07-01T14:00:00Z,https://dr.cash/...,https://cdn.../reel.mp4
```

## Dry Run режим

Всегда тестируй через dry_run=True перед реальной публикацией:
```python
# В дашборде кнопка A26 по умолчанию = dry_run
# Чтобы опубликовать реально — убери dry_run из запроса
```

## Частота публикаций

Рекомендации UBT OS (антибан):
- TikTok: 1–2 поста/день в первую неделю, до 3/день после прогрева
- Instagram: 1 Reel/день + 3–5 Stories
- YouTube: 1 Short/день

Между постами минимум 4 часа (HumanJitter A13).

## Переменные окружения

```bash
BLOTATO_API_KEY=your_key     # Обязателен для реальной публикации
BLOTATO_API_URL=https://api.blotato.com/v1  # По умолчанию
```
