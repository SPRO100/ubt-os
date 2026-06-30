#!/usr/bin/env python3
"""
FIX #10: Obsidian Vault — Git Sync с conflict resolution
=========================================================
Проблема: obsidian-sync (PyPI) перезаписывает файлы при
одновременном редактировании (Claude + пользователь вручную).
Нет merge-логики → потеря данных.

Решение:
  - git-based sync (pull → merge → commit → push)
  - Конфликты → НЕ автомёрж → алерт в Telegram
  - Часовой cron через n8n
  - Лок на время синхронизации (Fix #3)
"""

from __future__ import annotations
import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import httpx

logger = logging.getLogger("obsidian.sync")

VAULT_PATH    = Path(os.getenv("OBSIDIAN_VAULT_PATH", "/app/obsidian-vault"))
REMOTE_URL    = os.getenv("OBSIDIAN_REMOTE_URL", "")       # GitHub HTTPS с токеном
BRANCH        = os.getenv("OBSIDIAN_BRANCH", "main")
COMMIT_AUTHOR = "UBT OS Agent <agent@ubt-os.local>"
LOCK_FILE     = VAULT_PATH / ".sync_lock"


# ══════════════════════════════════════════════════════════
# 1. GIT HELPER
# ══════════════════════════════════════════════════════════

