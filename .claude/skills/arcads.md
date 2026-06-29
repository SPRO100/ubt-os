---
description: Генерирует AI видео-рекламу через Sora, Veo, Kling, GPT Image. Дополняет Higgsfield.ai в пайплайне UBT OS.
---

# Arcads — AI Видео-реклама

Создание видео-крео для betting/nutra без актёров и съёмок.
Используй рядом с Higgsfield.ai для A/B тестирования форматов.

## Доступные стили

| Скилл | Что создаёт | Лучше для |
|---|---|---|
| `arcads-api` | UGC-видео с AI-аватаром | Nutra отзывы, обзоры |
| `chatgpt-image-ad` | Статические баннеры | Betting бонусы, nutra CTA |
| `pixar-style` | Анимация Pixar-стиль | Lifestyle nutra контент |
| `claymation` | Пластилиновая анимация | Вирусный / мемный контент |
| `thumbnail` | YouTube превью | SEO видео |
| `meta-ad-builder` | Готово к публикации в Meta | Платный трафик |
| `caption-video` | Добавить субтитры | Все форматы |
| `image-clone` | Скопировать стиль крео конкурента | Быстрый старт |

## Команды

`/arcads ugc <скрипт> <аватар>` — UGC видео с AI-актёром
`/arcads banner <оффер> <гео>` — статический баннер
`/arcads clone <url-крео>` — клонировать стиль
`/arcads caption <видео>` — добавить субтитры
`/arcads thumbnail <тема>` — YouTube превью

## Промпт-библиотека (37 шаблонов)

Категории встроенных промптов:
- **Problem/Solution** — боль → продукт → результат
- **Testimonial** — от лица пользователя
- **Before/After** — трансформация
- **Lifestyle** — lifestyle интеграция продукта
- **Urgency** — ограниченное предложение / бонус

## A/B связка с Higgsfield

```
Higgsfield.ai → кинематографичное видео (premium)
Arcads → UGC/реальный стиль (высокое доверие)
Тестировать: 70% Higgsfield / 30% Arcads → оптимизировать по CR
```

## Настройка

```bash
ARCADS_API_KEY=your_key  # arcads.ai
```

Продакшн-пайплайн: `ubt_os/pipelines/arcads_queue.py` (создать по образцу `higgsfield_queue.py`)

## Соответствие форматам UBT OS

- `before_after_testimonial` → Arcads UGC + before/after промпт
- `ugc_reaction` → Arcads testimonial стиль
- `short_hook_problem_solution` → Arcads problem/solution шаблон
