# Ресерч: видео-стек UBT OS — Shorts Studio, Qwen3-TTS, LTX-2.3, Remotion, альтернативы Higgsfield

*Дата: 2026-07-02. По запросу: добавить формат шортсов, бесплатную озвучку,
бесплатную генерацию видео и резервные источники вместо единственного Higgsfield.*

---

## 1. Higgsfield Shorts Studio — «монтаж на автопилоте»

**Что это:** загружаешь исходное видео (4 сек – 2 мин) → выбираешь стиль-пресет
(«Комикс», «Глитч», «Клеймация»… или свой из 1–20 референсов) → получаешь
стилизованные короткие клипы 9:16/16:9, 720p. Движение и ритм оригинала
сохраняются. Оплата кредитами (цена показывается до рендера).

**Ключевое: это уже доступно через тот же MCP, что использует наш воркер.**
Инструменты: `shorts_studio_list_presets` → `shorts_studio_create`
(source_video_id + preset_id, 9:16) → опрос `shorts_studio_status`.
Плюс рядом есть `clipify` (Personal Clipper): одна ссылка на YouTube →
до 20 готовых клипов с субтитрами (шрифт/цвет/позиция настраиваются) —
это «шортсы из длинного видео» одним вызовом.

**План интеграции (≈1 день):**
- расширить `higgsfield_queue`: второй тип задания `shorts_restyle`
  (source_video_id, preset_id) и третий `clipify` (youtube_url);
- MCP-клиент уже написан — добавляются только вызовы инструментов;
- роуты `POST /shorts/restyle` и `POST /shorts/clipify` в main.py;
- источник исходников: наши сгенерированные видео из `videos.storage_url`
  или крипы конкурентов (внимание: чужой контент — только как референс стиля).

---

## 2. Qwen3-TTS — да, открытая и бесплатная

Выпущена январь 2026, **Apache 2.0** (можно коммерчески). 10 языков, включая
**русский**. Клонирование голоса по 3 сек референса (лучше 8–15 сек), «дизайн
голоса» текстовым описанием. Две модели: 1.7B (флагман) и 0.6B (лёгкая,
**от 4 GB VRAM**).

**Нюанс:** наш FirstVDS — без GPU. Варианты:
1. **DashScope API (Alibaba)** — облачный Qwen3-TTS, копейки за 1000 символов;
2. **Арендовать дешёвый GPU-инстанс** (RTX 3060/4060-класс хватит для 0.6B) и
   поднять сервер — у A35 уже есть слот `TTS_SERVER_URL` (self-hosted → ElevenLabs
   fallback), т.е. интеграция = поднять совместимый REST и вписать URL;
3. CPU-инференс 0.6B — работает, но медленно (не для потока).

**Рекомендация:** DashScope как primary в A35, ElevenLabs остаётся fallback →
себестоимость озвучки падает на порядок. Полдня работы.

---

## 3. LTX-2.3 (Lightricks) — «бесплатная» = открытые веса

Релиз 05.03.2026: 22B параметров, **Apache 2.0**, до 4K/50fps, **нативный
синхронный звук**, вертикаль 9:16, LoRA-тюнинг. «Бесплатно» — это веса на
HuggingFace: гонять надо на своём GPU (22B — это 24–48 GB VRAM класс).

**Для нас без GPU реалистично через API:**
- Lightricks API: ~**$0.04/сек** (Fast) — в ~5 раз дешевле Sora-класса;
- fal.ai (LTX-2-19B): ~**$0.20 за 5-сек 720p** ролик.

Это в разы дешевле кредитов Higgsfield → главный кандидат в постоянные
альтернативные провайдеры (см. п.5).

---

## 4. Remotion — программный рендер видео на React

**Это не генерация, а сборка:** видео описывается React-компонентами и
рендерится headless-браузером + ffmpeg на нашем же сервере (GPU не нужен).
Идеален для шаблонных форматов, где генеративная модель избыточна:
- слайдшоу Before/After из фото + текст + музыка;
- «текстовые» шортсы (факты/списки/квизы) с анимацией;
- прогресс-бары, счётчики, карусели для Pinterest/IG;
- брендированные интро/аутро и субтитры (синергия с A34).

**Лицензия:** бесплатно для физлиц и компаний ≤3 человек — под нас подходит;
при росте команды — платная company license (remotion.pro).

**План:** отдельный node-сервис `remotion-renderer` (docker), 2–3 шаблона
(before/after, факт-листикл, квиз-тизер), роут `POST /render/template`.
2–3 дня. Себестоимость ролика ≈ 0.

---

## 5. Альтернативы Higgsfield — мультипровайдерная архитектура

### 5.1. Предлагаемая архитектура: цепочка провайдеров

