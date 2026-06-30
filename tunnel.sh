#!/usr/bin/env bash
# Start Cloudflare Tunnels voor externe toegang
# Vereist: cloudflared geïnstalleerd (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
# Windows: winget install Cloudflare.cloudflared

if ! command -v cloudflared &>/dev/null; then
    echo "❌ cloudflared niet gevonden."
    echo ""
    echo "Installeren op Windows:"
    echo "   winget install Cloudflare.cloudflared"
    echo ""
    echo "Of download via: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    exit 1
fi

source "$(dirname "$0")/config.env" 2>/dev/null || true
PORT_CHATBOT="${PORT_CHATBOT:-5173}"
PORT_STREAMLIT="${PORT_STREAMLIT:-8501}"

echo "🌐 Cloudflare Tunnels starten..."
echo "   (even wachten op de publieke URLs)"
echo ""

# Start tunnels op de achtergrond en vang URLs op
cloudflared tunnel --url "http://localhost:$PORT_CHATBOT" --no-autoupdate 2>&1 \
    | grep --line-buffered "trycloudflare.com" \
    | while read -r line; do
        URL=$(echo "$line" | grep -o 'https://[^ ]*trycloudflare.com')
        if [ -n "$URL" ]; then
            echo "  💬 Chatbot (vervanger):      $URL"
        fi
    done &

cloudflared tunnel --url "http://localhost:$PORT_STREAMLIT" --no-autoupdate 2>&1 \
    | grep --line-buffered "trycloudflare.com" \
    | while read -r line; do
        URL=$(echo "$line" | grep -o 'https://[^ ]*trycloudflare.com')
        if [ -n "$URL" ]; then
            echo "  📝 Kenniscapture (invoer):   $URL"
        fi
    done &

echo "Wacht op URLs..."
sleep 8
echo ""
echo "Deel bovenstaande URLs met de externe gebruiker."
echo "Stop tunnels met: Ctrl+C"
wait
