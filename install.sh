#!/usr/bin/env bash
# Eenmalige installatie van Kenniscapture op een nieuwe machine
# Gebruik: ./install.sh

set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "=================================================="
echo "  Kenniscapture — installatie"
echo "=================================================="
echo ""

# === config.env aanmaken als die nog niet bestaat ===
if [ ! -f "$ROOT_DIR/config.env" ]; then
    echo "📋 config.env aanmaken van voorbeeld..."
    cp "$ROOT_DIR/config.env.example" "$ROOT_DIR/config.env" 2>/dev/null || true
    echo "   ✅ Pas config.env aan als nodig (HOST, OLLAMA_MODEL, etc.)"
fi

# === Python controleren ===
echo "🐍 Python controleren..."
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "   ❌ Python niet gevonden. Installeer Python 3.12 via https://python.org"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)
# Quotes verplicht: het pad kan spaties bevatten (C:\Program Files\...)
echo "   ✅ $("$PYTHON" --version)"

# === Node.js controleren ===
echo "📦 Node.js controleren..."
if ! command -v node &>/dev/null; then
    echo "   ❌ Node.js niet gevonden. Installeer via https://nodejs.org"
    exit 1
fi
echo "   ✅ $(node --version)"

# === pnpm controleren ===
echo "📦 pnpm controleren..."
if ! command -v pnpm &>/dev/null; then
    echo "   pnpm installeren..."
    npm install -g pnpm
fi
echo "   ✅ pnpm $(pnpm --version)"

# === Ollama controleren ===
echo "🦙 Ollama controleren..."
if ! command -v ollama &>/dev/null; then
    echo "   ❌ Ollama niet gevonden."
    echo "   Installeer via: https://ollama.com/download"
    echo "   Daarna opnieuw ./install.sh uitvoeren."
    exit 1
fi
echo "   ✅ Ollama gevonden"

# === Python venv aanmaken ===
echo ""
echo "🐍 Python omgeving installeren..."
if [ ! -d "$ROOT_DIR/backend/venv" ]; then
    "$PYTHON" -m venv "$ROOT_DIR/backend/venv"
    echo "   ✅ Virtuele omgeving aangemaakt"
fi

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    VENV_ACTIVATE="$ROOT_DIR/backend/venv/Scripts/activate"
else
    VENV_ACTIVATE="$ROOT_DIR/backend/venv/bin/activate"
fi

source "$VENV_ACTIVATE"
# Op Windows kan pip zichzelf niet via pip.exe upgraden — altijd via python -m pip
python -m pip install -q --upgrade pip
python -m pip install -q -r "$ROOT_DIR/backend/requirements.txt"
echo "   ✅ Python pakketten geïnstalleerd"

# === Node pakketten installeren ===
echo ""
echo "⚛️  Node.js pakketten installeren..."
(cd "$ROOT_DIR/chatbot_ui" && pnpm install --silent)
echo "   ✅ Node pakketten geïnstalleerd"

# === Mappen aanmaken ===
echo ""
echo "📁 Mappen aanmaken..."
mkdir -p "$ROOT_DIR/data"
mkdir -p "$ROOT_DIR/uploads"
echo "   ✅ data/ en uploads/ aangemaakt"

# === Ollama model downloaden ===
source "$ROOT_DIR/config.env" 2>/dev/null || true
MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
echo ""
echo "🦙 Ollama model downloaden: $MODEL"
echo "   (dit kan een paar minuten duren bij eerste keer)"
ollama serve &>/dev/null &
OLLAMA_PID=$!
sleep 3
ollama pull "$MODEL"
kill $OLLAMA_PID 2>/dev/null || true
echo "   ✅ Model $MODEL klaar"

# === Autostart via Windows Taakplanner ===
source "$ROOT_DIR/config.env" 2>/dev/null || true
if [ "${AUTOSTART:-false}" = "true" ]; then
    echo ""
    echo "⏰ Autostart instellen via Windows Taakplanner..."

    BASH_EXE="C:\\Program Files\\Git\\bin\\bash.exe"
    # Converteer pad naar Windows-formaat voor Task Scheduler
    WIN_ROOT=$(cygpath -w "$ROOT_DIR" 2>/dev/null || echo "$ROOT_DIR" | sed 's|/c/|C:\\|' | sed 's|/|\\|g')
    TASK_NAME="Kenniscapture"

    # Verwijder eventuele oude taak
    schtasks //Delete //TN "$TASK_NAME" //F &>/dev/null || true

    # Registreer nieuwe taak: start bij boot, hogere rechten
    schtasks //Create //TN "$TASK_NAME" \
        //TR "\"$BASH_EXE\" -c \"cd '$(echo $ROOT_DIR)' && ./start.sh\"" \
        //SC ONSTART \
        //RL HIGHEST \
        //F &>/dev/null

    if [ $? -eq 0 ]; then
        echo "   ✅ Taak '$TASK_NAME' geregistreerd — start automatisch bij Windows-herstart"
        echo "   Verwijderen: schtasks /Delete /TN Kenniscapture /F"
    else
        echo "   ⚠️  Taakplanner registratie mislukt — mogelijk admin-rechten nodig"
        echo "   Voer install.sh uit als Administrator"
    fi
fi

# === Klaar ===
echo ""
echo "=================================================="
echo "  ✅ Installatie voltooid!"
echo ""
echo "  Starten:       ./start.sh"
echo "  Stoppen:       ./stop.sh"
if [ "${AUTOSTART:-false}" = "true" ]; then
echo "  Autostart:     aan (start bij Windows-herstart)"
else
echo "  Autostart:     uit (zet AUTOSTART=true in config.env en herinstalleer)"
fi
echo "=================================================="