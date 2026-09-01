import os

import psycopg
import pytest
from dotenv import load_dotenv

from designs.service import create_design

load_dotenv()


@pytest.fixture
def cleanup_designs():
    """Tracks design ids created by `create_design` (which commits its own
    connection) and deletes them afterward -- unlike `designs/db.py`'s
    tests, this can't rely on a rolled-back transaction for isolation.
    `verification_items` rows cascade-delete with their design."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM designs WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


def test_create_design_returns_created_status_and_design_id(cleanup_designs):
    result = create_design(
        design_key="SVC-DES-1",
        name="Service Layer Design",
        revision="A",
        requirements={},
        architecture={},
    )
    cleanup_designs.append(result["design_id"])

    assert result["status"] == "created"
    assert result["design_key"] == "SVC-DES-1"
    assert result["design_status"] == "DRAFT"


def test_create_design_with_dangling_component_id_returns_structured_error(cleanup_designs):
    result = create_design(
        design_key="SVC-DES-2",
        name="Dangling Ref via Service",
        revision="A",
        requirements={},
        architecture={"lna": {"component_id": 987_654}},
    )

    assert result["status"] == "dangling_component_reference"
    assert result["offending"] == [{"block": "lna", "component_id": 987_654}]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", ("SVC-DES-2",))
            (count,) = cur.fetchone()
    finally:
        conn.close()
    assert count == 0


def test_create_design_with_malformed_requirements_returns_structured_error(cleanup_designs):
    result = create_design(
        design_key="SVC-DES-3",
        name="Bad Requirements via Service",
        revision="A",
        requirements={"REQ-1": "not a dict"},
        architecture={},
    )

    assert result["status"] == "invalid_requirements"
    assert "REQ-1" in result["message"]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", ("SVC-DES-3",))
            (count,) = cur.fetchone()
    finally:
        conn.close()
    assert count == 0
