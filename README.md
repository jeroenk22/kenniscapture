# Kenniscapture Systeem

Volledig intern kennisopslagsysteem. Niets verlaat het netwerk.

## Architectuur

```
KENNISCAPTURE TOOL          CHATBOT ASSISTENT
Streamlit (8501)            React + Vite (5173)
        |                           |
        └──────────┬────────────────┘
                   |
          FastAPI backend (8000)
                   |
        ┌──────────┴───────────────┐
        |                          |
   SQLite database             Ollama LLM
   (data/kennisbank.db)    (localhost:11434)
```

## Vereisten

- Python 3.12.6+
- Node.js 22+ & pnpm
- [Ollama](https://ollama.com) met `llama3.1:8b`

## Installatie

### 1. Ollama installeren en model downloaden
```bash
ollama pull llama3.1:8b
```

### 2. Python venv aanmaken en dependencies installeren
```bash
py -3.12 -m venv backend/venv
source backend/venv/Scripts/activate  # Windows
pip install -r backend/requirements.txt
```

### 3. React chatbot installeren
```bash
cd chatbot_ui
pnpm install
```

### 4. Database initialiseren
```bash
cd backend
python database.py
```

### 5. Alles starten
```bash
chmod +x start.sh
./start.sh
```

## Gebruik

| Service | URL |
|---|---|
| Kenniscapture (upload + vragen) | http://localhost:8501 |
| Chatbot assistent | http://localhost:5173 |
| API documentatie | http://localhost:8000/docs |

## Development

```bash
# Backend linting + tests
cd backend
ruff check . && ruff format --check .
pytest ../tests --cov=. --cov-fail-under=90

# Frontend linting + tests
cd chatbot_ui
pnpm biome check .
pnpm test:coverage
```
