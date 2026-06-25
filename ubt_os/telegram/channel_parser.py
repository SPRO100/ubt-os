"""
Парсер Telegram-каналов с открытыми комментариями.
Собирает каналы по ключевым словам/нише → сохраняет в Supabase как targets для T3-COMMENTER.
"""
from __future__ import annotations
import asyncio
import logging
import os
import urllib.request
import json
from datetime import datetime, timezone

logger = logging.getLogger("ubt_os.telegram.channel_parser")


class TelegramChannelParser:
    """Ищет каналы с открытыми комментами, пригодные для T3-COMMENTER."""

    def __init__(self, tg_client=None, supabase_url: str = "", supabase_key: str = ""):
        self.client    = tg_client
        self._supa_url = supabase_url or os.getenv("SUPABASE_URL", "")
        self._supa_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY", "")

    async def parse_by_keyword(self, keyword: str, vertical: str, limit: int = 20) -> dict:
        """
        Ищет каналы по ключевому слову через Telegram Search.
        Фильтрует только те, у которых открыты комментарии.
        Сохраняет найденные каналы в Supabase (channel_targets).
        """
        if not self.client:
            # Симуляция без реального клиента
            sample = [
                {"username": f"sample_{keyword}_channel_{i}", "title": f"Sample {keyword} {i}",
                 "subscribers": (i+1)*1000, "has_comments": True}
                for i in range(3)
            ]
            await self._save_targets(sample, keyword, vertical)
            logger.info(f"[PARSER] simulated {len(sample)} channels for '{keyword}'")
            return {"ok": True, "found": len(sample), "channels": sample}

        found = []
        try:
            from telethon.tl.functions.contacts import SearchRequest
            from telethon.tl.types import Channel

            result = await self.client(SearchRequest(q=keyword, limit=limit))
            chats = [c for c in result.chats if isinstance(c, Channel) and not c.megagroup]

            for chat in chats:
                try:
                    full = await self.client.get_entity(chat.username or chat.id)
                    # Проверяем открытость комментов через linked_chat
                    has_comments = bool(getattr(full, "linked_chat_id", None))
                    subs = getattr(chat, "participants_count", 0) or 0
                    if has_comments and subs >= 500:
                        found.append({
                            "username": chat.username or str(chat.id),
                            "title": chat.title,
                            "subscribers": subs,
                            "has_comments": True,
                        })
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"[PARSER] search error: {e}")
            return {"ok": False, "error": str(e)}

        if found:
            await self._save_targets(found, keyword, vertical)

        logger.info(f"[PARSER] found {len(found)} channels for '{keyword}'")
        return {"ok": True, "found": len(found), "channels": found}

    async def get_targets(self, vertical: str | None = None) -> list[dict]:
        """Возвращает список сохранённых target-каналов из Supabase."""
        if not self._supa_url:
            return []
        try:
            qs = "select=id,username,title,subscribers,vertical,keyword,parsed_at&order=parsed_at.desc&limit=100"
            if vertical:
                qs += f"&vertical=eq.{vertical}"
            url = f"{self._supa_url}/rest/v1/channel_targets?{qs}"
            req = urllib.request.Request(url)
            req.add_header("apikey", self._supa_key)
            req.add_header("Authorization", f"Bearer {self._supa_key}")
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as e:
            logger.warning(f"[PARSER] get_targets error: {e}")
            return []

    async def _save_targets(self, channels: list[dict], keyword: str, vertical: str):
        if not self._supa_url:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "username": c["username"],
                "title": c.get("title", ""),
                "subscribers": c.get("subscribers", 0),
                "has_comments": c.get("has_comments", True),
                "keyword": keyword,
                "vertical": vertical,
                "parsed_at": now,
            }
            for c in channels
        ]
        try:
            data = json.dumps(rows).encode()
            # upsert по username чтобы не дублировать
            url = f"{self._supa_url}/rest/v1/channel_targets"
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("apikey", self._supa_key)
            req.add_header("Authorization", f"Bearer {self._supa_key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"[PARSER] save_targets error: {e}")
