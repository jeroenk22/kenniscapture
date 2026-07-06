#!/usr/bin/env bash
# Stop alle Kenniscapture services
# Werkt ook op Windows/Git Bash zonder pkill (valt terug op PowerShell + taskkill)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Poorten uit config.env, voor de poortveegpas hieronder
sed -i 's/\r$//' "$ROOT_DIR/config.env" 2>/dev/null || true
source "$ROOT_DIR/config.env" 2>/dev/null || true
PORT_BACKEND="${PORT_BACKEND:-8000}"
PORT_STREAMLIT="${PORT_STREAMLIT:-8501}"
PORT_CHATBOT="${PORT_CHATBOT:-5173}"

echo "🛑 Stoppen van alle services..."

op_windows() {
    [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]
}

stop_processen() {
    local patroon=$1 naam=$2

    # pkill alleen op echt Unix: de pkill van MSYS/Git Bash ziet native
    # Windows-processen (uvicorn.exe, node.exe) niet en meldt dan ten
    # onrechte "niet actief" zonder iets te stoppen
    if ! op_windows && command -v pkill &>/dev/null; then
        if pkill -f "$patroon" 2>/dev/null; then
            echo "   ✅ $naam gestopt"
        else
            echo "   ⚠️  $naam was niet actief"
        fi
        return
    fi

    # Windows: zoek PIDs op commandline via PowerShell.
    # Eigen PowerShell-proces uitsluiten (de commandline bevat het patroon zelf).
    local pids
    pids=$(powershell -NoProfile -Command \
        "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match '$patroon' -and \$_.ProcessId -ne \$PID } | Select-Object -ExpandProperty ProcessId" 2>/dev/null | tr -d '\r')

    if [ -n "$pids" ]; then
        for pid in $pids; do
            taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
        done
        echo "   ✅ $naam gestopt"
    else
        echo "   ⚠️  $naam was niet actief"
    fi
}

# Vangnet ná de patroonmatching: die kan processen missen (afwijkende
# commandline via een package-runner, of een service die naar een andere
# poort is uitgeweken). Het doel van dit script is de servicepoorten
# vrijmaken — ruim dus alles op wat daar nog op luistert. cloudflared
# blijft buiten schot: tunnels luisteren niet op deze poorten.
poort_vrijmaken() {
    local poort=$1
    command -v powershell &>/dev/null || return 0
    local pids
    pids=$(powershell -NoProfile -Command \
        "Get-NetTCPConnection -LocalPort $poort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique" 2>/dev/null | tr -d '\r')
    for pid in $pids; do
        if taskkill //F //T //PID "$pid" >/dev/null 2>&1; then
            echo "   ✅ poort $poort vrijgemaakt (PID $pid)"
        fi
    done
}

# '.*' tussen commando en argumenten: op Windows is de commandline
# 'C:\...\Scripts\uvicorn.exe main:app ...' — een spatie-patroon als
# 'uvicorn main:app' matcht daar nooit op, waardoor de backend elke
# herstart overleefde met verouderde env vars (o.a. CORS_ORIGINS)
stop_processen "uvicorn.*main:app"      "FastAPI backend"
stop_processen "streamlit.*run app.py"  "Streamlit"
stop_processen "vite"                   "React (Vite)"

poort_vrijmaken "$PORT_BACKEND"
poort_vrijmaken "$PORT_STREAMLIT"
poort_vrijmaken "$PORT_CHATBOT"
# +1 is de poort waarnaar Vite vóór --strictPort stilletjes uitweek als de
# eigen poort bezet was; oude uitgeweken instanties ook opruimen
poort_vrijmaken "$((PORT_CHATBOT + 1))"

echo ""
echo "✅ Klaar"
