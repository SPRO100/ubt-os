-- ============================================================
-- PATCH 09: Начальное заполнение базы знаний kb_entries
-- Охватывает ключевые комбинации процесс × площадка × вертикаль × схема.
-- Идемпотентен: не перезапишет записи, которые уже существуют.
-- ============================================================

-- ── ПРОГРЕВ АККАУНТОВ ─────────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'warmup.tiktok.nutra.grey', 'warmup', 'nutra',
  'Прогрев TikTok нутра — серая схема',
  'Дни 1-3: только просмотры FYP 20-30 мин/день, не постим, не подписываемся. '
  'Дни 4-7: 1-2 лайфстайл-поста без продукта, 5-10 подписок на ЗОЖ-аккаунты. '
  'Дни 8-14: ссылка в bio, контент с намёком на трансформацию без медицинских заявлений. '
  'Готовность: ER >5%, 100+ подписчиков, хэштег-тест без shadow-ban. '
  'Нельзя: слова "лечение", "похудение", "болезнь" — заменяем метафорами ("энергия", "форма").',
  ARRAY['warmup','tiktok','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'warmup.tiktok.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'warmup.tiktok.betting.black', 'warmup', 'betting',
  'Прогрев TikTok беттинг — чёрная схема',
  'Ферма устройств: каждый аккаунт = отдельный телефон + местная SIM GEO-оффера. '
  'Дни 1-7: просмотр спортивного контента 30-40 мин/день, нет постов. '
  'Дни 8-14: спортивные посты 2-3/день (результаты матчей, аналитика) без упоминания ставок. '
  'Дни 15-21: "мои прогнозы вчера сыграли" — без ссылок и слов "ставки/казино". '
  'День 22+: ссылка bio → Linktree → Telegram → оффер. '
  'Критично: не менять девайс/IP в ходе прогрева — это основной сигнал детекции.',
  ARRAY['warmup','tiktok','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'warmup.tiktok.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'warmup.facebook.nutra.grey', 'warmup', 'nutra',
  'Прогрев Facebook нутра — серая схема',
  'Аккаунт: возраст 60+ дней (купленный или выращенный с активностью в группах). '
  'Дни 1-7: активность в нишевых группах (ЗОЖ, фитнес), репосты, заполнение профиля. '
  'Дни 8-21: создание бизнес-страницы, нейтральные ЗОЖ-посты, 0 рекламы. '
  'День 22+: BM → Ad Account → Pixel → запуск кампании $10/день для сбора первых событий. '
  'Метод Farmer: постепенное расширение бюджета +20% каждые 3 дня при стабильном CPM. '
  'Нельзя: medical claims в первых объявлениях — начинаем с awareness, не conversion.',
  ARRAY['warmup','facebook','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'warmup.facebook.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'warmup.facebook.betting.black', 'warmup', 'betting',
  'Прогрев Facebook беттинг — чёрная схема',
  'Антидетект: Dolphin Anty или Multilogin, отдельный профиль на каждый аккаунт. '
  'Резидентный прокси: 4G мобильный, геопривязка к GEO оффера, не датацентр. '
  'Facebook Profile Score: целевой 70+ (проверяем через Facebook Pixel Helper). '
  'BM-страхование: 3+ Business Manager, у каждого 2+ Ad Account, резервные BM готовы. '
  'Трастовые BM: покупные (90+ дней истории) или выращенные через белые кампании. '
  'Нельзя: логиниться в FB из IP, где залит аккаунт-донор или BM.',
  ARRAY['warmup','facebook','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'warmup.facebook.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'warmup.instagram.nutra.grey', 'warmup', 'nutra',
  'Прогрев Instagram нутра — серая схема',
  'Бизнес-аккаунт: переключить с личного, добавить ниша-ключевые слова в имя/bio. '
  'Дни 1-7: Stories 2-3/день (lifestyle без продукта), массфолловинг 20-30/день в ЗОЖ-нише. '
  'Дни 8-14: Reels без продукта (трансформация образа жизни), engagement bait в Stories. '
  'Дни 15-21: subtle product placement в Stories, swipe-up если 10K+ подписчиков. '
  'Action-блок: не превышать 500 действий/день (лайки+подписки+комменты суммарно). '
  'Тест готовности: post reach >15% от подписчиков, stories views >20%.',
  ARRAY['warmup','instagram','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'warmup.instagram.nutra.grey' AND is_current = TRUE);

-- ── ЗАЛИВ ТРАФИКА ─────────────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.tiktok.nutra.grey', 'zaliv', 'nutra',
  'Залив TikTok нутра — серая схема',
  'Формат: Before/After 15-30 сек, hook первые 3 сек (лицо крупным планом). '
  'Запрещённые слова: "похудение", "лечение", "болезнь", "диагноз" — метафоры: "энергия", "форма", "мой секрет". '
  'Хэштеги: mix нишевых (#wellness, #transformation) + широких (#fyp, #foryou) — 3-5 шт. '
  'Время публикации: 7-9 утра или 19-22 вечера по GEO-таргету. '
  'Ротация: 3-4 аккаунта в параллель, 1-2 поста/аккаунт/день. '
  'CTA: "ссылка в профиле" — офер через bio link. '
  'Стоп-сигнал: CTR bio <0.5% или CPA >3× target → меняем hook.',
  ARRAY['zaliv','tiktok','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.tiktok.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.tiktok.betting.black', 'zaliv', 'betting',
  'Залив TikTok беттинг — чёрная схема',
  'Контент: спортивные результаты, "мои прогнозы", аналитика матчей — без слова "ставки/казино". '
  'Клоака через Keitaro: TikTok-бот → белая страница (спортивный блог), живой user → Telegram-бот → оффер. '
  'Trigger-логика: User-Agent + IP-репутация (чистый IP + мобильный UA = пользователь). '
  'Воронка: TikTok органика → bio link → Telegram-бот CRM-прогрев → оффер казино с депозитом. '
  'Арбитраж (TikTok Ads): клоачная кампания с белым креативом (спорт-аналитика) → CPL $3-8 на Tier-1. '
  'Ротация аккаунтов: при первом ограничении → новый аккаунт из запаса (банк 5-10 прогретых).',
  ARRAY['zaliv','tiktok','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.tiktok.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.facebook.nutra.grey', 'zaliv', 'nutra',
  'Залив Facebook нутра — серая схема',
  'Форматы по эффективности: видео-крип 15-30 сек > карусель > статика (CTR в 3-8×). '
  'Таргет: женщины 35-55, интересы (wellness, weight loss, healthy living), GEO US/UK/AU. '
  'Look-alike: 1-3% от базы покупателей (нужно 500+ событий Purchase в пикселе). '
  'Ретаргет: посетители LP за 30 дней исключая покупателей — CR в 2-4× выше. '
  'Бюджет: $20-50/день для поиска рабочего крипа (3-4 дня), масштаб победителя +20%/3 дня. '
  'Social proof: "47,000 довольных покупателей" в тексте крипа повышает CR на 15%. '
  'Субтитры: обязательны (90% смотрят без звука).',
  ARRAY['zaliv','facebook','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.facebook.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.facebook.betting.black', 'zaliv', 'betting',
  'Залив Facebook беттинг — чёрная схема',
  'Структура: BM → Campaign (CBO) → Adset → Ad с клоакером (Keitaro). '
  'Клоака: Facebook-бот (IP ASN Meta/Facebook) → белая страница "спортивный прогноз"; живой user → лендинг казино. '
  'Пиксель: устанавливаем на белую страницу — Facebook видит чистый трафик, обучение идёт. '
  'CBO: Campaign Budget Optimization перераспределяет на лучшие Adsets автоматически. '
  'Резерв: 3 Ad Account в разных BM — при бане одного мгновенно переключаемся. '
  'Расходный лимит: старт $10/день, рост +20% каждые 3 дня при стабильном одобрении объявлений.',
  ARRAY['zaliv','facebook','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.facebook.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.instagram.nutra.grey', 'zaliv', 'nutra',
  'Залив Instagram нутра — серая схема',
  'Stories swipe-up: нужен бизнес-аккаунт 10K+ подписчиков (или Meta Ads с ссылкой). '
  'Reels: hook за 3 сек, "трансформация за 30 дней", без medical claims, 15-30 сек оптимум. '
  'Collab posts: партнёрство с нано-инфлюенсерами 3K-30K в ЗОЖ-нише — доверие выше. '
  'Хэштеги: 5-10, сочетание нишевых (#weightlossjourney) и средних (#healthylifestyle). '
  'Story-воронка: Story 1 (проблема) → Story 2 (решение) → Story 3 (CTA + ссылка). '
  'Лучший охват: публикация Reels 11-13 или 20-22 по GEO.',
  ARRAY['zaliv','instagram','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.instagram.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.youtube.nutra.white', 'zaliv', 'nutra',
  'Залив YouTube Shorts/Long-form нутра — белая схема',
  'Shorts (15-60 сек): hook за 3 сек, "трансформация", affiliate ссылка в описании + pinned comment. '
  'Long-form (8-15 мин): обзор продукта + личный опыт + научная база — SEO-дистрибуция. '
  'SEO-заголовок: ключевое слово в первых 60 символах ("Best [продукт] for [проблема] 2025"). '
  'Thumbnail: лицо + до/после + яркий контраст → CTR 8-12%. '
  'Affiliate ссылка: в описании с UTM + pinned comment "Ссылка на продукт ↓". '
  'Compliance: можно упоминать ингредиенты, исследования — без "лечит болезни", нужен disclaimer.',
  ARRAY['zaliv','youtube','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.youtube.nutra.white' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'zaliv.pinterest.nutra.white', 'zaliv', 'nutra',
  'Залив Pinterest нутра — белая схема',
  'Pinterest = поисковик: SEO-оптимизация заголовка и описания пина обязательна. '
  'Форматы: инфографика (советы, списки) > до/после > рецепты > product showcases. '
  'Rich Pins: подключаем product Rich Pin для автопулла цены и описания из магазина. '
  'Размер: вертикальные пины 2:3 или 1:2 (1000×1500 пикс) занимают больше места в ленте. '
  'Аудитория: женщины 25-45 US/UK/AU — лучший GEO для нутра Pinterest. '
  'Расписание: 5-10 пинов/день через Tailwind для равномерного распределения.',
  ARRAY['zaliv','pinterest','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'zaliv.pinterest.nutra.white' AND is_current = TRUE);

-- ── МАСТЕР-ПРОМТЫ ГЕНЕРАЦИИ ───────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'master_prompt.tiktok.nutra.grey', 'master_prompt', 'nutra',
  'Мастер-промт TikTok нутра (серый)',
  'Роль: "Создай TikTok-скрипт для нутра-продукта — серая схема. Без медицинских заявлений." '
  'Структура: Hook 3 сек → Проблема 5 сек → Трансформация 10 сек → CTA 3 сек. '
  'Запрещённые слова: лечить, болезнь, диагноз, врач рекомендует, клинически доказано. '
  'Разрешённые метафоры: "изменилась моя энергия", "перестала влезать в любимые джинсы", "мой секрет". '
  'Tone: первое лицо, разговорный UGC-стиль (не рекламный, не официальный). '
  'Hooks-стартеры: "Я не верила что это сработает, но через 3 недели..." / '
  '"Никто не говорит об этом, но я поделюсь..." / "Стоп-стоп-стоп, посмотри что я нашла..." '
  'Видео: лицо крупным планом первые 2 сек → completion rate +20%.',
  ARRAY['master_prompt','tiktok','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'master_prompt.tiktok.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'master_prompt.tiktok.betting.black', 'master_prompt', 'betting',
  'Мастер-промт TikTok беттинг (чёрный)',
  'Роль: "Создай TikTok-контент о спортивной аналитике. Никаких упоминаний ставок/казино." '
  'Ключевая подмена: "прогноз" вместо "ставка", "аналитика" вместо "беттинг". '
  'Форматы: "Мои прогнозы на [матч]", "ТОП 3 матча выходных", "Итоги недели — угадал?". '
  'Engagement bait: "Пишите в комментах свой прогноз на [матч]". '
  'Перенаправление: "Больше эксклюзивной аналитики в Telegram — ссылка в bio". '
  'Tone: спортивный эксперт/аналитик, не азартный игрок; уверенный, но не кричащий. '
  'Без: слов казино, выигрыш денег, букмекер, ставки на деньги.',
  ARRAY['master_prompt','tiktok','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'master_prompt.tiktok.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'master_prompt.facebook.nutra.grey', 'master_prompt', 'nutra',
  'Мастер-промт Facebook нутра (серый)',
  'Роль: "Создай Facebook Ad для нутра-оффера, аудитория женщины 35-55, US/UK." '
  'Primary text (3-5 предложений): история + трансформация. Без цифр потери веса. '
  'Headline: вопрос или неожиданный факт ("Почему диеты не работают после 40?"). '
  'Запрещено: "похудей", "жги жир", конкретные цифры потери веса, до/после. '
  'CTA button: "Узнать больше" или "Получить" (не "Купить" на холодную). '
  'Social proof: "Более 50,000 женщин уже изменили свой образ жизни с..." '
  'Структура успешного крипа: вопрос → идентификация → обещание → CTA.',
  ARRAY['master_prompt','facebook','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'master_prompt.facebook.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'master_prompt.any.nutra.white', 'master_prompt', 'nutra',
  'Мастер-промт нутра белая схема (универсальный)',
  'Белый контент: допустимы факты о составе, ссылки на исследования, механизм действия. '
  'Структура отзыва: Контекст (кто я) → Проблема → Как нашёл продукт → Результат → Рекомендация. '
  'Compliance обязателен: "These statements have not been evaluated by the FDA. '
  'This product is not intended to diagnose, treat, cure, or prevent any disease." '
  '"Results may vary. Individual results are not guaranteed." '
  'Научная база: PubMed-ссылки на ингредиенты повышают доверие и снижают риск бана. '
  'Tone: информационный, не давящий продажами; образовательный.',
  ARRAY['master_prompt','any','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'master_prompt.any.nutra.white' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'master_prompt.any.betting.black', 'master_prompt', 'betting',
  'Мастер-промт беттинг чёрная схема (универсальный)',
  'Нарратив: спортивный эксперт/аналитик — не азартный игрок. '
  'Ключевые замены: прогноз/ставка, аналитика/беттинг, экспертиза/выигрыш. '
  'Воронка контента: интерес к спорту → доверие к аналитике → переход в Telegram → оффер. '
  'Telegram-нарратив: "VIP группа с эксклюзивными прогнозами", "бесплатный тест стратегии на 7 дней". '
  'Крюк на ценность: показываем результаты прогнозов (скриншоты), не деньги. '
  'Запрещено в любом контенте: слова казино, деньги выиграл, ставки, букмекер.',
  ARRAY['master_prompt','any','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'master_prompt.any.betting.black' AND is_current = TRUE);

-- ── ПРОИЗВОДСТВО КОНТЕНТА ─────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'content.tiktok.nutra.grey', 'content', 'nutra',
  'Производство контента TikTok нутра (серый)',
  'Рабочие форматы по CR: Before/After > Testimonial UGC > "Секрет который скрывают" > "Тест на себе". '
  'Длина: 15-30 сек оптимум, >60 сек резко падает completion rate. '
  'Caption: ≤150 символов, 3-5 хэштегов (2 нишевых + 2 широких + 1 брендовый). '
  'Визуал: лицо крупным планом первые 2 сек — completion rate +20%; яркий освещение. '
  'Звук: трендовые аудио +30% органический охват; собственный голос → выше доверие и CR. '
  'A/B тест: меняем только hook, остальное фиксируем — 3 варианта hook за 3 дня. '
  'Volume: Higgsfield AI для генерации UGC-видео с разными лицами/углами без актёров.',
  ARRAY['content','tiktok','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'content.tiktok.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'content.tiktok.betting.grey', 'content', 'betting',
  'Производство контента TikTok беттинг (серый)',
  'Форматы: "Мой прогноз на сегодня", "Итоги недели", "ТОП 3 матча", live-реакция после матча. '
  'Faceless работает: голос за кадром + скриншоты статистики/таблиц — без раскрытия личности. '
  'Engagement bait: "Пишите в комментах свой прогноз на [матч]" → алгоритм продвигает. '
  'Длина: 30-45 сек оптимум для аналитического формата. '
  'Тренды: используем текущие горячие матчи (Champions League, World Cup) — алгоритм busts. '
  'Стикеры/опросы: "Угадаю счёт?" в TikTok LIVE → дополнительный охват.',
  ARRAY['content','tiktok','betting','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'content.tiktok.betting.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'content.facebook.nutra.grey', 'content', 'nutra',
  'Производство контента Facebook нутра (серый)',
  'Video vs image: CTR видео в 3-8× выше статики для нутра-офферов. '
  'Первые 3 сек без звука: 90% смотрят без звука → субтитры обязательны во всём крипе. '
  'Social proof frame: "47,000 довольных покупателей" в начале видео → CR +15%. '
  'Split test: 3-4 крипа одновременно в одном Ad Set; останавливаем проигравших через 3 дня. '
  'Winning threshold: CPC <$1.50 + CTR >2% = масштабируем. '
  'Усталость крипа: при росте frequency >2.5 → обновляем креатив или меняем аудиторию.',
  ARRAY['content','facebook','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'content.facebook.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'content.youtube.nutra.white', 'content', 'nutra',
  'Производство контента YouTube нутра (белый)',
  'SEO: ключевое слово в первых 60 символах заголовка, в описании первые 2 строки, в тегах. '
  'Thumbnail formula: лицо (эмоция) + до/после + яркий контраст + цифра → CTR 8-12%. '
  'Длина: 8-12 мин для порога монетизации; Shorts 15-60 сек для охвата. '
  'Структура Long-form: hook 0-30 сек → проблема → личный опыт → продукт → результат → CTA. '
  'Affiliate: ссылка в описании с UTM + pinned comment "Ссылка на продукт ↓ (со скидкой)". '
  'Compliance: можно исследования, ингредиенты — нельзя "лечит болезни". Disclaimer в описании.',
  ARRAY['content','youtube','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'content.youtube.nutra.white' AND is_current = TRUE);

-- ── АНТИБАН / АНТИДЕТЕКТ ──────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'antiban.tiktok.any.grey', 'antiban', 'any',
  'Антибан TikTok — серая схема',
  'Shadow-ban тест: публикуем с нишевым хэштегом → проверяем видимость через чистый аккаунт без входа. '
  'Триггеры shadow-ban: запрещённые слова, жалобы пользователей, rapid follow/unfollow, спам-лайки. '
  'Recovery: 48 ч полная тишина, затем 5-7 дней только нативный органический контент (без CTA). '
  'Ротация: бан аккаунт → холодильник 2 недели → следующий из запаса. '
  'Запрещено: >3 постов/час, сторонние накрутки, точный дубликат контента с другого аккаунта. '
  'Безопасная частота: 1-2 поста/день/аккаунт с интервалом ≥4 ч.',
  ARRAY['antiban','tiktok','any','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'antiban.tiktok.any.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'antiban.tiktok.any.black', 'antiban', 'any',
  'Антибан TikTok — чёрная схема',
  'Device fingerprint: каждый аккаунт = отдельное физическое устройство ИЛИ Multilogin-профиль. '
  'SIM: местная SIM на каждый аккаунт (GEO оффера), никогда не переиспользовать. '
  'IP: резидентный 4G прокси, не датацентр; меняем IP только одновременно с девайсом. '
  'При бане: НЕ апеллировать (апелляция — маркер для ML-системы, повышает Score аккаунта). '
  'Новый аккаунт: всегда свежее устройство / профиль, не "чистить" старый. '
  'Банк аккаунтов: держать 5-10 прогретых аккаунтов в резерве постоянно.',
  ARRAY['antiban','tiktok','any','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'antiban.tiktok.any.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'antiban.facebook.any.black', 'antiban', 'any',
  'Антибан Facebook — чёрная схема',
  'BM-страхование: 3+ Business Manager с 2+ Ad Account каждый; при бане переключение за <10 мин. '
  'Расходный лимит: старт $10/день, рост +20% каждые 3 дня при одобрении объявлений. '
  'Правило: никогда не логиниться в FB из IP, где залит аккаунт-донор или BM. '
  'Антидетект: Dolphin Anty или Multilogin — отдельный профиль на каждый аккаунт/BM. '
  'Резидентный прокси: 4G мобильный с геопривязкой к GEO оффера, не датацентр. '
  'При бане AA: немедленно дублируем кампании на резервный AA (готовить заранее).',
  ARRAY['antiban','facebook','any','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'antiban.facebook.any.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'antiban.instagram.any.grey', 'antiban', 'any',
  'Антибан Instagram — серая схема',
  'Action-блок: не превышать 500 действий/день суммарно (лайки + подписки + комменты). '
  'Разогрев активности: 10 → 20 → 50 → 100 действий/день (по одной неделе на уровень). '
  'При action-block: пауза 24 ч, затем возобновляем с 50% от прежнего объёма. '
  'Niche hashtag limit: ≤10 хэштегов/пост, чередовать наборы (не копипастить одни и те же). '
  'Stories link: использовать link sticker, не swipe-up — меньше ограничений. '
  'Проверка: публикуем хэштег-пост и проверяем видимость через другой чистый аккаунт.',
  ARRAY['antiban','instagram','any','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'antiban.instagram.any.grey' AND is_current = TRUE);

-- ── ПРЕЛЕНДИНГИ / КЛОАКА ──────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'prelanding.any.nutra.grey', 'prelanding', 'nutra',
  'Прелендинги нутра — серая схема',
  'Типы по CR: Quiz ("Ваш тип метаболизма") > Story ("Моя история") > Article ("Врачи удивлены"). '
  'Quiz повышает CR на 25-40% vs прямой лендинг — персонализация создаёт вовлечённость. '
  'Клоака: бот (Facebook Pixel Helper, GoogleBot, IP датацентра) → белый лендинг; user → нутра LP. '
  'Обязательно: Privacy Policy и Terms of Service страницы (для прохождения модерации FB/TikTok). '
  'Quiz-структура: 3-5 вопросов (образ жизни, цель) → персонализированный результат → оффер. '
  'Story-структура: знакомство с героем → проблема → кризис → продукт → трансформация → CTA.',
  ARRAY['prelanding','any','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'prelanding.any.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'prelanding.any.betting.black', 'prelanding', 'betting',
  'Прелендинги беттинг — чёрная схема',
  'Типы: "Сегодняшние прогнозы VIP", "Бесплатный тест стратегии 7 дней", "Закрытый канал аналитиков". '
  'Воронка: трафик (TikTok/FB) → Prelanding (спортивная аналитика) → Telegram-бот → оффер казино. '
  'Telegram-бот: CRM + прогрев (3-5 бесплатных прогнозов) → нативный оффер на регистрацию. '
  'Клоака: модератор видит "спортивный блог" без упоминания денег; пользователь видит форму регистрации. '
  'Ключевой принцип: казино/букмекер появляется ТОЛЬКО в Telegram, не на прелендинге. '
  'Юридический буфер: Telegram между прелендингом и оффером — разрывает прямую связь.',
  ARRAY['prelanding','any','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'prelanding.any.betting.black' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'prelanding.any.nutra.white', 'prelanding', 'nutra',
  'Прелендинги нутра — белая схема',
  'VSL (Video Sales Letter): 2-5 мин видео + текстовый вариант ниже. '
  'Структура VSL: проблема → агитация (почему болезненно) → решение → доказательства → оффер → гарантия. '
  'Соответствие: без medical claims, "not evaluated by FDA", "results may vary" внизу страницы. '
  'A/B тест: headline + CTA кнопка (цвет, текст) — минимум 2 варианта параллельно. '
  'Social proof: реальные отзывы с фото (не сток) + звёздный рейтинг. '
  'Trust elements: сертификаты GMP/ISO, ингредиенты с исследованиями, secure checkout badge.',
  ARRAY['prelanding','any','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'prelanding.any.nutra.white' AND is_current = TRUE);

-- ── ПУБЛИКАЦИЯ И UTM ──────────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'publishing.tiktok.any.grey', 'publishing', 'any',
  'Публикация TikTok — серая схема',
  'Расписание: 7-9 утра, 12-14 дня, 19-22 вечера по часовому поясу GEO. '
  'UTM: utm_source=tiktok&utm_medium=organic&utm_campaign={vertical}&utm_content={account_id}. '
  'Планирование: Publer за 1-2 недели вперёд, чередуем аккаунты (не 2 поста с одного в день). '
  'Пост-публикация: первые 30 мин не трогаем — TikTok алгоритм решает охват. '
  'Первый час: ответить на первые 3-5 комментариев — engagement буст. '
  'Синхронизация: один и тот же видеофайл не публиковать на 2 разных аккаунта.',
  ARRAY['publishing','tiktok','any','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'publishing.tiktok.any.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'publishing.facebook.any.grey', 'publishing', 'any',
  'Публикация Facebook — серая схема',
  'Оптимальное время: Tue-Thu, 9-11 утра и 18-20 вечера по GEO. '
  'Частота: 1-2 поста/день на бизнес-страницу (выше — падение органического охвата). '
  'UTM обязателен: utm_source=facebook&utm_medium=organic&utm_campaign={vertical}&utm_content={page_id}. '
  'Meta Business Suite: планируем за 2 недели, статус "Scheduled" — надёжнее сторонних инструментов. '
  'Stories: 2-3 в день без привязки к расписанию — охват stories отдельный от постов. '
  'Первый комментарий: сразу после публикации оставляем комментарий от страницы с CTA.',
  ARRAY['publishing','facebook','any','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'publishing.facebook.any.grey' AND is_current = TRUE);

-- ── ИНФРАСТРУКТУРА ────────────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'infra.any.any.grey', 'infra', 'any',
  'Инфраструктура — серая схема',
  'Прокси: мобильные резидентные (4G) > датацентр для прогрева; ротация IP каждые 5-10 мин. '
  'SIM-карты: виртуальные (SMS-activate.org) для верификации аккаунтов; физические для прогрева TikTok. '
  'Антидетект: Dolphin Anty (дешевле) или Multilogin (надёжнее) — отдельный профиль на каждый аккаунт. '
  'Хранение паролей: Bitwarden (не браузерный менеджер). '
  'VPN: НЕ использовать в связке с прогреваемыми аккаунтами TikTok/FB (маркер бота). '
  'Keitaro: трекер для клоаки + аналитики воронки; отдельный сервер от основного.',
  ARRAY['infra','any','any','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'infra.any.any.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'infra.any.any.black', 'infra', 'any',
  'Инфраструктура — чёрная схема',
  'Ферма устройств: 5-20 физических телефонов, каждый со своей SIM и аккаунтом. '
  'IP: покупаем мобильные 4G прокси от локальных провайдеров GEO-оффера — не перепродавцов. '
  'Автоматизация: ManyChat для Telegram-воронки; ботовые лайки для старта охвата (умеренно, <20% аудитории). '
  'Безопасность: отдельный физический компьютер или VM для чёрных схем — не смешивать с белым. '
  'Оплата инфраструктуры: крипта или карты без привязки к личным данным. '
  'Резервирование: для каждого элемента (аккаунт/BM/прокси/SIM) держать 2× запас.',
  ARRAY['infra','any','any','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'infra.any.any.black' AND is_current = TRUE);

-- ── АНАЛИТИКА И АТРИБУЦИЯ ────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'analytics.any.nutra.white', 'analytics', 'nutra',
  'Аналитика и атрибуция — нутра белая',
  'Ключевые метрики: CTR (крип→LP), CR (LP→Purchase), EPC (доход на клик), ROAS, LTV. '
  'Keitaro: трекер UTM-цепочки + attribution + A/B тест LP. '
  'Атрибуция: last-click для быстрых решений; data-driven (Google Ads / Meta) для масштаба. '
  'Ежедневный срез (A16): 10:00 — CPA, ROAS, бюджет/расход, статус кампаний. '
  'Еженедельный отчёт (A15): стратегический срез — топ/провал крипы, GEO, аудитории. '
  'Cohort LTV: нутра без подписки — считаем повторные покупки за 30/60/90 дней.',
  ARRAY['analytics','any','nutra','white'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'analytics.any.nutra.white' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'analytics.any.betting.black', 'analytics', 'betting',
  'Аналитика и атрибуция — беттинг чёрная',
  'Ключевые метрики: CPL (стоимость лида/регистрации), FTD (First Time Deposit), CPF (стоимость депозита). '
  'Модель оплаты: CPA (фиксированное за FTD) vs RevShare (% от проигрыша игрока) — CPA предпочтительнее на старте. '
  'Telegram-воронка: подписчик → прогрев (3-5 дней) → оффер → регистрация → депозит. '
  'Конверсия: подписчик→регистрация 15-25%; регистрация→FTD 20-35% (зависит от GEO и оффера). '
  'Keitaro: трекинг всей воронки включая Telegram через бот-webhook. '
  'GEO-приоритет: DACH (DE/AT/CH) и Nordics дают FTD $50-150; Tier-2 (BR, IN) — $5-20.',
  ARRAY['analytics','any','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'analytics.any.betting.black' AND is_current = TRUE);

-- ── МАСШТАБИРОВАНИЕ ────────────────────────────────────────

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'scaling.tiktok.nutra.grey', 'scaling', 'nutra',
  'Масштабирование TikTok нутра (серый)',
  'Горизонтальный: копируем рабочий крип → 3-5 новых аккаунтов параллельно. '
  'Вертикальный (Spark Ads): продвигаем органический пост с согласия создателя — KPI CTR >1.5%. '
  'Микс стратегия: органика 3-4 аккаунта ($0) + Spark Ads $50-200/день = оптимальный ROI. '
  'Стоп-сигнал масштаба: CTR bio <1% ИЛИ CPA >3× target → пауза, меняем hook. '
  'GEO-расширение: копируем рабочую схему US → UK → CA → AU (схожая аудитория, меньше конкуренции). '
  'Контент-масштаб: Higgsfield AI для 10+ вариантов видео из одного скрипта (разные лица, углы).',
  ARRAY['scaling','tiktok','nutra','grey'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'scaling.tiktok.nutra.grey' AND is_current = TRUE);

INSERT INTO kb_entries (entry_key, category, vertical, title, content, tags, changed_by, change_reason)
SELECT
  'scaling.facebook.betting.black', 'scaling', 'betting',
  'Масштабирование Facebook беттинг (чёрная)',
  'Дублируем Ad Set, не кампанию — сохраняем обучение пикселя (>50 событий/неделю в AdSet). '
  'CBO (Campaign Budget Optimization): алгоритм перераспределяет бюджет на топ-AdSets автоматически. '
  'Lookalike expansion: 1% (seed 1000+ FTD событий) → 2-3% после стабилизации CPA. '
  'Международный масштаб: дублируем кампанию на новый GEO через отдельный Ad Account в том же BM. '
  'Бюджет: удваиваем каждые 48-72 ч если CPA ≤ target; при росте CPA >20% → пауза на оптимизацию. '
  'Крип-ротация: новый креатив каждые 7-10 дней (fatigue при frequency >3).',
  ARRAY['scaling','facebook','betting','black'], 'seed', 'начальное заполнение базы знаний'
WHERE NOT EXISTS (SELECT 1 FROM kb_entries WHERE entry_key = 'scaling.facebook.betting.black' AND is_current = TRUE);
