import asyncio
import logging
import os
import signal

from invoice_agent.persistence.database import SessionFactory
from invoice_agent.services.invoice_worker import process_extraction_job
from invoice_agent.worker.queue import claim_next_job

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    worker_id = os.environ.get("WORKER_ID", f"worker-{os.getpid()}")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopping.set)
    while not stopping.is_set():
        async with SessionFactory() as session:
            job = await claim_next_job(session, worker_id)
            if job is None:
                await session.rollback()
                try:
                    await asyncio.wait_for(stopping.wait(), timeout=1.0)
                except TimeoutError:
                    pass
                continue
            job_id = job.id
            await session.commit()
        try:
            async with SessionFactory() as session:
                await process_extraction_job(session, job_id, worker_id)
        except Exception:
            logger.exception("Worker task failed", extra={"job_id": str(job_id)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass
