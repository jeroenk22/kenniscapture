# Python Best Practices — Kenniscapture Backend

## Tooling
- **Formatter + linter:** Ruff 0.15.18 (vervangt Black + flake8 + isort)
- **Tests:** pytest + pytest-cov (drempel ≥ 90%)
- **Python versie:** 3.12.6

## Logging
Gebruik altijd de centrale logger per module:
```python
import logging
_log = logging.getLogger("app.module_naam")
```
Nooit `print()` voor diagnostische output.

## Database
- Gebruik altijd de `_conn()` context manager voor SQLite verbindingen
- Gebruik `con.row_factory = sqlite3.Row` voor dict-achtige toegang
- Transacties worden automatisch gecommit/gerollbackt

## Ollama
- Ollama draaivereiste: `ollama serve` op localhost:11434
- Model: `llama3.1:8b` (minimaal) of `llama3.1:70b` (productie)
- Altijd JSON-only responses vragen via prompt
- Altijd `_strip_markdown()` toepassen op Ollama output

## Pre-PR checklist
```bash
cd backend
source venv/Scripts/activate  # Windows
ruff check .
ruff format --check .
pytest --cov --cov-fail-under=90
```
