---
description: Keitaro трекинг-ссылки и UTM-параметры для affiliate-кампаний betting/nutra.
---

# Claude Skill — Keitaro Tracker

Генерирует правильные трекинг-ссылки и UTM-структуру для Keitaro.
Применяется к вертикалям **betting / nutra**, GEO: **US, BR, MX, DE, PL**.

---

## Команды

`/keitaro link <оффер> <платформа> <geo>` — создать трекинг-ссылку
`/keitaro utm <base-url> <кампания>` — добавить UTM-параметры
`/keitaro campaign <вертикаль> <geo>` — структура кампании в Keitaro
`/keitaro flows <оффер>` — воронки для разных источников трафика
`/keitaro postback <партнёрка>` — настройка postback для партнёрки

---

## UTM структура UBT OS

```
utm_source={platform}       → tiktok | instagram | youtube | telegram
utm_medium=organic          → всегда organic (не платный)
utm_campaign={vertical}_{geo}  → nutra_US | betting_BR
utm_content=ubt_os          → идентификатор системы
utm_term={agent_id}         → a21 | a23 (какой агент создал контент)
```

### Пример для 1win (betting, BR):
```
https://1win.com/promo/br?
  utm_source=tiktok&
  utm_medium=organic&
  utm_campaign=betting_BR&
  utm_content=ubt_os&
  utm_term=a21
```

## Структура кампании в Keitaro

```
/keitaro campaign betting US
```

Создаёт структуру:
```
Campaign: betting_US_tiktok_organic
├── Flow 1: US Traffic → LP → Offer (1win)
│   ├── Filter: GEO = US
│   ├── Landing: /lp/betting-us-en/
│   └── Offer: 1win CPA $250
├── Flow 2: Bot Filter → Block
└── Flow 3: Other GEO → Default offer
```

## Партнёрские программы — postback URL

| Программа | Postback событие | Cookie |
|-----------|-----------------|--------|
| 1win | registration + deposit | 365 дней |
| Dr.Cash | lead (COD) | 30 дней |
| Mostbet | first_deposit | — |

```
/keitaro postback 1win
```
Генерирует: `https://keitaro.yourdomain.com/postback?status=lead&clickid={click_id}&payout={payout}`

## Интеграция с A26 (PubelerPublisher)

A26 автоматически добавляет базовый UTM через `_build_utm()`.
Для расширенного трекинга используй:
```python
from ubt_os.agents.publer_publisher import _build_utm
url = _build_utm(base_url, vertical="betting", geo="US", platform="tiktok")
```

## Compliance — UTM для рекламы

Nutra US: не использовать слова "weight loss" в utm_campaign (Facebook правило)
Betting: некоторые партнёрки требуют sub_id вместо utm_term
