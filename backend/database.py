"""SQLite database setup, queries en migrations voor Kenniscapture."""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_log = logging.getLogger("app.database")

DB_PATH = Path(os.getenv("DATABASE_PATH", "../data/kennisbank.db"))


@contextmanager
def _conn():
    """Context manager voor SQLite verbinding."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Maak alle tabellen aan en vul seed data in."""
    with _conn() as con:
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                topic_label TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                source_file TEXT,
                source_passage TEXT,
                source_page INTEGER,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS asked_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                question_hash TEXT UNIQUE NOT NULL,
                answered BOOLEAN DEFAULT FALSE,
                skipped BOOLEAN DEFAULT FALSE,
                irrelevant BOOLEAN DEFAULT FALSE,
                asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                contract_type TEXT,
                page_count INTEGER,
                extracted_topics TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_type TEXT NOT NULL,
                topic TEXT NOT NULL,
                topic_label TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                UNIQUE(contract_type, topic)
            )
        """)

        # Seed knowledge_topics
        topics = [
            # NDA
            (
                "NDA",
                "aansprakelijkheid_bedrag",
                "Aansprakelijkheid \u2014 bedrag bepalen",
                1,
            ),
            (
                "NDA",
                "aansprakelijkheid_begrensd_vs_onbeperkt",
                "Aansprakelijkheid \u2014 begrensd vs onbeperkt",
                1,
            ),
            (
                "NDA",
                "aansprakelijkheid_buitenlandse_partij",
                "Aansprakelijkheid \u2014 buitenlandse partij",
                2,
            ),
            ("NDA", "boeteclausule_wanneer", "Boeteclausule \u2014 wanneer opnemen", 2),
            ("NDA", "boeteclausule_bedrag", "Boeteclausule \u2014 bedrag bepalen", 3),
            ("NDA", "looptijd_bepalen", "Looptijd \u2014 hoe bepalen", 2),
            (
                "NDA",
                "automatische_verlenging",
                "Automatische verlenging \u2014 wanneer",
                3,
            ),
            ("NDA", "ontbinding_termijn", "Ontbinding \u2014 met of zonder termijn", 2),
            (
                "NDA",
                "ontbinding_directe_ontbinding",
                "Ontbinding \u2014 wanneer direct",
                2,
            ),
            ("NDA", "geheimhouding_scope", "Geheimhouding \u2014 scope bepalen", 3),
            # Arbeidscontract
            ("arbeidscontract", "proeftijd_duur", "Proeftijd \u2014 1 vs 2 maanden", 1),
            (
                "arbeidscontract",
                "concurrentiebeding_wanneer",
                "Concurrentiebeding \u2014 wanneer opnemen",
                1,
            ),
            (
                "arbeidscontract",
                "concurrentiebeding_scope",
                "Concurrentiebeding \u2014 geografische scope",
                2,
            ),
            (
                "arbeidscontract",
                "ontslaggronden",
                "Ontslag \u2014 gronden en procedure",
                1,
            ),
            ("arbeidscontract", "loon_bepalen", "Loon \u2014 hoe bepalen", 2),
            (
                "arbeidscontract",
                "overuren_regeling",
                "Overuren \u2014 regeling vastleggen",
                3,
            ),
            # Leverancier
            (
                "leverancier",
                "betaaltermijn_bepalen",
                "Betaaltermijn \u2014 hoe bepalen",
                1,
            ),
            ("leverancier", "garantie_clausule", "Garantie \u2014 clausule opnemen", 2),
            (
                "leverancier",
                "levering_voorwaarden",
                "Levering \u2014 voorwaarden vastleggen",
                2,
            ),
            (
                "leverancier",
                "aansprakelijkheid_leverancier",
                "Aansprakelijkheid leverancier",
                1,
            ),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO knowledge_topics "
            "(contract_type, topic, topic_label, priority) VALUES (?, ?, ?, ?)",
            topics,
        )
        _log.info("Database geinitialiseerd met %d topics", len(topics))


# === Query helpers ===


def get_all_topics() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM knowledge_topics ORDER BY priority"
        ).fetchall()
        return [dict(r) for r in rows]


def get_topic_label(topic: str) -> str:
    with _conn() as con:
        row = con.execute(
            "SELECT topic_label FROM knowledge_topics WHERE topic = ?", (topic,)
        ).fetchone()
        return row["topic_label"] if row else topic


def get_topics_for_contract(contract_type: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM knowledge_topics WHERE contract_type = ? ORDER BY priority",
            (contract_type,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_processed_document(file_hash: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM processed_documents WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return dict(row) if row else None


def save_processed_document(
    filename: str,
    file_hash: str,
    contract_type: str,
    page_count: int,
    extracted_topics: str,
) -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO processed_documents
                (filename, file_hash, contract_type, page_count, extracted_topics)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, file_hash, contract_type, page_count, extracted_topics),
        )
        return cur.lastrowid


def save_document_stub(filename: str, file_hash: str, page_count: int) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO processed_documents (filename, file_hash, page_count) VALUES (?, ?, ?)",
            (filename, file_hash, page_count),
        )
        return cur.lastrowid


def update_document_analysis(
    doc_id: int, contract_type: str, extracted_topics: str
) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE processed_documents SET contract_type = ?, extracted_topics = ? WHERE id = ?",
            (contract_type, extracted_topics, doc_id),
        )


def get_document_by_id(doc_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM processed_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_processed_documents() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM processed_documents ORDER BY processed_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_document_by_filename(filename: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM processed_documents WHERE filename = ? ORDER BY processed_at DESC LIMIT 1",
            (filename,),
        ).fetchone()
        return dict(row) if row else None


def get_irrelevant_topics(contract_type: str) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT topic FROM asked_questions WHERE contract_type = ? AND irrelevant = TRUE",
            (contract_type,),
        ).fetchall()
        return [r["topic"] for r in rows]


def get_skipped_topics(contract_type: str) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            """SELECT DISTINCT topic FROM asked_questions
               WHERE contract_type = ? AND skipped = TRUE
               AND answered = FALSE AND irrelevant = FALSE""",
            (contract_type,),
        ).fetchall()
        return [r["topic"] for r in rows]


def get_asked_questions(contract_type: str, topic: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM asked_questions WHERE contract_type = ? AND topic = ?",
            (contract_type, topic),
        ).fetchall()
        return [dict(r) for r in rows]


def save_asked_question(
    contract_type: str,
    topic: str,
    question: str,
    question_hash: str,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO asked_questions
                (contract_type, topic, question, question_hash)
            VALUES (?, ?, ?, ?)
            """,
            (contract_type, topic, question, question_hash),
        )


