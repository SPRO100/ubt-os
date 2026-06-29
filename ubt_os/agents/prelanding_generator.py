"""
A29 — PRELANDING_GENERATOR
Генерирует HTML прелендинг-страницы для воронок nutra/betting.
Форматы: quiz (квиз), native_article (нативная статья), story (история успеха), vsl (видео-сейл).
Поддерживает COD/Trial/SS модели и мультиязычность (EN/PT/ES/DE/PL).
"""
from __future__ import annotations
import logging, os, re
from dataclasses import dataclass
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import extract_json as _extract_json

logger = logging.getLogger("ubt_os.prelanding_generator")


@dataclass
class PrelandingResult:
    offer_name: str
    vertical: str
    geo: str
    billing_model: str
    format: str
    language: str
    html_content: str
    word_count: int
    estimated_cr: str
    compliance_notes: list[str]
    funnel_tips: list[str]


_LANGUAGE_MAP = {
    "US": "en", "UK": "en", "AU": "en", "CA": "en",
    "BR": "pt", "MX": "es",
    "DE": "de", "PL": "pl",
}

_FORMAT_PROMPTS = {
    "quiz": """Создай HTML квиз-прелендинг (quiz funnel).
Структура:
- Заголовок: "Find Out If [Product] Can Help You" (или на соотв. языке)
- 4–6 вопросов с вариантами ответов (radio buttons)
- Прогресс-бар вверху
- После последнего вопроса → кнопка "See My Results" → редирект на лендинг
- Каждый ответ ведёт к одному "позитивному" результату
- Кнопка CTA: "Claim Your [Product]" или эквивалент
- Дизайн: чистый, мобильный, зелёный акцент""",

    "native_article": """Создай HTML нативную статью-прелендинг.
Структура (псевдо-новость или блог):
- Шапка как у новостного сайта (логотип + nav)
- Заголовок в стиле: "Local [City] Woman Discovers Secret to [Benefit]" или аналог
- 400–600 слов текста с натуральным упоминанием продукта
- 2–3 секции с подзаголовками
- "Embedded" цитата от "эксперта" или "пользователя"
- Фото-placeholder (div с alt-текстом)
- CTA блок в конце: "Learn More" / "Get Yours Today"
- Дата публикации (свежая), имитация настоящей статьи""",

    "story": """Создай HTML прелендинг в формате истории успеха (testimonial story).
Структура:
- Заголовок: "My [X]-Day Journey with [Product]" или аналог
- От первого лица: проблема → открытие → трансформация → результат
- Timeline или этапы (неделя 1, неделя 2, итог)
- Несколько "реальных" фото-плейсхолдеров (div с описанием)
- Блок с Before/After (lifestyle, не медицинский контекст)
- Звёздный рейтинг и комментарии других пользователей (2–3 фейковых отзыва)
- Большая CTA кнопка: "I Want This Too" / "Try [Product]"
- Таймер обратного отсчёта (опционально, JavaScript)""",

    "vsl": """Создай HTML VSL (Video Sales Letter) прелендинг.
Структура:
- Видео-плейсхолдер (тёмный div 16:9 с play-кнопкой)
- Под видео: транскрипт первых 100 слов
- Пока видео "загружается" — текст-хук выше видео
- Прогресс видео (имитация загрузки)
- CTA кнопка появляется через 30 секунд (JavaScript setTimeout)
- Социальные доказательства справа/снизу
- Ограниченное предложение + таймер""",
}

