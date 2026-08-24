"""Fixture and local transport support for installed database qualification."""

import hashlib
import http.cookiejar
import json
import os
import sqlite3
import threading
import urllib.request
from datetime import datetime, timedelta, timezone

from fam_os.adapters.database import sqlite_data_digest, sqlite_schema_digest
from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.core.engineering import (
    DatabaseChangePlan, DatabaseEngine, DatabaseEnvironment, DatabaseFixtureSet,
    DatabaseMigrationStep, DatabaseTarget, EngineeringAuthority,
    EngineeringAuthorityGrant, EngineeringDelegationMode, EngineeringGrantScope,
    EngineeringGrantScopeKind, EngineeringResourceImpact, GrantLifecycleState,
    OwnerGrantApproval, ReversibilityPolicy, SecretExposurePolicy,
    VerificationRequirement,
)
from fam_os.core.engineering.grant_policy import engineering_grant_digest
from fam_os.core.engineering.transactions import CandidateWorkspace
from fam_os.product.engineering_authority_api import ProductEngineeringAuthorityApi
from fam_os.schemas import encode_document


def authority_api(storage, owner_id):
    assert storage.engineering_grants is not None
    assert storage.engineering_authentication is not None
    assert storage.engineering_authorizer is not None
    return ProductEngineeringAuthorityApi(
        owner_id, storage.engineering_grants,
        storage.engineering_authentication, storage.engineering_authorizer,
    )


def database_fixture(root):
    database = root / "app.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT",
    )
    connection.commit()
    baseline_schema = sqlite_schema_digest(connection)
    baseline_data = sqlite_data_digest(connection)
    connection.close()
    forward_sql = b"CREATE TABLE notes(id INTEGER PRIMARY KEY, body TEXT NOT NULL) STRICT;"
    forward = _write(root, "db/001.sql", forward_sql)
    rollback = _write(root, "db/001_down.sql", b"DROP TABLE notes;")
    fixture = _write(root, "db/fixtures.json", json.dumps({
        "tables": [{
            "name": "notes", "columns": ["id", "body"],
            "rows": [[1, "hello"]],
        }],
    }, separators=(",", ":")).encode())
    expected = sqlite3.connect(":memory:")
    expected.execute(
        "CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT",
    )
    expected.execute(forward_sql.decode())
    expected_schema = sqlite_schema_digest(expected)
    expected.close()
    target = DatabaseTarget(
        "database-1", DatabaseEngine.SQLITE, DatabaseEnvironment.CANDIDATE,
        "app.db", None, "candidate-host-1", False,
    )
    impact = EngineeringResourceImpact(300, 1, 0, 4, 16_777_216, 0)
    plan = DatabaseChangePlan(
        "database-plan-1", "task-1", "candidate-1", target,
        baseline_schema, baseline_data,
        (DatabaseMigrationStep(
            "migration-1", 1, "db/001.sql", forward,
            "db/001_down.sql", rollback, False, True, expected_schema,
        ),),
        DatabaseFixtureSet(
            "fixtures-1", "db/fixtures.json", fixture, 1, True, False,
        ),
        True, True, ("schema-match", "foreign-keys", "transaction-test"),
        (EngineeringAuthority.EXECUTE, EngineeringAuthority.MODIFY), impact,
        "changeset-1", now(),
    )
    candidate = CandidateWorkspace(
        plan.candidate_id, plan.task_id, "baseline-1", str(root.parent / "owner"),
        str(root), now(), "copy", "a" * 64, (),
    )
    return plan, candidate


def engineering_grant(owner_id, plan, candidate):
    instant = now()
    return EngineeringAuthorityGrant(
        "grant-database-1", owner_id, "fam-core",
        EngineeringDelegationMode.CUSTOM,
        (EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE),
        EngineeringGrantScope(
            EngineeringGrantScopeKind.TASK, plan.task_id,
            (candidate.owner_workspace,), (plan.target.database_name,), (),
            ("sqlite",), (), (), (), (), (),
        ),
        "Apply and verify the exact candidate database migration",
        instant - timedelta(seconds=1), instant + timedelta(minutes=20),
        GrantLifecycleState.ACTIVE, ReversibilityPolicy.REQUIRED,
        SecretExposurePolicy.NONE, VerificationRequirement.REQUIRED,
        plan.execution_resource_impact,
    )


class ConsoleAuthorityClient:
    def __init__(
        self, root, api, integration_environment_api=None,
        engineering_secret_api=None,
    ):
        root.mkdir(mode=0o700)
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(root), "x" * 32,
            engineering_authority_api=api,
            integration_environment_api=integration_environment_api,
            engineering_secret_api=engineering_secret_api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        exchange = urllib.request.Request(
            self.base + "/api/v1/session", data=b"{}", method="POST",
            headers={"Authorization": "Bearer " + "x" * 32, "Origin": self.base},
        )
        self.csrf = json.loads(self.opener.open(exchange).read())["csrf_token"]

    def post(self, path, document):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(document).encode(), method="POST",
            headers={
                "Content-Type": "application/json", "Origin": self.base,
                "X-CSRF-Token": self.csrf,
            },
        )
        return json.loads(self.opener.open(request).read())

    def get(self, path):
        return json.loads(self.opener.open(self.base + path).read())

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def console_activate(console, grant):
    digest = engineering_grant_digest(grant)
    context = console.post("/api/v1/engineering/authentication-contexts", {
        "owner_id": grant.owner_id, "purpose": "engineering-grant",
        "payload_sha256": digest, "confirmed": True,
    })
    approval = OwnerGrantApproval(
        "console-approval-1", grant.grant_id, grant.owner_id,
        digest, now(), context["context_id"],
    )
    console.post("/api/v1/engineering/grants/activate", {
        "grant": encode_document(grant), "approval": encode_document(approval),
        "challenge": None, "decision": None, "confirmed": True,
    })
    return approval


def serve(server, operation):
    result = []
    failure = []
    thread = threading.Thread(target=lambda: _capture(operation, result, failure))
    thread.start()
    server.serve_once()
    thread.join(timeout=10)
    if failure:
        raise failure[0]
    return result[0]


def _capture(operation, result, failure):
    try:
        result.append(operation())
    except Exception as error:
        failure.append(error)


def _write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def now():
    return datetime.now(timezone.utc)


class UnusedCore:
    pass
