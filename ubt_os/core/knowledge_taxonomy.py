"""
Таксономия базы знаний UBT OS.

Единая система адресации знаний, чтобы и агенты, и оркестратор писали/читали
по одному ключу. Ключ записи (entry_key) строится как:

    <процесс>.<площадка>.<вертикаль>.<схема>

Примеры:
    zaliv.tiktok.nutra.grey        — серый залив на TikTok под нутру
    warmup.facebook.betting.black  — прогрев FB под беттинг, чёрная схема
    master_prompt.higgsfield.nutra.white — мастер-промт генерации UGC

Оси намеренно ограничены словарями ниже — чтобы ключи были предсказуемыми
и по ним можно было строить обзорные страницы (площадка × процесс × схема).
"""
from __future__ import annotations

# ── Оси таксономии ────────────────────────────────────────

PLATFORMS = {
    "tiktok":    "TikTok",
    "facebook":  "Facebook",
    "instagram": "Instagram",
    "youtube":   "YouTube Shorts",
    "pinterest": "Pinterest",
    "threads":   "Threads",
    "any":       "Кросс-платформенно",
}

# Процессы = этапы жизненного цикла залива
PROCESSES = {
    "zaliv":         "Залив трафика",
    "warmup":        "Прогрев аккаунтов",
    "master_prompt": "Мастер-промты генерации",
    "content":       "Производство контента",
    "prelanding":    "Прелендинги / клоака",
    "publishing":    "Публикация и UTM",
    "antiban":       "Антибан / антидетект",
    "analytics":     "Аналитика и атрибуция",
    "scaling":       "Масштабирование",
    "infra":         "Инфраструктура (прокси/SIM/фермы)",
}

# Схемы залива по «цвету шляпы»
SCHEMES = {
    "white": "⚪ White — в рамках правил площадок",
    "grey":  "🟡 Grey — обход мягких ограничений, серая зона",
    "black": "⚫ Black — высокорисковые техники, клоака, фарм",
}

VERTICALS = {
    "nutra":   "Nutra",
    "betting": "Betting",
    "both":    "Обе вертикали",
    "any":     "Вне вертикали",
}


def build_entry_key(process: str, platform: str = "any",
                    vertical: str = "any", scheme: str = "white") -> str:
    """Собирает канонический entry_key, валидируя оси по словарям."""
    if process not in PROCESSES:
        raise ValueError(f"неизвестный процесс: {process} (см. PROCESSES)")
    if platform not in PLATFORMS:
        raise ValueError(f"неизвестная площадка: {platform} (см. PLATFORMS)")
    if vertical not in VERTICALS:
        raise ValueError(f"неизвестная вертикаль: {vertical} (см. VERTICALS)")
    if scheme not in SCHEMES:
        raise ValueError(f"неизвестная схема: {scheme} (см. SCHEMES)")
    return f"{process}.{platform}.{vertical}.{scheme}"


def parse_entry_key(entry_key: str) -> dict:
    """Разбирает entry_key обратно в оси (для обзорных страниц/фильтров)."""
    parts = (entry_key or "").split(".")
    while len(parts) < 4:
        parts.append("any")
    process, platform, vertical, scheme = parts[:4]
    return {
        "process":  process,
        "platform": platform,
        "vertical": vertical,
        "scheme":   scheme,
        "process_label":  PROCESSES.get(process, process),
        "platform_label": PLATFORMS.get(platform, platform),
        "vertical_label": VERTICALS.get(vertical, vertical),
        "scheme_label":   SCHEMES.get(scheme, scheme),
    }


def vault_path_for(entry_key: str) -> str:
    """Путь в Obsidian-vault для записи знаний по её ключу."""
    ax = parse_entry_key(entry_key)
    return (f"50 Resources/knowledge/kb/{ax['process']}/"
            f"{ax['platform']}/{entry_key}.md")


def page_template(entry_key: str, title: str, content: str = "") -> str:
    """Markdown-шаблон страницы знаний с фронтматтером по таксономии."""
    ax = parse_entry_key(entry_key)
    return (
        "---\n"
        f"entry_key: {entry_key}\n"
        f"process: {ax['process']}\n"
        f"platform: {ax['platform']}\n"
        f"vertical: {ax['vertical']}\n"
        f"scheme: {ax['scheme']}\n"
        "tags: [kb, "
        f"{ax['process']}, {ax['platform']}, {ax['vertical']}, {ax['scheme']}]\n"
        "---\n\n"
        f"# {title}\n\n"
        f"> {ax['process_label']} · {ax['platform_label']} · "
        f"{ax['vertical_label']} · {ax['scheme_label']}\n\n"
        f"{content}\n"
    )


# Маппинг агент → process для автоматической загрузки KB в _run_agent
AGENT_PROCESS: dict[str, str] = {
    "content_creator":      "content",
    "text_humanizer":       "content",
    "youtube_creator":      "content",
    "higgsfield_agent":     "master_prompt",
    "trend_scraper":        "zaliv",
    "ads_auditor":          "zaliv",
    "spy_analyzer":         "zaliv",
    "competitor_analyst":   "zaliv",
    "trend_radar":          "zaliv",
    "competitor_scraper":   "zaliv",
    "compliance_gate":      "content",
    "prelanding_generator": "prelanding",
    "publer_publisher":     "publishing",
    "warmup_manager":       "warmup",
    "post_analytics_agent": "analytics",
}


def taxonomy_overview() -> dict:
    """Полная карта осей — для дашборда и обзорных страниц vault."""
    return {
        "platforms": PLATFORMS,
        "processes": PROCESSES,
        "schemes":   SCHEMES,
        "verticals": VERTICALS,
    }
