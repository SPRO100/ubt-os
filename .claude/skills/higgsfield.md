---
description: Видеогенерация через Higgsfield.ai MCP. UGC-реклама, анимация, motion control для nutra/betting.
---

# Claude Skill — Higgsfield Video

Основан на Higgsfield.ai MCP (встроен в среду).
Создаёт видео для TikTok/IG Reels/YouTube Shorts.

---

## Команды

`/higgsfield ugc <скрипт> <вертикаль> <geo>` — UGC-видео по скрипту
`/higgsfield short <тема> <вертикаль>` — Short-form видео 15–60 сек
`/higgsfield ab <концепт>` — 3 A/B варианта видео под сплит-тест
`/higgsfield motion <описание>` — анимация/motion control
`/higgsfield repurpose <url>` — адаптация существующего контента
`/higgsfield audit <промпт>` — предсказание виральности перед генерацией

---

## UGC формат для nutra (US)

```
/higgsfield ugc "Person looks in mirror, surprised reaction, 
before/after transformation, holds product up to camera" nutra US
```

Стиль: натуральная съёмка (не студия), естественное освещение,
нет логотипов, лицо не показывается полностью (анонимность UGC)

## Short-form структура (0–60 сек)

- 0–3 сек: Pattern interrupt (шок/цифра/обещание)
- 3–15 сек: Проблема + агитация
- 15–45 сек: Решение / трансформация
- 45–60 сек: CTA

## A/B сплит-тест

```
/higgsfield ab "weight loss transformation"
```

Генерирует 3 варианта:
- A: Emotion hook (лицо с реакцией)
- B: Result hook (до/после фото)
- C: Number hook (цифры на экране)

Тест на 48ч → победитель получает больший бюджет

## Compliance для видео

Nutra: не показывать весы, медицинские приборы
Betting: не показывать деньги крупным планом, не обещать выигрыш
Оба: Age-gate disclaimer в конце (US требование)

## Интеграция с UBT OS

`/higgsfield ugc` → результат → A25 compliance_gate → A26 publer_publisher
`/higgsfield ab` → 3 видео → virality_predictor → лучший в Publer

## Настройки по GEO

| GEO | Аспект | Длина | Субтитры |
|-----|--------|-------|----------|
| US  | 9:16   | 15–45 | EN обязательно |
| BR  | 9:16   | 30–60 | PT-BR |
| MX  | 9:16   | 30–60 | ES |
| DE  | 9:16   | 15–30 | DE (строгий тон) |
| PL  | 9:16   | 30–45 | PL |
