#!/usr/bin/env bash
# Stop alle Kenniscapture services
# Werkt ook op Windows/Git Bash zonder pkill (valt terug op PowerShell + taskkill)

echo "🛑 Stoppen van alle services..."

stop_processen() {
    local patroon=$1 naam=$2

    if command -v pkill &>/dev/null; then
        if pkill -f "$patroon" 2>/dev/null; then
            echo "   ✅ $naam gestopt"
        else
            echo "   ⚠️  $naam was niet actief"
        fi
        return
    fi

    # Git Bash zonder pkill: zoek PIDs op commandline via PowerShell.
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

stop_processen "uvicorn main:app"      "FastAPI backend"
stop_processen "streamlit run app.py"  "Streamlit"
stop_processen "vite"                  "React (Vite)"

echo ""
echo "✅ Klaar"
