#!/usr/bin/env bash
# Start alle Kenniscapture services

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Bepaal venv activatie pad
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    VENV="$ROOT_DIR/backend/venv/Scripts/activate"
else
    VENV="$ROOT_DIR/backend/venv/bin/activate"
fi

# Controleer Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama niet gevonden. Installeer via: https://ollama.com"
    echo "   Daarna: ollama pull llama3.1:8b"
    exit 1
fi

echo "🦙 Ollama starten..."
ollama serve &> /dev/null &

# Activeer venv
source "$VENV"

echo "🚀 FastAPI backend starten (poort 8000)..."
(cd "$ROOT_DIR/backend" && uvicorn main:app --reload --port 8000) &

echo "📝 Streamlit kenniscapture starten (poort 8501)..."
(cd "$ROOT_DIR/kenniscapture_ui" && streamlit run app.py --server.port 8501) &

echo "⚛️  React chatbot starten (poort 5173)..."
(cd "$ROOT_DIR/chatbot_ui" && pnpm dev) &

sleep 2
echo ""
echo "=================================================="
echo "  Alle services draaien:"
echo "  📝 Kenniscapture:  http://localhost:8501"
echo "  💬 Chatbot:        http://localhost:5173"
echo "  📡 API docs:       http://localhost:8000/docs"
echo "  🦙 Ollama:         http://localhost:11434"
echo "=================================================="
echo ""
echo "Stop alle services met: Ctrl+C (meerdere keren)"
wait
