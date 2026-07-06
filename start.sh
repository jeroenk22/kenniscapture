#!/usr/bin/env bash
# Start alle Kenniscapture services

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Laad config.env als die bestaat
if [ -f "$ROOT_DIR/config.env" ]; then
    # Windows-editors (Notepad, PowerShell) laten soms CRLF-regeleinden
    # achter — dat plakt een onzichtbare \r achter elke waarde, waardoor
    # bijv. LLM_PROVIDER=claude niet meer matcht met "claude" in Python
    sed -i 's/\r$//' "$ROOT_DIR/config.env" 2>/dev/null || true
    set -a
    source "$ROOT_DIR/config.env"
    set +a
fi

# Publieke tunnel-URLs (aangemaakt door tunnel.sh, alleen tijdens een
# actieve quick-tunnelsessie — wordt bij het stoppen weer verwijderd)
if [ -f "$ROOT_DIR/tunnel.env" ]; then
    set -a
    source "$ROOT_DIR/tunnel.env"
    set +a
fi

# Standaardwaarden
HOST="${HOST:-127.0.0.1}"
PORT_BACKEND="${PORT_BACKEND:-8000}"
PORT_STREAMLIT="${PORT_STREAMLIT:-8501}"
PORT_CHATBOT="${PORT_CHATBOT:-5173}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
DATABASE_PATH="${DATABASE_PATH:-../data/kennisbank.db}"
UPLOAD_DIR="${UPLOAD_DIR:-../uploads}"

# Bepaal venv activatie pad
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    VENV="$ROOT_DIR/backend/venv/Scripts/activate"
else
    VENV="$ROOT_DIR/backend/venv/bin/activate"
fi

echo "🦙 Ollama starten..."
ollama serve &> /dev/null &

# Activeer venv
source "$VENV"

export DATABASE_PATH UPLOAD_DIR OLLAMA_MODEL
# Claude demo-provider (optioneel): key en modelkeuze uit config.env
export ANTHROPIC_API_KEY LLM_PROVIDER CLAUDE_MODEL

echo "🚀 FastAPI backend starten (poort $PORT_BACKEND)..."
(cd "$ROOT_DIR/backend" && uvicorn main:app --reload --host "$HOST" --port "$PORT_BACKEND") &

echo "📝 Streamlit kenniscapture starten (poort $PORT_STREAMLIT)..."
(cd "$ROOT_DIR/kenniscapture_ui" && streamlit run app.py \
    --server.port "$PORT_STREAMLIT" \
    --server.address "$HOST") &

echo "⚛️  React chatbot starten (poort $PORT_CHATBOT)..."
VITE_HOST_FLAG=""
if [ "$HOST" = "0.0.0.0" ]; then
    VITE_HOST_FLAG="--host"
fi
(cd "$ROOT_DIR/chatbot_ui" && pnpm dev --port "$PORT_CHATBOT" --open $VITE_HOST_FLAG) &

sleep 2

# Toon juiste URLs op basis van HOST
if [ "$HOST" = "0.0.0.0" ]; then
    # Bepaal lokaal IP voor weergave
    if command -v hostname &>/dev/null; then
        LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "192.168.x.x")
    else
        LOCAL_IP="192.168.x.x"
    fi
    URL_BASE="http://$LOCAL_IP"
else
    URL_BASE="http://localhost"
fi

echo ""
echo "=================================================="
echo "  Alle services draaien:"
echo "  📝 Kenniscapture:  $URL_BASE:$PORT_STREAMLIT"
echo "  💬 Chatbot:        $URL_BASE:$PORT_CHATBOT"
echo "  📡 API docs:       $URL_BASE:$PORT_BACKEND/docs"
echo "  🦙 Ollama:         http://localhost:11434"
echo "=================================================="
echo ""
echo "Stop alle services met: Ctrl+C (meerdere keren)"
wait