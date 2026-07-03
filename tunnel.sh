#!/usr/bin/env bash
# Externe toegang via Cloudflare quick tunnels (gratis, geen account nodig).
#
# Start drie tunnels — kennisbank (Streamlit), chatbot (Vite) én backend-API —
# en herstart de services met de juiste publieke URLs (via tunnel.env), zodat
# de chat en documentpreviews ook extern werken.
#
# Gebruik:  ./tunnel.sh
# Stoppen:  Ctrl+C — tunnel.env wordt opgeruimd; draai daarna eenmalig
#           ./stop.sh && ./start.sh om weer op interne URLs te draaien.
#
# Let op: de *.trycloudflare.com-URLs wisselen bij elke start. Voor vaste
# URLs (en toegangsafscherming) zie DEPLOY.md — named tunnel met eigen domein.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v cloudflared &>/dev/null; then
    echo "❌ cloudflared niet gevonden."
    echo ""
    echo "Installeren op Windows:"
    echo "   winget install Cloudflare.cloudflared"
    echo ""
    echo "Of download via: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
fi

set -a
source "$ROOT_DIR/config.env" 2>/dev/null || true
set +a
PORT_BACKEND="${PORT_BACKEND:-8000}"
PORT_STREAMLIT="${PORT_STREAMLIT:-8501}"
PORT_CHATBOT="${PORT_CHATBOT:-5173}"
BASIS_CORS="${CORS_ORIGINS:-}"

LOG_DIR=$(mktemp -d)
PIDS=()

start_tunnel() {
    local port=$1 log=$2
    # 127.0.0.1 en niet localhost: op Windows lost localhost op naar ::1
    # (IPv6) terwijl de services op IPv4 luisteren — dat geeft een 502
    cloudflared tunnel --url "http://127.0.0.1:$port" --no-autoupdate >"$log" 2>&1 &
    PIDS+=($!)
}

wacht_op_url() {
    local log=$1 url=""
    for _ in $(seq 1 30); do
        url=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' "$log" 2>/dev/null | head -1)
        if [ -n "$url" ]; then
            echo "$url"
            return 0
        fi
        sleep 1
    done
    return 1
}

opruimen() {
    echo ""
    echo "🛑 Tunnels stoppen..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    rm -f "$ROOT_DIR/tunnel.env"
    rm -rf "$LOG_DIR"
    echo "   tunnel.env opgeruimd. Herstart de services met:"
    echo "   ./stop.sh && ./start.sh   (weer puur interne URLs)"
}
trap opruimen EXIT

echo "🌐 Quick tunnels starten (kan ±15 sec duren)..."
start_tunnel "$PORT_BACKEND"   "$LOG_DIR/api.log"
start_tunnel "$PORT_STREAMLIT" "$LOG_DIR/kennisbank.log"
start_tunnel "$PORT_CHATBOT"   "$LOG_DIR/chat.log"

API_URL=$(wacht_op_url "$LOG_DIR/api.log")       || { echo "❌ API-tunnel kreeg geen URL — zie $LOG_DIR/api.log"; exit 1; }
KB_URL=$(wacht_op_url "$LOG_DIR/kennisbank.log") || { echo "❌ Kennisbank-tunnel kreeg geen URL"; exit 1; }
CHAT_URL=$(wacht_op_url "$LOG_DIR/chat.log")     || { echo "❌ Chatbot-tunnel kreeg geen URL"; exit 1; }

CORS="$CHAT_URL"
if [ -n "$BASIS_CORS" ]; then
    CORS="$BASIS_CORS,$CHAT_URL"
fi

cat > "$ROOT_DIR/tunnel.env" <<EOF
# Automatisch gegenereerd door tunnel.sh — niet handmatig aanpassen.
# start.sh laadt dit bovenop config.env; bij het stoppen van tunnel.sh
# wordt dit bestand weer verwijderd.
VITE_API_BASE=$API_URL
PUBLIC_API_BASE_URL=$API_URL
CORS_ORIGINS=$CORS
EOF

echo "♻️  Services herstarten met de publieke URLs..."
"$ROOT_DIR/stop.sh" >/dev/null 2>&1 || true
nohup "$ROOT_DIR/start.sh" >"$LOG_DIR/services.log" 2>&1 &
PIDS+=($!)

echo ""
echo "=================================================="
echo "  Extern bereikbaar — deel deze links:"
echo "  📝 Kenniscapture:  $KB_URL"
echo "  💬 Chatbot:        $CHAT_URL"
echo "     (backend-API:   $API_URL)"
echo "=================================================="
echo ""
echo "⚠️  Deze URLs wisselen bij elke start van tunnel.sh."
echo "⚠️  Iedereen met de link kan erbij — alleen voor demo's met fictieve data."
echo "💡 Verse URLs kunnen 1-2 minuten nodig hebben voordat DNS overal werkt."
echo ""
echo "Stop tunnels met: Ctrl+C"
wait
