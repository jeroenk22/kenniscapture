"""Unit tests voor knowledge_engine module."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def test_calculate_completion_leeg():
    """Completion is 0.0 als er geen chunks zijn."""
    mock_topics = [
        {"contract_type": "NDA", "topic": "aansprakelijkheid_bedrag",
         "topic_label": "Aansprakelijkheid", "priority": 1},
    ]
    with patch("knowledge_engine.database") as mock_db:
        mock_db.get_all_topics.return_value = mock_topics
        mock_db.get_covered_topics.return_value = {}
        import knowledge_engine
        result = knowledge_engine.calculate_completion()
    assert result["overall"] == 0.0
    assert result["total_topics"] == 1
    assert result["covered_topics"] == 0


def test_get_open_topics_geeft_alle_topics_terug():
    """Alle topics zijn open als er geen chunks zijn."""
    mock_topics = [
        {"contract_type": "NDA", "topic": "looptijd_bepalen",
         "topic_label": "Looptijd", "priority": 2},
        {"contract_type": "NDA", "topic": "boeteclausule_wanneer",
         "topic_label": "Boeteclausule", "priority": 2},
    ]
    with patch("knowledge_engine.database") as mock_db:
        mock_db.get_all_topics.return_value = mock_topics
        mock_db.get_covered_topics.return_value = {}
        import knowledge_engine
        open_topics = knowledge_engine.get_open_topics()
    assert len(open_topics) == 2


def test_get_next_question_topic_intersection():
    """Topic in detected_topics heeft prioriteit."""
    all_topics = [
        {"contract_type": "NDA", "topic": "topic_a", "topic_label": "Topic A", "priority": 1},
        {"contract_type": "NDA", "topic": "topic_b", "topic_label": "Topic B", "priority": 2},
    ]
    with patch("knowledge_engine.database") as mock_db:
        mock_db.get_topics_for_contract.return_value = all_topics
        mock_db.get_covered_topics.return_value = {}
        import knowledge_engine
        result = knowledge_engine.get_next_question_topic("NDA", ["topic_b"])
    assert result is not None
    assert result["topic"] == "topic_b"