_COMPLIANCE_RULES = {
    "nutra": {
        "US": [
            "Не использовать: cure, treat, diagnose, prevent disease",
            "Не использовать: guaranteed results, lose X lbs in Y days",
            "Можно: supports, maintains, promotes, helps with",
            "Lifestyle before/after — OK. Медицинское before/after — НЕТ",
            "FTC требует: явные дисклеймеры о результатах ('Results may vary')",
        ],
        "BR": [
            "Não usar: cura, trata, elimina diabetes",
            "Pode usar: suporta, ajuda, contribui para",
            "ANVISA: não fazer afirmações medicamentosas",
        ],
        "MX": [
            "No usar: cura, trata, elimina enfermedades",
            "COFEPRIS: sin afirmaciones médicas",
            "Puede usar: apoya, ayuda, contribuye",
        ],
        "DE": [
            "Keine Heilversprechen (Heilmittelwerbegesetz)",
            "Erlaubt: unterstützt, fördert, beiträgt zu",
            "Pflicht: Disclaimer 'Kein Ersatz für medizinische Behandlung'",
        ],
        "PL": [
            "Nie używać: leczy, leczyć, wyleczyć",
            "Wolno: wspiera, pomaga, przyczynia się do",
            "Wymagane: 'Wyniki mogą się różnić'",
        ],
    },
    "betting": {
        "US": [
            "Не использовать: guaranteed win, guaranteed profit",
            "Educational format: sports analysis, not gambling promotion",
            "Не использовать слова bet, gambling, casino в SEO-заголовках",
            "Возраст 21+: обязательный дисклеймер для некоторых штатов",
        ],
    },
}

_BILLING_CTA = {
    "COD": {
        "en": ("Order Now — Pay on Delivery", "No credit card needed. Pay when you receive!"),
        "pt": ("Peça Agora — Pague na Entrega", "Sem cartão de crédito. Pague ao receber!"),
        "es": ("Pedir Ahora — Pagar al Recibir", "Sin tarjeta. ¡Paga cuando lo recibas!"),
        "de": ("Jetzt bestellen — Bei Lieferung bezahlen", "Keine Kreditkarte nötig!"),
        "pl": ("Zamów Teraz — Zapłać przy odbiorze", "Bez karty kredytowej!"),
    },
    "Trial": {
        "en": ("Try FREE for 30 Days", "Just cover $4.95 shipping. Cancel anytime."),
        "pt": ("Teste GRÁTIS por 30 Dias", "Apenas $4.95 de frete. Cancele quando quiser."),
        "es": ("Prueba GRATIS 30 Días", "Solo $4.95 de envío. Cancela cuando quieras."),
        "de": ("30 Tage KOSTENLOS testen", "Nur $4.95 Versand. Jederzeit kündbar."),
        "pl": ("Testuj BEZPŁATNIE 30 Dni", "Tylko $4.95 wysyłki. Anuluj w dowolnym momencie."),
    },
    "SS": {
        "en": ("Get Yours Today", "One-time purchase. 30-day money-back guarantee."),
        "pt": ("Compre Agora", "Compra única. Garantia de 30 dias."),
        "es": ("Consigue el Tuyo Hoy", "Compra única. Garantía de 30 días."),
        "de": ("Jetzt kaufen", "Einmalkauf. 30-Tage-Geld-zurück-Garantie."),
        "pl": ("Kup Teraz", "Jednorazowy zakup. Gwarancja 30 dni."),
    },
}

_SYSTEM_PROMPT = """Ты — эксперт по созданию прелендинг-страниц для affiliate-маркетинга.
Создаёшь высококонвертирующие HTML-страницы для nutra/betting офферов.

ТРЕБОВАНИЯ:
1. Полный валидный HTML5 с встроенным CSS (никаких внешних зависимостей)
2. Mobile-first дизайн (max-width 480px центрирован)
3. Быстрая загрузка (никаких тяжёлых библиотек, только vanilla JS если нужен)
4. Compliance: только разрешённые клеймы (см. правила для GEO/вертикали)
5. CTA кнопка ведёт на: LANDER_URL (placeholder для замены)
6. Никаких реальных медицинских клеймов (поддерживает / помогает — да, лечит — нет)

СТРУКТУРА ОТВЕТА:
Верни ТОЛЬКО HTML-код. Начни с <!DOCTYPE html>. Никакого объяснения."""


