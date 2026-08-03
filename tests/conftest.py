import hashlib

import pytest

from app.database import Database
from app.metering import MeteringService


@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.migrate()
    with db.transaction() as connection:
        connection.executemany(
            "INSERT INTO plans(code,api_call_limit,ai_token_limit) VALUES (?,?,?)",
            [("free", 1000, 100_000), ("pro", 100_000, 10_000_000)],
        )
        connection.execute(
            "INSERT INTO tenants(id,name,api_key_hash) VALUES (?,?,?)",
            ("tenant-a", "Tenant A", hashlib.sha256(b"secret").hexdigest()),
        )
        connection.execute(
            "INSERT INTO subscriptions(tenant_id,plan_code,status) VALUES (?,?,?)",
            ("tenant-a", "free", "active"),
        )
    return db


@pytest.fixture
def service(database):
    return MeteringService(database)


@pytest.fixture
def tenant(service):
    return service.authenticate("tenant-a", "secret")

