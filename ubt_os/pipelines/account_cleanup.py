"""
Каскадное удаление аккаунта — для дашборда, когда обычный DELETE упирается
в внешний ключ (content_plans/videos/publications ссылаются на accounts.id).

Порядок обусловлен зависимостями FK: сначала publications (ссылается на
videos и accounts), затем videos (ссылается на content_plans и accounts;
у уникализированных копий на ДРУГИХ аккаунтах parent_video_id отвязывается,
а не удаляется — они не принадлежат удаляемому аккаунту), затем
content_plans, и только потом сама строка accounts.

Запуск: POST /accounts/delete-cascade {"account_id": "...", "dry_run": true|false}
"""
from __future__ import annotations

import logging

from ubt_os.core.agent_api_layer import get_db
from ubt_os.utils.supabase_utils import rows

logger = logging.getLogger("ubt_os.account_cleanup")


def _dependent_video_ids(account_id: str, plan_ids: list[str]) -> list[str]:
    ids: set[str] = {
        r["id"] for r in rows(get_db().table("videos").select("id").eq("account_id", account_id).execute())
    }
    if plan_ids:
        ids |= {
            r["id"] for r in rows(
                get_db().table("videos").select("id").in_("content_plan_id", plan_ids).execute()
            )
        }
    return list(ids)


async def delete_account_cascade(account_id: str, dry_run: bool = True) -> dict:
    """Считает (dry_run=True) или реально удаляет (dry_run=False) все записи,
    зависящие от аккаунта, и сам аккаунт."""
    db = get_db()

    plan_ids = [r["id"] for r in rows(
        db.table("content_plans").select("id").eq("account_id", account_id).execute()
    )]
    video_ids = _dependent_video_ids(account_id, plan_ids)

    pub_ids: set[str] = {
        r["id"] for r in rows(db.table("publications").select("id").eq("account_id", account_id).execute())
    }
    if video_ids:
        pub_ids |= {
            r["id"] for r in rows(
                db.table("publications").select("id").in_("video_id", video_ids).execute()
            )
        }

    counts = {
        "content_plans": len(plan_ids),
        "videos": len(video_ids),
        "publications": len(pub_ids),
    }

    if dry_run:
        return {"status": "dry_run", "account_id": account_id, "counts": counts}

    if pub_ids:
        db.table("publications").delete().in_("id", list(pub_ids)).execute()
    if video_ids:
        # копии на ДРУГИХ аккаунтах не удаляем — только отвязываем ссылку на родителя
        db.table("videos").update({"parent_video_id": None}).in_("parent_video_id", video_ids).execute()
        db.table("videos").delete().in_("id", video_ids).execute()
    if plan_ids:
        db.table("content_plans").delete().in_("id", plan_ids).execute()

    # best-effort — таблицы прямой публикации хранят account_id без FK-констрейнта
    for table in ("direct_publish_jobs", "direct_publish_accounts"):
        try:
            db.table(table).delete().eq("account_id", account_id).execute()
        except Exception as e:
            logger.warning("account_cleanup: %s не очищена для %s: %s", table, account_id, e)

    db.table("accounts").delete().eq("id", account_id).execute()

    logger.info("account_cleanup: удалён %s (%s)", account_id, counts)
    return {"status": "deleted", "account_id": account_id, "counts": counts}