def mark_question_answered(question_id: str) -> None:  # noqa: ARG001
    with _conn() as con:
        con.execute(
            """
            UPDATE asked_questions SET answered = TRUE
            WHERE id = (
                SELECT id FROM asked_questions
                WHERE answered = FALSE AND skipped = FALSE AND irrelevant = FALSE
                ORDER BY id DESC LIMIT 1
            )
            """
        )


def mark_question_skipped(question_id: str) -> None:  # noqa: ARG001
    with _conn() as con:
        con.execute(
            """
            UPDATE asked_questions SET skipped = TRUE
            WHERE id = (
                SELECT id FROM asked_questions
                WHERE answered = FALSE AND skipped = FALSE
                ORDER BY id DESC LIMIT 1
            )
            """
        )


def mark_question_irrelevant(question_id: str) -> None:  # noqa: ARG001
    with _conn() as con:
        con.execute(
            """
            UPDATE asked_questions SET irrelevant = TRUE
            WHERE id = (
                SELECT id FROM asked_questions
                WHERE answered = FALSE AND irrelevant = FALSE
                ORDER BY id DESC LIMIT 1
            )
            """
        )


def save_knowledge_chunk(
    contract_type: str,
    topic: str,
    topic_label: str,
    question: str,
    answer: str,
    source_file: str,
    source_passage: str,
    source_page: int | None,
) -> int:
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO knowledge_chunks
                (contract_type, topic, topic_label, question, answer,
                 source_file, source_passage, source_page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract_type,
                topic,
                topic_label,
                question,
                answer,
                source_file,
                source_passage,
                source_page,
            ),
        )
        return cur.lastrowid


def get_all_chunks() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM knowledge_chunks ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_covered_topics() -> dict[str, list[str]]:
    """Geeft per contracttype de gedekte topics (confidence >= 0.5)."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT DISTINCT contract_type, topic
            FROM knowledge_chunks
            WHERE confidence >= 0.5
            """
        ).fetchall()
    result: dict[str, list[str]] = {}
    for r in rows:
        result.setdefault(r["contract_type"], []).append(r["topic"])
    return result


def reset_knowledge_bank() -> None:
    """Verwijder alle kennis, vragen en documenten. Behoudt topics seed."""
    with _conn() as con:
        con.execute("DELETE FROM knowledge_chunks")
        con.execute("DELETE FROM asked_questions")
        con.execute("DELETE FROM processed_documents")


if __name__ == "__main__":
    init_db()
    print("Database geinitialiseerd")
