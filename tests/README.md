# Tests

## Structuur
- `fixtures/` — representatieve inputbestanden en testdata
- `helpers/` — gedeelde hulpfuncties
- `unit/` — unit tests per module (alles gemocked)
- `integration/` — integratietests voor de volledige keten

## Backend tests uitvoeren
```bash
cd backend
source venv/Scripts/activate  # Windows
pytest ../tests --cov=. --cov-fail-under=90
```

## Frontend tests uitvoeren
```bash
cd chatbot_ui
pnpm test
```
