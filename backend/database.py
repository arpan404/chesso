"""Durable web records. Each request commits all changes or none."""

import json
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path

from psycopg import ProgrammingError, RawCursor
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import set_json_loads
from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, created_at REAL NOT NULL, profile TEXT NOT NULL, clerk_id TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS activities (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL, state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
 category TEXT NOT NULL, kind TEXT NOT NULL, recorded_at REAL NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS activities_user ON activities(user_id, updated_at);
CREATE INDEX IF NOT EXISTS events_user ON events(user_id, recorded_at);
CREATE INDEX IF NOT EXISTS events_activity ON events(activity_id, recorded_at);
PRAGMA user_version = 1;
"""


class Database:
    def __init__(self, path: Path | None = None, *, url: str = ""):
        self.path = path
        self._pool = None
        self.backend = "postgresql" if url.strip() else "sqlite"
        if self.backend == "sqlite":
            if path is None:
                raise ValueError("A local database path or DATABASE_URL is required.")
            return
        # Validate without including credentials in error messages.
        try:
            if not url.strip().startswith(("postgresql://", "postgres://")):
                raise ValueError
            options = conninfo_to_dict(url.strip())
            if not options.get("host") or not options.get("dbname"):
                raise ValueError
        except (ValueError, ProgrammingError):
            raise ValueError(
                "DATABASE_URL must be a valid PostgreSQL connection URL."
            ) from None
        options.setdefault("sslmode", "require")
        if options["sslmode"] not in (
            "require",
            "verify-ca",
            "verify-full",
        ) and options.get("host") not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote PostgreSQL connections require TLS.")
        options.setdefault("connect_timeout", "10")
        options.setdefault("application_name", "chesso")
        self._pool = ConnectionPool(
            kwargs={
                **options,
                "autocommit": True,
                "cursor_factory": RawCursor,
                "row_factory": record_row,
                # Works with Neon's transaction pooler without session state.
                "prepare_threshold": None,
            },
            configure=configure_json,
            min_size=0,
            max_size=10,
            max_idle=60,
            timeout=15,
            open=False,
        )

    @property
    def research_consent_sql(self):
        if self.backend == "postgresql":
            return "users.profile->>'research_consent' = 'true'"
        return "json_extract(users.profile, '$.research_consent')=1"

    def initialize(self):
        if self._pool is not None:
            self._pool.open()
            try:
                with self.connect() as db:
                    # Serialize migration runners across API instances.
                    db.execute("SELECT pg_advisory_xact_lock(73973017858895)")
                    db.execute(
                        "CREATE TABLE IF NOT EXISTS schema_migrations ("
                        "version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, "
                        "applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                    )
                    applied = dict(
                        db.execute("SELECT version, checksum FROM schema_migrations")
                    )
                    for migration in sorted(
                        (Path(__file__).parent / "migrations").glob("*.sql")
                    ):
                        version = int(migration.name.split("_", 1)[0])
                        script = migration.read_text()
                        checksum = sha256(script.encode()).hexdigest()
                        if version in applied:
                            if applied[version] != checksum:
                                raise RuntimeError(
                                    "An applied database migration was modified."
                                )
                            continue
                        db.execute(script)
                        db.execute(
                            "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
                            (version, checksum),
                        )
            except BaseException:
                self.close()
                raise
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        if self._pool is not None:
            with self._pool.connection() as db, db.transaction():
                yield db
            return
        db = sqlite3.connect(
            self.path, timeout=15, check_same_thread=False, factory=SQLiteConnection
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def lock_user(self, db, clerk_id):
        if self._pool is not None:
            # Include first login: a row lock alone cannot lock a missing user.
            # Released on commit/rollback, including on a transaction pooler.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", (clerk_id,)
            )

    def close(self):
        if self._pool is not None:
            self._pool.close()


class Record(tuple):
    """The same named and positional row access as sqlite3.Row."""

    def __new__(cls, values, names):
        row = super().__new__(cls, values)
        row.names = names
        return row

    def __getitem__(self, key):
        return super().__getitem__(
            self.names.index(key) if isinstance(key, str) else key
        )

    def keys(self):
        return self.names


class SQLiteConnection(sqlite3.Connection):
    """Bind numbered SQL parameters by name, including on Python 3.14+."""

    def execute(self, statement, parameters=()):
        if isinstance(parameters, (tuple, list)):
            parameters = {str(i): value for i, value in enumerate(parameters, 1)}
        return super().execute(statement, parameters)


def record_row(cursor):
    names = tuple(column.name for column in cursor.description or ())
    return lambda values: Record(values, names)


def configure_json(db):
    # Keep the web service's JSON text interface while PostgreSQL stores JSONB.
    set_json_loads(lambda data: bytes(data).decode("utf-8"), db)


def event(db, user_id, activity_id, category, kind, **payload):
    db.execute(
        "INSERT INTO events VALUES ($1, $2, $3, $4, $5, $6, $7)",
        (
            uuid.uuid4().hex,
            user_id,
            activity_id,
            category,
            kind,
            time.time(),
            json.dumps(payload, allow_nan=False),
        ),
    )


def save_activity(db, activity_id, state):
    db.execute(
        "UPDATE activities SET state=$1, updated_at=$2 WHERE id=$3",
        (json.dumps(state, allow_nan=False), time.time(), activity_id),
    )
