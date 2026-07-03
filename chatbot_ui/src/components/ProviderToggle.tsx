import { useEffect, useRef, useState } from "react";
import { getSettings, type LlmSettings, setProvider } from "../api";

// Interval waarmee de providerstand bij de backend wordt ververst, zodat een
// switch vanuit de Streamlit-sidebar hier vanzelf zichtbaar wordt (en andersom)
const POLL_INTERVAL_MS = 3000;

export default function ProviderToggle() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  useEffect(() => {
    let actief = true;
    const laadSettings = () => {
      getSettings()
        .then((s) => {
          // Niet overschrijven terwijl een eigen switch onderweg is
          if (actief && !busyRef.current) setSettings(s);
        })
        .catch(() => {
          if (actief && !busyRef.current) setSettings(null);
        });
    };
    laadSettings();
    const interval = setInterval(laadSettings, POLL_INTERVAL_MS);
    return () => {
      actief = false;
      clearInterval(interval);
    };
  }, []);

  if (!settings) return null;

  const isClaude = settings.provider === "claude";

  const handleToggle = async () => {
    if (busy) return;
    const next = isClaude ? "ollama" : "claude";
    setBusy(true);
    busyRef.current = true;
    try {
      await setProvider(next);
      setSettings({ ...settings, provider: next });
    } catch {
      // switch mislukt (bijv. geen API-key) — huidige stand behouden
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">AI-model:</span>
        <button
          type="button"
          onClick={handleToggle}
          disabled={busy || (!isClaude && !settings.claude_available)}
          title={
            !isClaude && !settings.claude_available
              ? "Zet ANTHROPIC_API_KEY in config.env om Claude te gebruiken"
              : isClaude
                ? "Terug naar lokale Ollama"
                : "Switch naar Claude (cloud, demo)"
          }
          className="text-xs px-3 py-1 rounded-full border border-gray-300 bg-white hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isClaude ? "⚡ Claude (cloud)" : "🔒 Ollama (lokaal)"}
        </button>
      </div>
      {isClaude && (
        <span className="text-xs text-amber-600">Data gaat naar Anthropic — alleen voor demo</span>
      )}
    </div>
  );
}
