#!/usr/bin/env bash
# Stop alle Kenniscapture services

echo "🛑 Stoppen van alle services..."

pkill -f "uvicorn main:app" 2>/dev/null && echo "   ✅ FastAPI backend gestopt" || echo "   ⚠️  Backend was niet actief"
pkill -f "streamlit run app.py" 2>/dev/null && echo "   ✅ Streamlit gestopt"     || echo "   ⚠️  Streamlit was niet actief"
pkill -f "vite"                 2>/dev/null && echo "   ✅ React (Vite) gestopt"   || echo "   ⚠️  React was niet actief"

echo ""
echo "✅ Klaar"