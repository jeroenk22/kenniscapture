"""Integratietests voor FastAPI endpoints (echte DB, gemockte Ollama)."""
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


@pytest.fixture()
def tmp_db(tmp_path):
    """Tijdelijke SQLite database per test."""
    db_path = tmp_path / "test.db"
    with (
        patch("database.DB_PATH", db_path),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        import database

        database.init_db()
        yield db_path


@pytest.fixture()
def client(tmp_db):
    """TestClient met tijdelijke database en upload-map."""
    with patch("database.DB_PATH", tmp_db):
        from main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── /api/documents ─────────────────────────────────────────────────────────


def test_get_documents_leeg(client):
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert resp.json() == {"documents": []}


def test_get_documents_na_upload(client, tmp_path):
    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        database.save_processed_document(
            filename="test.pdf",
            file_hash="abc123",
            contract_type="NDA",
            page_count=2,
            extracted_topics=json.dumps([{"topic": "concurrentiebeding", "passage": "p"}]),
        )

    resp = client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "test.pdf"


# ── /api/completion ────────────────────────────────────────────────────────


def test_get_completion(client):
    resp = client.get("/api/completion")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data
    assert "total_topics" in data


# ── /api/knowledge-bank ────────────────────────────────────────────────────


def test_get_knowledge_bank_leeg(client):
    resp = client.get("/api/knowledge-bank")
    assert resp.status_code == 200
    data = resp.json()
    assert "chunks" in data
    assert "open_topics" in data


# ── /api/reset ─────────────────────────────────────────────────────────────


def test_reset(client):
    resp = client.post("/api/reset")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── /api/skip-question ─────────────────────────────────────────────────────


def test_skip_question_straks(client):
    resp = client.post("/api/skip-question", json={"question_id": "q_test1", "reason": "straks"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_skip_question_niet_relevant(client):
    resp = client.post(
        "/api/skip-question", json={"question_id": "q_test2", "reason": "niet_relevant"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── /api/save-answer ───────────────────────────────────────────────────────


def test_save_answer(client):
    payload = {
        "question_id": "q_abc",
        "question": "Wat is de opzegtermijn?",
        "answer": "Drie maanden",
        "topic": "opzegtermijn",
        "contract_type": "arbeidscontract",
        "source_file": "contract.pdf",
        "source_passage": "De opzegtermijn bedraagt 3 maanden.",
        "source_page": 2,
    }
    resp = client.post("/api/save-answer", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "chunk_id" in data
    assert "completion" in data


# ── /api/generate-question ─────────────────────────────────────────────────


def test_generate_question_geen_topics(client):
    resp = client.post(
        "/api/generate-question",
        json={
            "document_id": 1,
            "contract_type": "anders",
            "detected_topics": [],
            "source_passage": "",
            "source_file": "x.pdf",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["has_question"] is False


def test_generate_question_met_topic(client):
    mock_result = AsyncMock(return_value={"question": "Wat is de looptijd?"})
    with patch("ollama_client.generate_question", mock_result):
        resp = client.post(
            "/api/generate-question",
            json={
                "document_id": 1,
                "contract_type": "NDA",
                "detected_topics": ["geheimhouding"],
                "source_passage": "Partijen houden informatie geheim.",
                "source_file": "nda.pdf",
                "passages_by_topic": {"geheimhouding": "Partijen houden informatie geheim."},
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_question"] is True
    assert "question" in data


def test_generate_question_ollama_fout(client):
    with patch("ollama_client.generate_question", side_effect=RuntimeError("Ollama down")):
        resp = client.post(
            "/api/generate-question",
            json={
                "document_id": 1,
                "contract_type": "NDA",
                "detected_topics": ["geheimhouding"],
                "source_passage": "Tekst",
                "source_file": "nda.pdf",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["has_question"] is True  # fallback vraag


# ── /api/upload-document ───────────────────────────────────────────────────


def test_upload_document_ongeldig_type(client):
    resp = client.post(
        "/api/upload-document",
        files={"file": ("test.txt", b"inhoud", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_document_pdf(client, tmp_path):
    mock_parse = MagicMock(return_value=("Contract tekst", [{"text": "tekst", "page": 1}]))
    mock_analyse = AsyncMock(
        return_value={"contract_type": "NDA", "detected_topics": []}
    )
    with (
        patch("document_parser.parse_pdf", mock_parse),
        patch("ollama_client.analyze_document", mock_analyse),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(
            "/api/upload-document",
            files={"file": ("contract.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["contract_type"] == "NDA"
    assert data["already_processed"] is False


def test_upload_document_al_verwerkt(client, tmp_path):
    import hashlib

    content = b"%PDF-1.4 test"
    file_hash = hashlib.sha256(content).hexdigest()

    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        database.save_processed_document(
            filename="contract.pdf",
            file_hash=file_hash,
            contract_type="NDA",
            page_count=1,
            extracted_topics="[]",
        )

    resp = client.post(
        "/api/upload-document",
        files={"file": ("contract.pdf", content, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["already_processed"] is True


def test_upload_document_parse_fout(client, tmp_path):
    with (
        patch("document_parser.parse_pdf", side_effect=ValueError("Kapot bestand")),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(
            "/api/upload-document",
            files={"file": ("kapot.pdf", b"%PDF broken", "application/pdf")},
        )
    assert resp.status_code == 422


# ── /api/parse-document ────────────────────────────────────────────────────


def test_parse_document_nieuw(client, tmp_path):
    mock_parse = MagicMock(return_value=("tekst", [{"text": "p", "page": 1}]))
    with (
        patch("document_parser.parse_pdf", mock_parse),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(
            "/api/parse-document",
            files={"file": ("doc.pdf", b"%PDF test", "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["already_processed"] is False


def test_parse_document_ongeldig_type(client):
    resp = client.post(
        "/api/parse-document",
        files={"file": ("test.csv", b"a,b,c", "text/csv")},
    )
    assert resp.status_code == 400


def test_parse_document_al_verwerkt(client, tmp_path):
    import hashlib

    content = b"%PDF al verwerkt"
    file_hash = hashlib.sha256(content).hexdigest()

    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        database.save_document_stub(
            filename="al_verwerkt.pdf", file_hash=file_hash, page_count=2
        )

    resp = client.post(
        "/api/parse-document",
        files={"file": ("al_verwerkt.pdf", content, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["already_processed"] is True


def test_parse_document_parse_fout(client, tmp_path):
    with (
        patch("document_parser.parse_pdf", side_effect=ValueError("Kapot")),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(
            "/api/parse-document",
            files={"file": ("kapot.pdf", b"%PDF broken", "application/pdf")},
        )
    assert resp.status_code == 422


def test_upload_document_docx(client, tmp_path):
    mock_parse = MagicMock(return_value=("Tekst", [{"text": "p", "page": None}]))
    mock_analyse = AsyncMock(
        return_value={"contract_type": "arbeidscontract", "detected_topics": []}
    )
    with (
        patch("document_parser.parse_docx", mock_parse),
        patch("ollama_client.analyze_document", mock_analyse),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(
            "/api/upload-document",
            files={"file": ("contract.docx", b"PK fake docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert resp.status_code == 200
    assert resp.json()["contract_type"] == "arbeidscontract"


def test_analyze_document_succes(client, tmp_path):
    import hashlib

    content = b"%PDF test"
    file_hash = hashlib.sha256(content).hexdigest()
    bestand = tmp_path / f"{file_hash}.pdf"
    bestand.write_bytes(content)

    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        doc_id = database.save_document_stub(
            filename="analyse.pdf", file_hash=file_hash, page_count=1
        )

    mock_parse = MagicMock(return_value=("tekst", [{"text": "p", "page": 1}]))
    mock_analyse = AsyncMock(
        return_value={"contract_type": "NDA", "detected_topics": [{"topic": "geheimhouding", "passage": "tekst"}]}
    )
    with (
        patch("document_parser.parse_pdf", mock_parse),
        patch("ollama_client.analyze_document", mock_analyse),
        patch("main.UPLOAD_DIR", tmp_path),
    ):
        resp = client.post(f"/api/analyze-document/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["contract_type"] == "NDA"


# ── /api/analyze-document/{doc_id} ────────────────────────────────────────


def test_analyze_document_niet_gevonden(client):
    resp = client.post("/api/analyze-document/9999")
    assert resp.status_code == 404


def test_analyze_document_bestand_ontbreekt(client, tmp_path):
    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        doc_id = database.save_document_stub(
            filename="missing.pdf", file_hash="doesnotexist", page_count=0
        )

    with patch("main.UPLOAD_DIR", tmp_path):
        resp = client.post(f"/api/analyze-document/{doc_id}")
    assert resp.status_code == 404


# ── /api/download ──────────────────────────────────────────────────────────


def test_download_niet_gevonden(client):
    resp = client.get("/api/download/onbekend.pdf")
    assert resp.status_code == 404


def test_download_bestand_aanwezig(client, tmp_path):
    import hashlib

    content = b"PDF inhoud"
    file_hash = hashlib.sha256(content).hexdigest()

    with patch("database.DB_PATH", tmp_path / "test.db"):
        import database

        database.save_processed_document(
            filename="download.pdf",
            file_hash=file_hash,
            contract_type="anders",
            page_count=1,
            extracted_topics="[]",
        )

    bestand = tmp_path / f"{file_hash}.pdf"
    bestand.write_bytes(content)

    with patch("main.UPLOAD_DIR", tmp_path):
        resp = client.get("/api/download/download.pdf")
    assert resp.status_code == 200


# ── /api/chat ──────────────────────────────────────────────────────────────


async def _fake_stream(*_args, **_kwargs):
    yield "Antwoord"
    yield " op vraag."


def test_chat_stream(client):
    with patch("ollama_client.chat_stream", _fake_stream):
        resp = client.post(
            "/api/chat",
            json={"message": "Wat is een NDA?", "conversation_history": []},
        )
    assert resp.status_code == 200
    body = resp.text
    assert "token" in body
    assert "done" in body


def test_chat_stream_ollama_fout(client):
    async def fout_stream(*_args, **_kwargs):
        raise RuntimeError("Ollama niet bereikbaar")
        yield  # noqa: unreachable

    with patch("ollama_client.chat_stream", fout_stream):
        resp = client.post(
            "/api/chat",
            json={"message": "Vraag", "conversation_history": []},
        )
    assert resp.status_code == 200
    assert "fout" in resp.text.lower() or "token" in resp.text