"""
migrations/env.py
Wired to the Veritas-Audit SQLModel metadata so Alembic can autogenerate
migration scripts from the model definitions in src/core/db.py.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

# Import all models so their metadata is registered before autogenerate runs.
import src.core.db  # noqa: F401  — registers AuditLog on SQLModel.metadata

from src.core.db import _engine

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Interpret the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point autogenerate at our SQLModel metadata.
target_metadata = SQLModel.metadata


# ---------------------------------------------------------------------------
# Run migrations offline (no live DB connection needed)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Run migrations online (uses the existing engine from db.py)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    with _engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
