"""
Vertical Config Loader + AI Generator
Загружает конфиги вертикалей и генерирует новые через форму + Claude.
"""
from __future__ import annotations
import json, logging, os
from pathlib import Path
import yaml
from supabase import create_client, Client
from anthropic import AsyncAnthropic

from ubt_os.utils.llm_utils import response_text
from ubt_os.utils.supabase_utils import rows

logger = logging.getLogger("ubt_os.vertical_loader")

CONFIGS_DIR = Path(__file__).parent.parent.parent / "vertical_configs"


# ── Загрузчик ─────────────────────────────────────────────

class VerticalLoader:
    """Читает конфиги вертикалей из Supabase или файловой системы."""

    def __init__(self, db: Client):
        self.db    = db
        self._cache: dict[str, dict] = {}

    def get(self, vertical_id: str) -> dict | None:
        if vertical_id in self._cache:
            return self._cache[vertical_id]

        # 1. Попробовать Supabase
        row = rows(
            self.db.table("vertical_configs")
            .select("*")
            .eq("id", vertical_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if row:
            config = row[0]["config_yaml"]
            self._cache[vertical_id] = config
            return config

        # 2. Файловая система (fallback / dev)
        path = CONFIGS_DIR / f"{vertical_id}.yaml"
        if path.exists():
            config = yaml.safe_load(path.read_text())
            self._cache[vertical_id] = config
            return config

        logger.warning(f"Vertical config не найден: {vertical_id}")
        return None

    def list_active(self) -> list[dict]:
        return rows(
            self.db.table("vertical_configs")
            .select("id, name, category")
            .eq("status", "active")
            .execute()
        )

    def save(self, config: dict) -> str:
        vid = config["vertical"]["id"]
        self.db.table("vertical_configs").upsert({
            "id":          vid,
            "name":        config["vertical"]["name"],
            "category":    config["vertical"]["category"],
            "status":      config["vertical"].get("status", "active"),
            "config_yaml": config,
        }, on_conflict="id").execute()
        self._cache[vid] = config
        logger.info(f"Vertical config сохранён: {vid}")
        return vid


# ── AI Генератор конфига ──────────────────────────────────

GENERATOR_PROMPT = """Ты — архитектор контент-стратегий системы UBT OS.

На основе данных формы создай полный Vertical Config в формате YAML.
Верни СТРОГО YAML — без пояснений, без markdown-блоков, только YAML.

ПРАВИЛА:
- id: slug без пробелов, маленькими буквами, через _
- tone: конкретный, не абстрактный
- hook_patterns: 3 готовых хука-шаблона для этой ниши
- pain_points: 3 реальные боли аудитории
- forbidden_words: всё что может нарушить правила платформ
- platforms.tiktok_sensitivity: low/medium/high — исходя из ниши
  (adult, крипто, азартные игры = high; авто, еда, образование = low)
- Для lead_gen и direct_sales — заполнить секцию funnel
- Для affiliate — заполнить секцию affiliate

ДАННЫЕ ФОРМЫ:
{form_data}"""


class VerticalConfigGenerator:
    """Генерирует конфиг вертикали через Claude на основе формы."""

    def __init__(self):
        self.client = AsyncAnthropic()

    async def generate(self, form: dict) -> dict:
        """
        form = {
          "name": "Авто из Кореи",
          "category": "ecommerce",
          "geo": ["RU", "KZ"],
          "language": ["ru"],
          "audience_age": "28-45",
          "audience_gender": "male",
          "main_pain": "Не знают как купить авто за рубежом",
          "monetization_model": "lead_generation",
          "funnel_type": "full",
          "crm": "bitrix24",
          "platforms": ["tiktok", "youtube", "telegram"]
        }
        """
        prompt = GENERATOR_PROMPT.format(
            form_data=json.dumps(form, ensure_ascii=False, indent=2)
        )

        resp = await self.client.messages.create(
            model      = "claude-sonnet-5",
            max_tokens = 3000,
            messages   = [{"role": "user", "content": prompt}],
        )

        raw_yaml = response_text(resp).strip()
        # Убираем markdown-блоки если вдруг вернул
        if raw_yaml.startswith("```"):
            raw_yaml = "\n".join(raw_yaml.split("\n")[1:-1])

        config = yaml.safe_load(raw_yaml)
        logger.info(f"AI сгенерировал конфиг: {config.get('vertical',{}).get('id')}")
        return config


# ── AgentContext ──────────────────────────────────────────

class AgentContext:
    """Контекст вертикали, передаваемый всем агентам."""

    def __init__(self, config: dict):
        v = config.get("vertical", {})
        self.vertical_id   = v.get("id", "unknown")
        self.vertical_name = v.get("name", "")
        self.category      = v.get("category", "")

        a = config.get("audience", {})
        self.geo           = a.get("geo", [])
        self.language      = a.get("language", ["ru"])
        self.pain_points   = a.get("pain_points", [])
        self.desires       = a.get("desires", [])

        c = config.get("content", {})
        self.tone              = c.get("tone", "нейтральный")
        self.first_15_sec_rule = c.get("first_15_sec_rule", "")
        self.cta_style         = c.get("cta_style", "")
        self.forbidden_words   = c.get("forbidden_words", [])
        self.hook_patterns     = c.get("hook_patterns", [])

        p = config.get("platforms", {})
        self.platforms_allowed    = p.get("allowed", ["tiktok"])
        self.primary_platform     = p.get("primary", "tiktok")
        self.tiktok_sensitivity   = p.get("tiktok_sensitivity", "medium")
        self.posting_schedule     = p.get("posting_schedule", {})

        m = config.get("monetization", {})
        self.monetization_model = m.get("model", "affiliate_cpa")
        self.funnel_type        = m.get("funnel_type", "simple")
        self.funnel             = m.get("funnel", {})
        self.affiliate          = m.get("affiliate", {})

        s = config.get("seo", {})
        self.seed_keywords      = s.get("seed_keywords", [])
        self.hashtags_tiktok    = s.get("hashtags_tiktok", [])

    def to_prompt_vars(self) -> dict:
        """Словарь для подстановки в промпты агентов."""
        return {
            "vertical_name":      self.vertical_name,
            "category":           self.category,
            "tone":               self.tone,
            "audience_geo":       ", ".join(self.geo),
            "pain_points":        "\n".join(f"- {p}" for p in self.pain_points),
            "forbidden_words":    ", ".join(self.forbidden_words),
            "cta_style":          self.cta_style,
            "first_15_sec_rule":  self.first_15_sec_rule,
            "hook_examples":      "\n".join(self.hook_patterns[:3]),
            "monetization_model": self.monetization_model,
            "seed_keywords":      ", ".join(self.seed_keywords[:5]),
        }

    def allows_platform(self, platform: str) -> bool:
        return platform in self.platforms_allowed

    def is_affiliate(self) -> bool:
        return self.monetization_model in ("affiliate_cpa", "affiliate_revshare")

    def needs_full_funnel(self) -> bool:
        return self.funnel_type == "full"


# ── Точка входа для API ───────────────────────────────────

async def create_vertical_from_form(form: dict) -> dict:
    """
    POST /vertical/create
    Принимает форму → генерирует конфиг → сохраняет → возвращает config.
    """
    db        = create_client(os.environ["SUPABASE_URL"],
                              os.environ["SUPABASE_SERVICE_KEY"])
    generator = VerticalConfigGenerator()
    loader    = VerticalLoader(db)

    config  = await generator.generate(form)
    vid     = loader.save(config)
    context = AgentContext(config)

    return {
        "vertical_id": vid,
        "config":      config,
        "prompt_vars": context.to_prompt_vars(),
        "platforms":   context.platforms_allowed,
        "funnel_type": context.funnel_type,
    }


async def get_vertical_context(vertical_id: str) -> AgentContext | None:
    """Быстрое получение контекста для агентов."""
    db     = create_client(os.environ["SUPABASE_URL"],
                           os.environ["SUPABASE_SERVICE_KEY"])
    loader = VerticalLoader(db)
    config = loader.get(vertical_id)
    return AgentContext(config) if config else None
