# Todo

## Sprint 2 — выполнено ✅

- [x] Compliance Gate — `ubt_os/core/compliance_gate.py`, роут `/compliance/check`
- [x] Warmup Automation — платформо-специфичные лимиты и расписание в `warming_state_machine.py`
- [x] Keitaro postback — `KeitaroPostbackHandler` в `attribution.py`, роут `/keitaro/postback`
- [x] JSONDecodeError fix — валидация пустого тела в `main.py`
- [ ] Higgsfield Queue — на холде до оплаты Higgsfield
- [ ] Cross-platform Repurposing — на холде (зависит от Higgsfield)

## Следующие шаги (на approve)

- Настройка n8n воркфлоу для `/compliance/check` и `/keitaro/postback`
- SQL-миграция `conversion_events` в Supabase (если таблица не создана)
- Проверка логов после деплоя Sprint 2
