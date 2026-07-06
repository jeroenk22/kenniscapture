"""Unit tests voor database module."""
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import database  # noqa: E402


def test_init_db_maakt_tabellen_aan() -> None:
    """init_db maakt alle verwachte tabellen aan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()

            con = sqlite3.connect(db_path)
            tabellen = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            con.close()

    assert "knowledge_chunks" in tabellen
    assert "asked_questions" in tabellen
    assert "processed_documents" in tabellen
    assert "knowledge_topics" in tabellen


def test_init_db_seed_data() -> None:
    """init_db vult knowledge_topics met seed data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            topics = database.get_all_topics()

    assert len(topics) == 20
    contract_types = {t["contract_type"] for t in topics}
    assert "NDA" in contract_types
    assert "arbeidscontract" in contract_types
    assert "leverancier" in contract_types


def test_get_document_by_filename_gevonden() -> None:
    """get_document_by_filename geeft het juiste document terug."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            database.save_processed_document(
                filename="test.docx",
                file_hash="abc123def456",
                contract_type="arbeidscontract",
                page_count=5,
                extracted_topics="[]",
            )
            result = database.get_document_by_filename("test.docx")

    assert result is not None
    assert result["filename"] == "test.docx"
    assert result["file_hash"] == "abc123def456"
    assert result["contract_type"] == "arbeidscontract"


def test_get_all_processed_documents_leeg() -> None:
    """get_all_processed_documents geeft lege lijst terug als er geen documenten zijn."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            result = database.get_all_processed_documents()
    assert result == []


def test_get_all_processed_documents_meerdere() -> None:
    """get_all_processed_documents geeft alle opgeslagen documenten terug."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            database.save_processed_document("eerste.docx", "hash1", "NDA", 3, "[]")
            database.save_processed_document("tweede.docx", "hash2", "arbeidscontract", 5, "[]")
            result = database.get_all_processed_documents()
    assert len(result) == 2
    filenames = {r["filename"] for r in result}
    assert filenames == {"eerste.docx", "tweede.docx"}


def test_get_document_by_filename_niet_gevonden() -> None:
    """get_document_by_filename geeft None als het bestand niet bestaat."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            result = database.get_document_by_filename("bestaat_niet.docx")

    assert result is None


def test_ensure_topic_voegt_nieuw_contracttype_toe() -> None:
    """ensure_topic laat de catalogus meegroeien met een nieuw contracttype."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            database.ensure_topic(
                "aannemingsovereenkomst", "boeteclausule_bij_vertraging", "Boeteclausule bij vertraging"
            )
            topics = database.get_topics_for_contract("aannemingsovereenkomst")

    assert len(topics) == 1
    assert topics[0]["topic"] == "boeteclausule_bij_vertraging"
    assert topics[0]["topic_label"] == "Boeteclausule bij vertraging"


def test_ensure_topic_overschrijft_bestaand_topic_niet() -> None:
    """Een tweede vindplaats van dezelfde sleutel wijzigt de eerste label niet."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            database.ensure_topic("leverancier", "nieuw_onderwerp", "Eerste label")
            database.ensure_topic("leverancier", "nieuw_onderwerp", "Tweede label")
            topics = database.get_topics_for_contract("leverancier")

    nieuw = [t for t in topics if t["topic"] == "nieuw_onderwerp"]
    assert len(nieuw) == 1
    assert nieuw[0]["topic_label"] == "Eerste label"


def test_get_known_contract_types_bevat_seed_types() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            types = database.get_known_contract_types()

    assert set(types) == {"NDA", "arbeidscontract", "leverancier"}


def test_get_known_contract_types_bevat_nieuw_type_na_ensure_topic() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("database.DB_PATH", db_path):
            database.init_db()
            database.ensure_topic("huurovereenkomst", "huurprijs_bepalen", "Huurprijs bepalen")
            types = database.get_known_contract_types()

    assert "huurovereenkomst" in types