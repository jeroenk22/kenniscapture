"""Unit tests voor ollama_client._build_chat_prompt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import ollama_client


def test_prompt_bevat_kennisbank_en_vraag():
    prompt = ollama_client._build_chat_prompt(
        message="Wat is de proeftijd?",
        history=[],
        knowledge_chunks="[Proeftijd | Bron: contract.docx]\nV: ...\nA: twee maanden",
    )
    assert "KENNISBANK" in prompt
    assert "Wat is de proeftijd?" in prompt
    assert "ANTWOORD" in prompt
    assert "twee maanden" in prompt


def test_prompt_geen_vorige_context_zonder_history():
    prompt = ollama_client._build_chat_prompt(
        message="vraag",
        history=[],
        knowledge_chunks="kennis",
    )
    assert "Vorige context" not in prompt


def test_prompt_filtert_geen_antwoord_uit_history():
    history = [
        {"role": "user", "content": "Vraag 1"},
        {"role": "assistant", "content": "Ik kan geen antwoord geven op deze vraag"},
        {"role": "user", "content": "Vraag 2"},
        {"role": "assistant", "content": "De proeftijd is twee maanden"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="Nieuwe vraag",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "Ik kan geen antwoord geven" not in prompt
    assert "De proeftijd is twee maanden" in prompt


def test_prompt_filtert_niet_relevant_uit_history():
    history = [
        {"role": "user", "content": "Vraag"},
        {"role": "assistant", "content": "Er is geen relevante informatie beschikbaar"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="Nieuwe vraag",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "geen relevante informatie" not in prompt


def test_prompt_trunceert_kennisbank_op_4000_tekens():
    lange_kennis = "k" * 5000
    prompt = ollama_client._build_chat_prompt(
        message="vraag",
        history=[],
        knowledge_chunks=lange_kennis,
    )
    kennis_in_prompt = "k" * 4000
    assert kennis_in_prompt in prompt
    assert "k" * 4001 not in prompt


def test_prompt_behoudt_geslaagde_history():
    history = [
        {"role": "user", "content": "Wat is een NDA?"},
        {"role": "assistant", "content": "Een NDA is een geheimhoudingsovereenkomst"},
    ]
    prompt = ollama_client._build_chat_prompt(
        message="En wat staat er in?",
        history=history,
        knowledge_chunks="kennis",
    )
    assert "Vorige context" in prompt
    assert "Een NDA is een geheimhoudingsovereenkomst" in prompt
