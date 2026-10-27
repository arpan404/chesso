"""Database selection, rollback, and opt-in PostgreSQL integration checks."""

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql

from backend.app import create_app
from backend.database import Database, event
from backend.migrate_sqlite import import_sqlite
from tests import test_web
from tests.test_web import test_identity


class DatabaseTests(unittest.TestCase):
    def test_configuration_and_local_test_isolation(self):
        url = "postgresql://test@localhost/test?sslmode=disable"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            app = create_app()
            self.assertEqual(app.state.database.backend, "postgresql")
            app.state.database.close()
            with tempfile.TemporaryDirectory() as directory:
                local = create_app(
                    Path(directory) / "test.sqlite3", auth_verifier=test_identity
                )
                self.assertEqual(local.state.database.backend, "sqlite")
                with TestClient(local) as client:
                    self.assertEqual(client.get("/api/health").status_code, 200)

    def test_invalid_url_fails_without_credentials_or_local_fallback(self):
        for url in (
            "https://user:private-password@example.com/db",
            "postgresql://invalid%",
        ):
            with self.assertRaises(ValueError) as error:
                create_app(database_url=url)
            self.assertNotIn(url, str(error.exception))
            self.assertNotIn("private-password", str(error.exception))
        with self.assertRaisesRegex(ValueError, "require TLS"):
            Database(
                url="postgresql://user:private-password@example.com/db?sslmode=disable"
            )

    def test_transaction_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.sqlite3")
            database.initialize()
            with self.assertRaises(RuntimeError), database.connect() as db:
                db.execute(
                    "INSERT INTO users VALUES ($1, $2, $3, $4)",
                    ("p", 0, "{}", "user_p"),
                )
                event(db, "p", None, "essential", "profile_created")
                raise RuntimeError("An action failed")
            with database.connect() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0
                )


# Never reuse DATABASE_URL: tests create and delete an isolated random schema.
TEST_URL = os.environ.get("CHESSO_TEST_DATABASE_URL", "")


class PostgresSchemaMixin:
    def setUp(self):
        self.schema = "chesso_test_" + uuid.uuid4().hex
        with psycopg.connect(TEST_URL, autocommit=True) as db:
            db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        parts = urlsplit(TEST_URL)
        options = dict(parse_qsl(parts.query))
        options["options"] = "-csearch_path=" + self.schema
        self.database_url = urlunsplit(parts._replace(query=urlencode(options)))
        super().setUp()

    def drop_schema(self):
        with psycopg.connect(TEST_URL, autocommit=True) as db:
            db.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))
            )

    def make_app(self):
        return create_app(
            database_url=self.database_url,
            admin_token="research-test",
            auth_verifier=test_identity,
        )


@unittest.skipUnless(TEST_URL, "Set CHESSO_TEST_DATABASE_URL for PostgreSQL checks")
class PostgresWebTests(PostgresSchemaMixin, test_web.WebTests):
    def test_transactions_roll_back_moves_and_events_together(self):
        user = self.client.get("/api/me").json()
        database = self.app.state.database
        with self.assertRaises(RuntimeError), database.connect() as db:
            db.execute(
                "UPDATE users SET profile=$1 WHERE id=$2",
                ('{"points":999}', user["id"]),
            )
            event(db, user["id"], None, "essential", "failed_action")
            raise RuntimeError("An action failed")
        self.assertEqual(self.client.get("/api/me").json()["points"], 0)
        self.assertFalse(
            any(
                e["kind"] == "failed_action"
                for e in self.client.get("/api/me/export").json()["events"]
            )
        )

    def test_migrations_are_idempotent_across_instances(self):
        profile = self.client.get("/api/me").json()
        with TestClient(self.make_app()) as restarted:
            result = restarted.get(
                "/api/me", headers={"Authorization": "Bearer alice"}
            ).json()
            self.assertEqual(result["id"], profile["id"])
        with self.app.state.database.connect() as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1
            )

    def seed_legacy(self):
        local = create_app(
            self.path, admin_token="research-test", auth_verifier=test_identity
        )
        with TestClient(local) as client:
            client.headers["Authorization"] = "Bearer alice"
            client.patch(
                "/api/me", json={"research_consent": True, "analytics_consent": True}
            )
            puzzle = client.post("/api/puzzles", json={"tier": "medium"}).json()
            client.post(
                f"/api/puzzles/{puzzle['id']}/hint", json={"version": puzzle["version"]}
            )
            client.post("/api/studies")
            return client.get("/api/me/export").json()

    def test_import_preserves_ids_json_events_and_session_progress(self):
        before = self.seed_legacy()
        counts = import_sqlite(self.path, self.app.state.database)
        after = self.client.get("/api/me/export").json()
        self.assertEqual(before["profile"], after["profile"])
        for kind in ("activities", "events"):
            self.assertEqual(
                sorted(before[kind], key=lambda row: row["id"]),
                sorted(after[kind], key=lambda row: row["id"]),
            )
            self.assertEqual(counts[kind], len(before[kind]))
        self.assertEqual(counts["users"], 1)
        self.assertIn(
            "puzzle_hint_shown",
            self.client.get(
                "/api/research/export",
                headers={"Authorization": "Bearer research-test"},
            ).text,
        )

    def test_import_refuses_existing_records(self):
        self.seed_legacy()
        before = self.client.get("/api/me/export").json()
        with self.assertRaisesRegex(ValueError, "destination must be empty"):
            import_sqlite(self.path, self.app.state.database)
        self.assertEqual(before, self.client.get("/api/me/export").json())

    def test_invalid_import_rolls_back_all_records(self):
        self.seed_legacy()
        legacy = Database(self.path)
        with legacy.connect() as db:
            db.execute("UPDATE events SET payload='not json'")
        with self.assertRaises(psycopg.errors.InvalidTextRepresentation):
            import_sqlite(self.path, self.app.state.database)
        with self.app.state.database.connect() as db:
            for table in ("users", "activities", "events"):
                self.assertEqual(
                    db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
