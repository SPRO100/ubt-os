---
description: 25 SEO sub-skills для organic трафика. Аудит, контент, schema, hreflang (US/BR/MX/DE/PL), программатик SEO, интеграция GSC/GA4.
---

# Claude SEO — Полный SEO инструментарий

Основан на claude-seo (AgriciDaniel/claude-seo, 10.1k ⭐).
25 специализированных команд. До 15 параллельных агентов.
Применяется к вертикалям **betting / nutra**, GEO: **US, BR, MX, DE, PL**.

---

## Аудит и стратегия

`/seo audit <url>` — полный аудит сайта (параллельно 6 агентов)
`/seo technical <url>` — технический SEO (Core Web Vitals: LCP, INP, CLS)
`/seo content <url>` — E-E-A-T и качество контента
`/seo plan <вертикаль> <гео>` — стратегический SEO-план

## Контент и Schema

`/seo content-brief <ключ> <гео>` — бриф статьи с LSI и internal links
`/seo schema <тип>` — JSON-LD разметка (Article, Product, FAQ, Review)
`/seo page <url>` — глубокий анализ одной страницы
`/seo cluster <seed-ключ>` — семантический кластер из SERP
`/seo sxo <url>` — Search Experience Optimization

## AI Search и Performance

`/seo geo <вертикаль> <гео>` — AI Overviews / GEO оптимизация
`/seo images <url>` — оптимизация изображений
`/seo sitemap <домен>` — XML sitemap + отраслевые шаблоны

## Международное SEO (критично для UBT OS)

`/seo hreflang <домен>` — аудит и генерация hreflang для US/BR/MX/DE/PL
`/seo local <гео>` — локальный SEO (Google Business Profile, NAP)
`/seo maps <гео>` — геогрид ранжирования, аудит конкурентов

## Конкурентная разведка

`/seo backlinks <домен>` — профиль ссылок (Moz, Bing, Common Crawl)
`/seo competitor-pages <url1> <url2>` — сравнение страниц конкурентов
`/seo drift <домен>` — мониторинг SEO-регрессий (SQLite снимки)

## Google интеграция

`/seo google <домен>` — PageSpeed + CrUX + GSC + GA4 + Indexing API
`/seo programmatic <шаблон> <csv-ключей>` — программатик SEO страницы

## E-commerce (нутра лендинги)

`/seo ecommerce <url>` — marketplace intelligence, schema для продуктов
- Product schema (цена, наличие, рейтинг, отзывы)
- Merchant return policies
- Energy efficiency labels (EU)

---

## Конфигурация для UBT OS

Задать один раз в начале сессии:
```
Вертикаль: nutra | betting
GEO: US | BR | MX | DE | PL
Язык: EN | PT | ES | DE | PL
Домен: [твой домен]
Конкуренты: [список 3-5 конкурентов]
```

## Compliance — запрещено для SEO

Nutra: медицинские диагнозы, гарантии похудения за точный срок
Betting: гарантии выигрыша, "беспроигрышные системы"
Оба: имена конкурентов как основные ключи (trademark)

## Связь с агентами UBT OS

`/seo content-brief` → A21 content_creator (передать бриф)
`/seo competitor-pages` → A20 trend_scraper (дополнить анализ)
`/seo drift` → A18 knowledge_synthesizer (логировать регрессии)
`/seo hreflang` → vertical_configs (обновить GEO настройки)
