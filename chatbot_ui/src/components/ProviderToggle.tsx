import { useEffect, useState } from "react";
import { getSettings, type LlmSettings, setProvider } from "../api";

export default function ProviderToggle() {
  const [settings, setSettings] = useState<LlmSettings | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => setSettings(null));
  }, []);

  if (!settings) return null;

  const isClaude = settings.provider === "claude";

  const handleToggle = async () => {
    if (busy) return;
    const next = isClaude ? "ollama" : "claude";
    setBusy(true);
    try {
      await setProvider(next);
      setSettings({ ...settings, provider: next });
    } catch {
      // switch mislukt (bijv. geen API-key) — huidige stand behouden
    } finally {
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
