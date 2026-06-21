"""
Higgsfield Worker — запускается как отдельный Railway сервис.
Слушает Redis очередь и обрабатывает задачи генерации видео.

FIXES в этом файле (Sprint 1):
  FIX #2a — HiggsFieldWorker(redis_url) → HiggsFieldWorker(queue, higgsfield_api_key)
             Класс принимает HiggsFieldQueue + api_key, а не строку redis_url.
  FIX #2b — worker.run() → worker.run_forever()
             Метод в классе называется run_forever(), не run().
"""
import asyncio
import logging
import os
import sys

# Добавляем корень проекта в путь
sys.path.insert(0, "/app")

from ubt_os.pipelines.higgsfield_queue import HiggsFieldQueue, HiggsFieldWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [higgsfield_worker] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    redis_url = os.environ["REDIS_URL"]
    api_key   = os.environ["HIGGSFIELD_API_KEY"]

    # FIX #2a: создаём HiggsFieldQueue отдельно, передаём в worker
    # БЫЛО:   HiggsFieldWorker(redis_url)            ← TypeError
    # СТАЛО:  HiggsFieldQueue(redis_url) → worker(queue, api_key)
    queue  = HiggsFieldQueue(redis_url=redis_url)
    worker = HiggsFieldWorker(queue=queue, higgsfield_api_key=api_key)

    logger.info("Higgsfield Worker запущен ▶")

    # FIX #2b: метод run_forever(), не run()
    # БЫЛО:   await worker.run()           ← AttributeError
    # СТАЛО:  await worker.run_forever()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