По образцу A35 (self-hosted → ElevenLabs) сделать `VideoGenProvider` с цепочкой
в env: `VIDEO_PROVIDER_CHAIN=stock,fal,higgsfield`. Воркер идёт по цепочке:
упал/нет кредитов → следующий. Очередь `higgsfield_queue` переименовать в
`video_gen_queue`, у задания появляется поле `provider`.

### 5.2. Агрегаторы API (один ключ — много моделей), цены fal.ai 04/2026

| Модель | Цена | Комментарий |
|---|---|---|
| **Wan 2.5** (Alibaba) | **$0.05/сек** | самый дешёвый, MoE, t2v+i2v |
| **LTX-2** | ~$0.20 / 5-сек 720p | быстрый, звук |
| Seedance 2 (ByteDance) | $0.24–0.30/сек 720p | качество/липсинк |
| Kling 3.0 | $0.4/сек | топ-качество, дорого |

Похожие агрегаторы для сравнения цен: Replicate, WaveSpeed, SiliconFlow.
**Рекомендация: fal.ai с Wan 2.5 как первый fallback** (5-сек ролик ≈ $0.25).

### 5.3. Опенсорс для self-host (если арендуем GPU ~$0.3–0.5/час за 4090)

| Модель | Лицензия | VRAM | Сильная сторона |
|---|---|---|---|
| **LTX-Video/2.3** | Apache 2.0 | 24GB+ | скорость: 5-сек клип < 30 сек на 4090 |
| **Wan 2.2/2.5** | Apache 2.0 | от 8–12GB (малые) | универсальность t2v/i2v/edit |
| HunyuanVideo 1.5 | Tencent (огранич.) | 24GB INT8 | физика движения |
| CogVideoX-5B | Apache 2.0 | 16–24GB | точное следование скрипту |
| Mochi 1 | Apache 2.0 | 24GB+ | пластика движения |

### 5.4. Полностью бесплатный уровень (без GPU): стоковый конвейер

Класс инструментов MoneyPrinterTurbo / ShortGPT (GitHub, 30k+ звёзд суммарно):
скрипт LLM → стоковые клипы **Pexels API (бесплатно)** → TTS → субтитры →
ffmpeg-склейка 9:16 1080p. **У нас 90% компонентов уже есть:** A21 (скрипт),
A35 (озвучка), A34 (субтитры + ffmpeg burn), ffmpeg в Docker-образе.

**Предложение — собственный `stock_video_pipeline` (1–2 дня):**
A21 скрипт → ключевые слова → Pexels клипы → A35 голос → ffmpeg склейка →
A34 сабы. Себестоимость ролика ≈ $0.01 (только токены Haiku). Это и есть
«постоянная замена» на случай, когда Higgsfield недоступен/дорог, плюс
вариативность контента (стоковые ролики выглядят иначе, чем генерация).

---

## 6. Рекомендуемый порядок внедрения

| # | Задача | Эффект | Оценка |
|---|---|---|---|
| 1 | `stock_video_pipeline` (Pexels + A35 + A34 + ffmpeg) | бесплатный поток видео уже сейчас | 1–2 дня |
| 2 | Провайдер-цепочка + fal.ai (Wan 2.5 / LTX-2.3) | резерв ×3 дешевле Higgsfield | 1 день |
| 3 | Qwen3-TTS (DashScope) как primary в A35 | −90% стоимости озвучки | 0.5 дня |
| 4 | Shorts Studio + clipify форматы в воркере | рестайл и нарезка шортсов | 1 день |
| 5 | Remotion-сервис с 2–3 шаблонами | карусели/слайдшоу с нулевой себестоимостью | 2–3 дня |

## Источники

- [github.com/QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [анонс Qwen](https://qwen.ai/blog?id=qwen3tts-0115)
- [huggingface.co/Lightricks/LTX-2.3](https://huggingface.co/Lightricks/LTX-2.3), [github.com/Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video), [fal.ai/ltx-2.3](https://fal.ai/ltx-2.3)
- [remotion.dev/docs/license](https://www.remotion.dev/docs/license)
- [higgsfield.ai/shorts-studio-intro](https://higgsfield.ai/shorts-studio-intro)
- [fal.ai/pricing](https://fal.ai/pricing), [сравнение цен video-API 04/2026](https://www.buildmvpfast.com/api-costs/ai-video)
- Обзоры опенсорс-моделей: [ltx.io/blog](https://ltx.io/blog/best-open-source-video-generation-models), [modal.com/blog](https://modal.com/blog/text-to-video-ai-article), [hyperstack.cloud](https://www.hyperstack.cloud/blog/case-study/best-open-source-video-generation-models)
- [github.com/harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo), ShortGPT и аналоги
