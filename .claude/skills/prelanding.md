---
description: Генерация HTML прелендинг-страниц через A29 PrelandingGenerator. Форматы: quiz, story, native_article, vsl. Мультиязычность, COD/Trial/SS, Compliance Gate встроен.
---

# Claude Skill — Prelanding Generator (A29)

Генерирует готовые HTML прелендинг-страницы для affiliate-воронок.
Работает в паре с A29 prelanding_generator.py и A25 compliance_gate.py.
Выход подключается между A26 Publer (трафик) и лендингом партнёра.

---

## Команды

`/prelanding generate <оффер> <vertical> <geo> <формат>` — сгенерировать одну страницу
`/prelanding variants <оффер> <vertical> <geo>` — 2–3 варианта разных форматов
`/prelanding quiz <оффер>` — квиз-воронка (5–7 вопросов)
`/prelanding story <оффер>` — история от первого лица (нативная статья)
`/prelanding vsl <оффер>` — видео-сейл пейдж с плейсхолдером VSL

---

## Форматы страниц

| Формат | Конверсия | Вертикаль | Описание |
|--------|-----------|-----------|---------|
| `story` | 3–6% | Nutra | История пользователя, 400–600 слов. Работает для COD. |
| `native_article` | 2–4% | Nutra / Betting | Новостная стилистика. "Врачи выяснили…" |
| `quiz` | 5–9% | Nutra | 5–7 вопросов, персонализация → вовлечение |
| `vsl` | 4–8% | Betting / Nutra | Видеоплеер + текст ниже, urgency таймер |

---

## Билинговые модели

| Модель | CTA | Когда использовать |
|--------|-----|-------------------|
| `COD` | "Заказать за 0 сейчас" | Nutra без предоплаты, TR/MX/BR |
| `Trial` | "Попробовать 14 дней" | Подписочные нутра-офферы, US/DE |
| `SS` | "Купить за $X" | Прямые продажи, белые офферы |

---

## Пайплайн

```
A27 spy_analyzer → A21 content_creator
    ↓
A29 prelanding_generator (HTML страница)
    ↓
A25 compliance_gate (проверка клеймов)
    ↓
A26 publer_publisher (трафик с TikTok/FB/IG → прелендинг → лендинг партнёра)
    ↓
Keitaro postback (трекинг: preland_view + click + conversion)
```

---

## GEO и языки

| GEO | Язык | Особенности |
|-----|------|-------------|
| US | English | Trial/SS, мягкие клеймы |
| BR | Portuguese | COD, тёплый доверительный тон |
| MX | Spanish | COD, "historia real" формат |
| DE | German | Факты и исследования, избегай суперлативов |
| PL | Polish | COD, локальные референсы |

---

## Примеры использования

```
/prelanding generate BloodSugarX nutra US story
/prelanding variants KetoPro nutra BR
/prelanding quiz SlimFast nutra MX
```

## Переменные окружения

```bash
ANTHROPIC_API_KEY=your_key    # Обязателен (генерация через Claude Haiku)
```

## Compliance встроен

Все страницы проходят A25 compliance_gate автоматически:
- Запрещены: "лечит", "гарантирует выздоровление", "клинически доказано" (без ссылок)
- Разрешены мягкие клеймы: "помогает поддерживать", "способствует", "пользователи отмечают"
