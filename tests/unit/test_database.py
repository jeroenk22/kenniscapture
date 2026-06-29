"""Unit tests voor database module."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def test_init_db_maakt_tabellen_aan():
    """init_db maakt alle verwachte tabellen aan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            import database
            database.init_db()

            import sqlite3
            con = sqlite3.connect(db_path)
            tabellen = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            con.close()

    assert "knowledge_chunks" in tabellen
    assert "asked_questions" in tabellen
    assert "processed_documents" in tabellen
    assert "knowledge_topics" in tabellen


def test_init_db_seed_data():
    """init_db vult knowledge_topics met seed data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            import database
            database.init_db()
            topics = database.get_all_topics()

    assert len(topics) == 20
    contract_types = {t["contract_type"] for t in topics}
    assert "NDA" in contract_types
    assert "arbeidscontract" in contract_types
    assert "leverancier" in contract_types
