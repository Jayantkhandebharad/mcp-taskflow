"""Alembic environment — runs before every ``alembic upgrade`` / ``downgrade``.

Two things this file exists to do:

1. Point Alembic at the same database URL the app uses (via app.config), so
   there is exactly one source of truth for how we connect.
2. Point Alembic at our ``Base.metadata`` so ``alembic revision --autogenerate``
   can diff the models against the live schema.

We only implement the "online" mode — running against a real database
connection. The "offline" mode Alembic supports (emitting SQL to a file) is
occasionally useful for CI-managed migrations, but adds a code path we would
have to explain in phase 1 and isn't used by anything yet.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings

# Bringing every model into scope so it registers with Base.metadata.
from app.models import Base  # noqa: F401  (import for side effect)
import app.models  # noqa: F401

# Alembic's configuration object — populated from alembic.ini.
config = context.config

# Feed the URL Alembic uses from our own Settings. sqlalchemy.url in
# alembic.ini is deliberately empty; setting it here means one place decides
# how we connect to Postgres.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

# Wire up Python logging per the [loggers] sections in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# What Alembic diffs against on `--autogenerate`.
target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against a real database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool: Alembic opens exactly one connection, uses it once, and
        # exits. A real pool would just be extra machinery.
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # When autogenerate runs, treat a type change in the models as a
            # real change (default is False, which misses e.g. Text vs String).
            compare_type=True,
            # Same for server-side defaults.
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
