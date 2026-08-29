from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_every_table_has_row_level_security_enabled(postgres_container, monkeypatch):
    """
    Supabase auto-exposes every public-schema table through PostgREST to
    anyone holding the project's anon key, and that key is public (it ships
    in the frontend's JS bundle). RLS is the only thing that closes that
    path — the app itself never needs it, since the backend connects
    directly as the table-owning role, which bypasses RLS regardless.

    This runs the real Alembic migration chain against a scratch database,
    not `Base.metadata.create_all` (what the rest of the suite uses via the
    shared `test_engine` fixture) — `create_all` only knows about ORM
    column/constraint definitions, not migration-only DDL like RLS grants.
    A future migration that creates a table without enabling RLS on it
    fails here before it ships.
    """
    admin_url = postgres_container.get_connection_url(driver="psycopg")
    db_name = "rls_check"

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
    finally:
        admin_engine.dispose()

    check_url = admin_url.rsplit("/", 1)[0] + f"/{db_name}"
    monkeypatch.setenv("DATABASE_URL", check_url)

    api_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "migrations"))
    command.upgrade(cfg, "head")

    check_engine = create_engine(check_url)
    try:
        with check_engine.connect() as conn:
            unprotected = conn.execute(
                text(
                    "select relname from pg_class "
                    "where relnamespace = 'public'::regnamespace "
                    "and relkind = 'r' "
                    "and relrowsecurity = false"
                )
            ).scalars().all()
    finally:
        check_engine.dispose()

    assert unprotected == [], (
        f"{unprotected} have no row-level security enabled. Add "
        "`ALTER TABLE <table> ENABLE ROW LEVEL SECURITY` to the migration "
        "that creates the table — see 002_enable_row_level_security.py."
    )
