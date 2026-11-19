from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from invoice_agent.persistence.job_repository import Job


async def claim_next_job(
    session: AsyncSession, worker_id: str, lease_seconds: int = 60
) -> Job | None:
    now = datetime.now(UTC)
    statement = (
        select(Job)
        .where(
            or_(
                and_(Job.state.in_(["queued", "retry"]), Job.next_attempt_at <= now),
                and_(Job.state == "leased", Job.lease_expires_at < now),
            ),
        )
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.execute(statement)).scalar_one_or_none()
    if job is None:
        return None
    job.state = "leased"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    await session.flush()
    return job


async def enqueue_job(session: AsyncSession, tenant_id: UUID, invoice_id: UUID, stage: str) -> Job:
    job = Job(tenant_id=tenant_id, invoice_id=invoice_id, stage=stage, state="queued")
    session.add(job)
    await session.flush()
    return job
