# UBT OS — Makefile
# Использование: make <команда>

.PHONY: help setup db-init up down logs build deploy-railway test lint

help:
	@echo "UBT OS — команды деплоя"
	@echo ""
	@echo "  make setup          — первый запуск: .env + зависимости"
	@echo "  make db-init        — применить SQL схему (FIX #1)"
	@echo "  make up             — запустить все сервисы"
	@echo "  make down           — остановить все сервисы"
	@echo "  make logs           — смотреть логи"
	@echo "  make build          — пересобрать Docker образ"
	@echo "  make deploy-railway — задеплоить на Railway"
	@echo "  make test-lock      — протестировать Redis lock"
	@echo "  make test-budget    — проверить LiteLLM бюджет"
	@echo "  make fixes-status   — статус применения фиксов"

# ── ПЕРВЫЙ ЗАПУСК ────────────────────────────────────────────
setup:
	@echo "⚙️  Настройка UBT OS..."
	@if [ ! -f .env ]; then cp .env.template .env; echo "✅ .env создан — заполни значения!"; fi
	pip install -r deploy/requirements.txt
	@echo ""
	@echo "📝 Следующий шаг: заполни .env и запусти 'make db-init'"

# ── БАЗА ДАННЫХ ──────────────────────────────────────────────
db-init:
	@echo "🗄️  Применяем все SQL схемы (FIX #4: было только 01_schema_sot.sql)..."
	@if [ -z "$(DATABASE_URL)" ]; then \
		export $$(cat .env | xargs); \
	fi
	@echo "  [1/13] 01_schema_sot.sql"
	psql $${DATABASE_URL} -f deploy/01_schema_sot.sql
	@echo "  [2/13] strategy_schema.sql"
	psql $${DATABASE_URL} -f deploy/strategy_schema.sql
	@echo "  [3/13] revenue_schema.sql"
	psql $${DATABASE_URL} -f deploy/revenue_schema.sql
	@echo "  [4/13] risk_schema.sql"
	psql $${DATABASE_URL} -f deploy/risk_schema.sql
	@echo "  [5/13] vertical_schema.sql"
	psql $${DATABASE_URL} -f deploy/vertical_schema.sql
	@echo "  [6/13] creative_vault_schema.sql"
	psql $${DATABASE_URL} -f deploy/creative_vault_schema.sql
	@echo "  [7/13] recovery_schema.sql"
	psql $${DATABASE_URL} -f deploy/recovery_schema.sql
	@echo "  [8/13] 02_patch_missing_tables.sql"
	psql $${DATABASE_URL} -f deploy/02_patch_missing_tables.sql
	@echo "  [9/13] 03_patch_knowledge_entries.sql"
	psql $${DATABASE_URL} -f deploy/03_patch_knowledge_entries.sql
	@echo "  [10/13] 04_patch_competitor_patterns.sql"
	psql $${DATABASE_URL} -f deploy/04_patch_competitor_patterns.sql
	@echo "  [11/13] 05_patch_projects_chat.sql  ← chat_messages + vertical_id"
	psql $${DATABASE_URL} -f deploy/05_patch_projects_chat.sql
	@echo "  [12/13] dohoo_features_schema.sql  ← hook_templates, transcriptions, direct_publish_*"
	psql $${DATABASE_URL} -f deploy/dohoo_features_schema.sql
	@echo "  [13/13] 06_patch_accounts_align.sql  ← id TEXT + facebook/pinterest + publer/proxy колонки"
	psql $${DATABASE_URL} -f deploy/06_patch_accounts_align.sql
	@echo "✅ Все 13 схем применены"

apply-schema:
	psql $${DATABASE_URL} -f $(SCHEMA)

# ── DOCKER ──────────────────────────────────────────────────
build:
	docker-compose build --no-cache agents higgsfield_worker

up:
	@echo "🚀 Запуск UBT OS..."
	docker-compose up -d
	@echo "✅ Сервисы запущены:"
	@docker-compose ps

down:
	docker-compose down

logs:
	docker-compose logs -f --tail=100

logs-agents:
	docker-compose logs -f agents

logs-litellm:
	docker-compose logs -f litellm

restart:
	docker-compose restart agents higgsfield_worker

# ── ТЕСТЫ ───────────────────────────────────────────────────
test:
	@echo "🧪 Запуск unit-тестов..."
	pytest tests/ -v --tb=short

lint:
	@echo "🔍 Линтинг кода..."
	ruff check ubt_os/

test-lock:
	@echo "🔒 Тест Redis Lock..."
	@export $$(cat .env | xargs) && \
	python -c "import asyncio; from ubt_os.core import pipeline_lock; \
	async def t(): \
	    async with pipeline_lock('test', 10) as ok: print('Lock:', ok); \
	asyncio.run(t())"

test-budget:
	@echo "💰 Проверка LiteLLM бюджета..."
	@export $$(cat .env | xargs) && \
	python -c "import asyncio,os; from ubt_os.core.budget_guard import BudgetGuard; \
	guard = BudgetGuard(os.environ['LITELLM_BASE_URL'], os.environ['LITELLM_MASTER_KEY']); \
	usage = asyncio.run(guard.get_usage_today()); print(usage)"

test-warming:
	@echo "🌡️  Тест State Machine..."
	@export $$(cat .env | xargs) && \
	python -c "from ubt_os.agents import WarmingStateMachine; print('WarmingStateMachine OK')"

# ── RAILWAY ДЕПЛОЙ ──────────────────────────────────────────
deploy-railway:
	@echo "🚂 Деплой на Railway..."
	@command -v railway >/dev/null || (echo "Установи Railway CLI: npm install -g @railway/cli" && exit 1)
	railway up

# ── СТАТУС ФИКСОВ ───────────────────────────────────────────
fixes-status:
	@echo "🔧 Статус 12 фиксов UBT OS:"
	@echo ""
	@echo "FIX #1  SOT Schema    — deploy/01_schema_sot.sql + ubt_os/core/agent_api_layer.py"
	@echo "FIX #2  Circuit Break — ubt_os/core/circuit_breaker.py"
	@echo "FIX #3  Lock          — ubt_os/core/pipeline_lock.py + n8n/workflows/"
	@echo "FIX #4  Warming FSM   — ubt_os/agents/warming_state_machine.py"
	@echo "FIX #5  Checker       — ubt_os/agents/account_checker.py"
	@echo "FIX #6  LiteLLM       — deploy/litellm_config.yaml + ubt_os/core/budget_guard.py"
	@echo "FIX #7  Higgs Queue   — ubt_os/pipelines/higgsfield_queue.py"
	@echo "FIX #8  TG Jitter     — ubt_os/agents/telegram_jitter.py"
	@echo "FIX #9  KB Version    — ubt_os/core/knowledge_base.py"
	@echo "FIX #10 Obsidian Sync — ubt_os/utils/obsidian_git_sync.py"
	@echo "FIX #11 Blotato DLQ   — ubt_os/pipelines/blotato_dlq.py"
	@echo "FIX #12 Attribution   — ubt_os/utils/attribution.py"
	@echo ""
	@echo "📋 Порядок применения: #3 → #6 → #2 → #1 → #4 → #5 → #11 → #8 → #7 → #10 → #9 → #12"
