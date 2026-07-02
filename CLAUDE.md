# Kenniscapture Systeem

## Wat deze app doet

Een volledig intern draaiend systeem dat de kennis van een medewerker (contractspecialist)
vastlegt voordat zij met zwangerschapsverlof gaat. Twee tools, één backend, één kennisbank:

1. **Kenniscapture tool** (Streamlit, poort 8501) — voor de vertrekkende medewerker
2. **Chatbot assistent** (React + Vite, poort 5173) — voor de vervanger

Alles draait volledig lokaal. Geen enkele data verlaat het interne netwerk.

## Stack

| Component | Versie |
|---|---|
| Python | 3.12.6 |
| FastAPI | 0.138.0 |
| uvicorn | 0.49.0 |
| Streamlit | 1.58.0 |
| pdfplumber | 0.11.10 |
| Ruff | 0.15.18 |
| React | 19.2.7 |
| Vite | 8.1.0 |
| TypeScript | 6.0.3 |
| Biome | 2.5.1 |
| Vitest | 4.1.9 |
| Tailwind CSS | 4.3.1 |
| Ollama | llama3.1:8b |

## Commando's

```bash
# Alles starten
./start.sh

# Backend (vanuit backend/ met actieve venv)
uvicorn main:app --reload --port 8000

# Streamlit UI (vanuit kenniscapture_ui/ met actieve venv)
streamlit run app.py --server.port 8501

# React chatbot (vanuit chatbot_ui/)
pnpm dev

# Backend testen
ruff check . && ruff format --check .
pytest ../tests --cov=. --cov-fail-under=90

# Frontend testen
pnpm biome check . && pnpm test:coverage
```

## Projectstructuur

```
kenniscapture/
├── backend/           FastAPI + SQLite + Ollama client
├── kenniscapture_ui/  Streamlit app (upload + vragen)
├── chatbot_ui/        React chatbot voor de vervanger
├── data/              SQLite database (gitignored)
├── uploads/           Tijdelijke uploads (gitignored)
├── tests/             Python unit + integratietests
├── skills/            Best-practice gidsen
└── start.sh           Start alle services
```

## Conventies

- Branch strategie: `main` → `develop` → `feature/xxx`, `fix/xxx`
- Commits: Conventional Commits
- Package manager Python: pip + venv
- Package manager JS: pnpm
- PR: altijd via PR met passing CI

## Pre-PR checklist

**Python:**
```bash
ruff check backend/
ruff format --check backend/
pytest tests/ --cov=backend --cov-fail-under=90
```

**TypeScript:**
```bash
pnpm biome check .
pnpm typecheck
pnpm test:coverage
```

## Wat Claude NIET mag doen

- Nooit direct committen naar main of develop
- Nooit .env bestanden aanmaken met echte secrets
- Nooit data/ of uploads/ committen (vertrouwelijke contracten)
- Nooit de Ollama integratie vervangen door een cloud API
- Nooit bestaande tests verwijderen
- Nooit code opleveren die niet production-ready is
- Nooit "Co-Authored-By: Claude" of "Generated with Claude" (of vergelijkbare AI-attributie) toevoegen aan commits of PR's

## Teststrategie

- **Unit tests** — `tests/unit/` — alles gemocked, snel
- **Integratietests** — `tests/integration/` — echte DB, geen mocks
- Minimaal 90% coverage (Python) / 80% (TypeScript)
- Fixtures aanmaken vóór productiecode

## Security

- Alle data blijft lokaal — geen cloud, geen externe API
- Ollama draait op localhost:11434
- SQLite op `data/kennisbank.db` (gitignored)
- Geüploade bestanden in `uploads/` (gitignored)

## Karpathy Gedragsregels

### 1. Think Before Coding
Stel aannames expliciet. Stop bij onduidelijkheden.

### 2. Simplicity First
Minimum code die het probleem oplost. Geen speculatieve features.

### 3. Surgical Changes
Raak alleen aan wat nodig is. Match bestaande stijl.

### 4. Goal-Driven Execution
Definieer verifieerbare succescriteria voordat je begint.
