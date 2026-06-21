"""
Obsidian Cron — запускается каждый час через Railway cron.
Синхронизирует vault с GitHub используя FIX #10.
"""
import asyncio
import logging
import sys

sys.path.insert(0, "/app")
from ubt_os.core.pipeline_lock     import pipeline_lock
from ubt_os.utils.obsidian_git_sync import ObsidianSync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [obsidian_cron] %(levelname)s: %(message)s",
)

async def main():
    async with pipeline_lock("obsidian-sync", 60) as acquired:
        if not acquired:
            logging.info("Obsidian sync уже запущен, пропускаем")
            return
        sync = ObsidianSync()
        ok   = await sync.sync()
        logging.info(f"Sync результат: {'✅ OK' if ok else '❌ Ошибка'}")

if __name__ == "__main__":
    asyncio.run(main())
