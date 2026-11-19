from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from invoice_agent.config import settings
from invoice_agent.persistence import (
    chat_models,  # noqa: F401
    invoice_models,  # noqa: F401
    job_repository,  # noqa: F401
    review_models,  # noqa: F401
    validation_models,  # noqa: F401
    workbook_models,  # noqa: F401
)
from invoice_agent.persistence.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.replace("+asyncpg", "+psycopg"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    migration_url = settings.database_url.replace("+asyncpg", "+psycopg")
    connectable = create_engine(migration_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