def git(*args, cwd: Path = VAULT_PATH, check: bool = True) -> subprocess.CompletedProcess:
    """Запускает git команду."""
    cmd = ["git", *args]
    logger.debug(f"[Git] {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def git_out(*args, cwd: Path = VAULT_PATH) -> str:
    """Запускает git и возвращает stdout."""
    return git(*args, cwd=cwd).stdout.strip()


# ══════════════════════════════════════════════════════════
# 2. SYNC ENGINE
# ══════════════════════════════════════════════════════════

class ObsidianSync:
    """
    Git-based синхронизация Obsidian vault.
    Конфликты = алерт, не автомёрж.
    """

    def __init__(self, vault_path: Path = VAULT_PATH):
        self.vault = vault_path

    async def sync(self) -> dict:
        """
        Полный цикл синхронизации:
        stash → pull → apply stash → commit → push
        """
        if not self.vault.exists():
            return {"status": "error", "message": f"Vault не найден: {self.vault}"}

        if LOCK_FILE.exists():
            return {"status": "skipped", "message": "Sync уже выполняется"}

        LOCK_FILE.touch()
        try:
            return await self._do_sync()
        finally:
            LOCK_FILE.unlink(missing_ok=True)

    async def _do_sync(self) -> dict:
        now = datetime.now(timezone.utc)

        # 1. Инициализируем git если нужно
        if not (self.vault / ".git").exists():
            await self._init_repo()

        # 2. Настройка автора
        git("config", "user.email", "agent@ubt-os.local")
        git("config", "user.name",  "UBT OS Agent")

        # 3. Stash локальных изменений
        status = git_out("status", "--porcelain")
        has_local_changes = bool(status)
        stashed = False

        if has_local_changes:
            result = git("stash", "push", "-m", f"auto-stash {now.isoformat()}", check=False)
            stashed = result.returncode == 0
            logger.info(f"[Sync] Stash: {'OK' if stashed else 'пусто'}")

        # 4. Pull с remote
        pull_result = git("pull", "--rebase", "origin", BRANCH, check=False)
        if pull_result.returncode != 0:
            await self._handle_conflict(pull_result.stderr)
            if stashed:
                git("stash", "pop", check=False)
            return {
                "status":  "conflict",
                "message": "Конфликт при pull. Требуется ручное разрешение.",
                "stderr":  pull_result.stderr,
            }

        # 5. Применяем stash обратно
        if stashed:
            stash_result = git("stash", "pop", check=False)
            if stash_result.returncode != 0:
                # Конфликт stash ↔ remote
                await self._handle_conflict(stash_result.stderr)
                git("stash", "drop", check=False)
                return {
                    "status":  "conflict",
                    "message": "Конфликт при применении локальных изменений.",
                    "stderr":  stash_result.stderr,
                }

        # 6. Коммитим всё что есть
        status_after = git_out("status", "--porcelain")
        committed = False
        if status_after:
            git("add", "-A")
            commit_msg = f"auto-sync {now.strftime('%Y-%m-%d %H:%M')} UTC"
            git("commit", "-m", commit_msg, check=False)
            committed = True
            logger.info(f"[Sync] Committed: {commit_msg}")

        # 7. Push
        push_result = git("push", "origin", BRANCH, check=False)
        if push_result.returncode != 0:
            logger.error(f"[Sync] Push failed: {push_result.stderr}")
            await _send_telegram_alert(
                f"⚠️ OBSIDIAN SYNC: push failed\n{push_result.stderr[:300]}"
            )
            return {"status": "push_failed", "stderr": push_result.stderr}

        # 8. Статистика
        changed_files = len(status_after.splitlines()) if status_after else 0
        stats = {
            "status":        "ok",
            "committed":     committed,
            "changed_files": changed_files,
            "synced_at":     now.isoformat(),
        }
        logger.info(f"[Sync] ✅ OK | изменено файлов: {changed_files}")
        return stats

    async def _init_repo(self):
        """Инициализирует git репозиторий если не существует."""
        logger.info(f"[Sync] Инициализация git в {self.vault}")
        git("init", "-b", BRANCH)
        if REMOTE_URL:
            git("remote", "add", "origin", REMOTE_URL)
        git("add", "-A")
        git("commit", "-m", "init: vault initial commit", check=False)

    async def _handle_conflict(self, stderr: str):
        """Обрабатывает конфликт: алерт + abort rebase."""
        git("rebase", "--abort", check=False)
        logger.error(f"[Sync] ❌ Конфликт: {stderr[:200]}")
        await _send_telegram_alert(
            "🆘 OBSIDIAN SYNC КОНФЛИКТ\n"
            "Обнаружен конфликт слияния.\n"
            "Действие: автомёрж ОТМЕНЁН, требуется ручное разрешение.\n\n"
            f"Детали:\n{stderr[:400]}\n\n"
            "Команды для разрешения:\n"
            f"```\ncd {self.vault}\ngit status\ngit mergetool\ngit rebase --continue\n```"
        )

    def get_file_history(self, relative_path: str, max_entries: int = 10) -> list[dict]:
        """Возвращает историю изменений файла."""
        log = git_out(
            "log", f"-{max_entries}",
            "--pretty=format:%H|%ai|%s|%an",
            "--", relative_path
        )
        if not log:
            return []
        entries = []
        for line in log.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                entries.append({
                    "commit":    parts[0][:8],
                    "date":      parts[1],
                    "message":   parts[2],
                    "author":    parts[3],
                })
        return entries

    def restore_file(self, relative_path: str, commit_hash: str) -> bool:
        """Восстанавливает файл к указанному коммиту."""
        try:
            git("checkout", commit_hash, "--", relative_path)
            logger.info(f"[Sync] Восстановлен {relative_path} к {commit_hash[:8]}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"[Sync] Ошибка восстановления: {e}")
            return False


# ══════════════════════════════════════════════════════════
# 3. n8n ВОРКФЛОУ: OBSIDIAN SYNC (каждый час)
# ══════════════════════════════════════════════════════════

N8N_SYNC_WORKFLOW = """
// n8n Execute Code Node: obsidian-sync
// Cron: 0 * * * * (каждый час)
// Запускает Python скрипт синхронизации через SSH/exec

const result = await $execution.helpers.request({
  method: 'POST',
  url: process.env.OBSIDIAN_SYNC_WEBHOOK_URL,
  body: { action: 'sync' },
  json: true,
});

if (result.status === 'conflict') {
  // Telegram алерт уже отправлен из Python
  return [{ json: { status: 'conflict', requires_action: true } }];
}

return [{ json: result }];
"""


# ══════════════════════════════════════════════════════════
# УТИЛИТА
# ══════════════════════════════════════════════════════════

async def _send_telegram_alert(text: str):
    bot_token = os.getenv("TELEGRAM_ALERT_BOT_TOKEN")
    chat_id   = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    if not bot_token or not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            )
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(ObsidianSync().sync())
    print(result)