class PrelandingGenerator:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    async def generate(
        self,
        offer_name: str,
        vertical: str = "nutra",
        geo: str = "US",
        billing_model: str = "COD",
        format: str = "story",
        language: str | None = None,
        product_benefits: list[str] | None = None,
        target_audience: str = "",
        lander_url: str = "LANDER_URL",
    ) -> PrelandingResult:
        """
        Генерирует HTML прелендинг.

        Args:
            offer_name: Название продукта/оффера
            vertical: nutra|betting
            geo: US|BR|MX|DE|PL
            billing_model: COD|Trial|SS
            format: quiz|native_article|story|vsl
            language: en|pt|es|de|pl (если None — определяется по GEO)
            product_benefits: Список преимуществ продукта
            target_audience: Описание целевой аудитории
            lander_url: URL лендинга для CTA
        """
        lang = language or _LANGUAGE_MAP.get(geo, "en")
        benefits_str = "\n".join(f"- {b}" for b in (product_benefits or []))
        format_instructions = _FORMAT_PROMPTS.get(format, _FORMAT_PROMPTS["story"])

        cta_data = _BILLING_CTA.get(billing_model, _BILLING_CTA["COD"]).get(lang, _BILLING_CTA["COD"]["en"])
        cta_button, cta_sub = cta_data

        compliance = _COMPLIANCE_RULES.get(vertical, {}).get(geo, [])
        compliance_str = "\n".join(compliance)

        default_benefits = "- Натуральный состав\n- Видимый эффект за 30 дней\n- Тысячи довольных клиентов"
        user_msg = f"""Создай прелендинг для:
Продукт: {offer_name}
Вертикаль: {vertical}
GEO: {geo}
Язык: {lang}
Модель биллинга: {billing_model}
Формат: {format}
Целевая аудитория: {target_audience or "взрослые с проблемой в нише"}

Преимущества продукта:
{benefits_str or default_benefits}

CTA кнопка текст: "{cta_button}"
CTA подзаголовок: "{cta_sub}"
Ссылка в CTA: {lander_url}

ПРАВИЛА COMPLIANCE для {geo}/{vertical}:
{compliance_str}

{format_instructions}

Создай полный профессиональный HTML прелендинг. Используй реалистичный контент.
Сделай дизайн конвертирующим: контраст, читаемость, чёткий CTA."""

        resp = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        html_content = resp.content[0].text.strip()

        # Убираем markdown-обёртку если есть
        html_content = re.sub(r"^```(?:html)?\s*\n?", "", html_content)
        html_content = re.sub(r"\n?```\s*$", "", html_content)

        word_count = len(html_content.split())

        # Оценка CR по формату
        cr_map = {
            "quiz": "4–8%",
            "native_article": "2–5%",
            "story": "3–7%",
            "vsl": "5–10%",
        }

        funnel_tips = [
            f"Keitaro: добавь прелендинг как промежуточную ступень перед лендингом",
            f"A/B тест: создай 2–3 варианта заголовка для этого формата",
            f"GEO-локализация: убедись что язык ({lang}) совпадает с GEO ({geo}) аккаунта",
            f"Скорость: страница должна грузиться <2 сек — убери лишние скрипты",
            f"CTA кнопка '{cta_button}' должна быть видна без прокрутки (above the fold)",
        ]

        if billing_model == "Trial":
            funnel_tips.append("Trial: добавь заметный disclaimer о автосписании (требование FTC)")
        if geo == "US" and vertical == "nutra":
            funnel_tips.append("US Nutra: добавь 'Results may vary. These statements have not been evaluated by the FDA.'")

        return PrelandingResult(
            offer_name=offer_name,
            vertical=vertical,
            geo=geo,
            billing_model=billing_model,
            format=format,
            language=lang,
            html_content=html_content,
            word_count=word_count,
            estimated_cr=cr_map.get(format, "2–5%"),
            compliance_notes=compliance,
            funnel_tips=funnel_tips,
        )

    async def generate_variants(
        self,
        offer_name: str,
        vertical: str = "nutra",
        geo: str = "US",
        billing_model: str = "COD",
        formats: list[str] | None = None,
    ) -> list[PrelandingResult]:
        """Генерирует несколько вариантов прелендинга для A/B теста."""
        import asyncio
        formats = formats or ["story", "native_article"]
        tasks = [
            self.generate(offer_name, vertical, geo, billing_model, fmt)
            for fmt in formats
        ]
        return list(await asyncio.gather(*tasks))
