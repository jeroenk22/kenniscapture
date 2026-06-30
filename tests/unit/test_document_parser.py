"""Unit tests voor document_parser module."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import document_parser  # noqa: E402


def test_parse_docx_geeft_tekst_en_passages(tmp_path):
    mock_para = MagicMock()
    mock_para.text = "Dit is een paragraaf."
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]
    mock_doc.tables = []

    with patch("docx.Document", return_value=mock_doc):
        tekst, passages = document_parser.parse_docx(tmp_path / "test.docx")

    assert "Dit is een paragraaf." in tekst
    assert passages[0]["text"] == "Dit is een paragraaf."
    assert passages[0]["page"] is None


def test_parse_docx_lege_paragrafen_worden_overgeslagen(tmp_path):
    para_leeg = MagicMock()
    para_leeg.text = "   "
    para_vol = MagicMock()
    para_vol.text = "Inhoud"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [para_leeg, para_vol]
    mock_doc.tables = []

    with patch("docx.Document", return_value=mock_doc):
        _, passages = document_parser.parse_docx(tmp_path / "test.docx")

    assert len(passages) == 1
    assert passages[0]["text"] == "Inhoud"


def test_parse_docx_tabel_tekst_meegenomen(tmp_path):
    cel = MagicMock()
    cel.text = "Tabelinhoud"
    rij = MagicMock()
    rij.cells = [cel]
    tabel = MagicMock()
    tabel.rows = [rij]
    mock_doc = MagicMock()
    mock_doc.paragraphs = []
    mock_doc.tables = [tabel]

    with patch("docx.Document", return_value=mock_doc):
        tekst, passages = document_parser.parse_docx(tmp_path / "test.docx")

    assert "Tabelinhoud" in tekst
    assert any(p["text"] == "Tabelinhoud" for p in passages)


def test_parse_pdf_geeft_tekst_en_passages(tmp_path):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Eerste pagina\n\nTweede alinea"
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        tekst, passages = document_parser.parse_pdf(tmp_path / "test.pdf")

    assert "Eerste pagina" in tekst
    assert any(p["page"] == 1 for p in passages)


def test_parse_pdf_lege_pagina_wordt_overgeslagen(tmp_path):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        tekst, passages = document_parser.parse_pdf(tmp_path / "test.pdf")

    assert tekst == ""
    assert passages == []