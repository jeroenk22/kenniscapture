"""Gap detectie en completion berekening voor Kenniscapture."""
import logging

import database

_log = logging.getLogger("app.knowledge_engine")


def get_next_question_topic(
    contract_type: str,
    detected_topics: list[str],
) -> dict | None:
    """
    Bepaal het volgende onderwerp om een vraag over te stellen.

    Prioriteit: hoge prioriteit topics eerst, nooit al gedekte topics.
    Intersecteer eerst met detected_topics uit het huidige document.
    """
    all_topics = database.get_topics_for_contract(contract_type)
    covered = database.get_covered_topics().get(contract_type, [])
    open_topics = [t for t in all_topics if t["topic"] not in covered]

    if not open_topics:
        return None

    # Intersecteer met topics uit huidig document
    if detected_topics:
        intersection = [t for t in open_topics if t["topic"] in detected_topics]
        if intersection:
            return intersection[0]

    # Fallback: eerste open topic voor dit contracttype
    return open_topics[0]


def calculate_completion() -> dict:
    """Bereken voortgang kennisbank per contracttype en overall."""
    all_topics = database.get_all_topics()
    covered_map = database.get_covered_topics()

    by_type: dict[str, list[str]] = {}
    for t in all_topics:
        by_type.setdefault(t["contract_type"], []).append(t["topic"])

    by_contract_type = {}
    total_topics = 0
    total_covered = 0

    for ct, topics in by_type.items():
        covered = covered_map.get(ct, [])
        n_covered = sum(1 for t in topics if t in covered)
        n_total = len(topics)
        total_topics += n_total
        total_covered += n_covered
        by_contract_type[ct] = {
            "percentage": round(n_covered / n_total, 2) if n_total > 0 else 0.0,
            "covered": n_covered,
            "total": n_total,
        }

    overall = round(total_covered / total_topics, 2) if total_topics > 0 else 0.0

    return {
        "overall": overall,
        "total_topics": total_topics,
        "covered_topics": total_covered,
        "by_contract_type": by_contract_type,
    }


def get_open_topics() -> list[dict]:
    """Geef alle niet-gedekte topics terug, gesorteerd op prioriteit."""
    all_topics = database.get_all_topics()
    covered_map = database.get_covered_topics()

    return sorted(
        [
            {
                "contract_type": t["contract_type"],
                "topic": t["topic"],
                "topic_label": t["topic_label"],
                "priority": t["priority"],
            }
            for t in all_topics
            if t["topic"] not in covered_map.get(t["contract_type"], [])
        ],
        key=lambda x: x["priority"],
    )
