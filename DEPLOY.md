# Deployment: server + externe toegang via Cloudflare Tunnel

Doel: het systeem draaien op de server (bijv. `192.168.4.105`) en de
kenniscapture-tool, de chatbot én de API van buitenaf bereikbaar maken via
Cloudflare, zonder poorten open te zetten op de router.

> ⚠️ **Vertrouwelijke data.** De kennisbank bevat contractkennis. Zet de
> Cloudflare-hostnames ALTIJD achter **Cloudflare Access** (stap 5) voordat je
> de tunnel aanzet — anders staat alles open op het publieke internet.

## 1. Vereisten op de server

- Python 3.12, Node.js + pnpm, git
- Ollama met het model: `ollama pull llama3.1:8b`
- `cloudflared` ([installatie-instructies](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/))
- Een domein dat bij Cloudflare beheerd wordt

## 2. Installatie

```bash
git clone https://github.com/jeroenk22/kenniscapture.git
cd kenniscapture

# Backend
python -m venv backend/venv
backend/venv/Scripts/pip install -r backend/requirements.txt   # Windows
# of: backend/venv/bin/pip install -r backend/requirements.txt # Linux

# Chatbot
cd chatbot_ui && pnpm install && cd ..
```

## 3. Data meenemen van de oude machine

De kennisbank en de originele documenten staan buiten git. Kopieer van de
oude machine naar dezelfde paden op de server:

- `data/kennisbank.db` — de volledige kennisbank
- `uploads/` — de geüploade contractbestanden (nodig voor documentpreviews)

Doe dit terwijl de services op de oude machine **gestopt** zijn.

## 4. `config.env` op de server

Maak `config.env` in de projectroot (wordt niet gecommit):

```bash
# Luister op alle interfaces (nodig voor de tunnel)
HOST=0.0.0.0

# Publieke URLs (vervang <domein> door je eigen domein)
PUBLIC_API_BASE_URL=https://kc-api.<domein>
VITE_API_BASE=https://kc-api.<domein>
CORS_ORIGINS=https://kc-chat.<domein>,https://kc-kennisbank.<domein>

# Optioneel: Claude demo-provider
# ANTHROPIC_API_KEY=sk-ant-...
# LLM_PROVIDER=ollama
```

Wat deze doen:
- `VITE_API_BASE` — de chatbot in de browser roept de backend via deze
  publieke URL aan (i.p.v. `hostname:8000`, dat achter een tunnel niet werkt)
- `PUBLIC_API_BASE_URL` — documentpreview-links in Streamlit wijzen hierheen
- `CORS_ORIGINS` — de backend accepteert browser-verzoeken van deze origins

## 5. Cloudflare Tunnel + Access

```bash
cloudflared tunnel login
cloudflared tunnel create kenniscapture
```

Maak `~/.cloudflared/config.yml`:

```yaml
tunnel: kenniscapture
credentials-file: /pad/naar/<tunnel-id>.json

ingress:
  - hostname: kc-kennisbank.<domein>
    service: http://localhost:8501
  - hostname: kc-chat.<domein>
    service: http://localhost:5173
  - hostname: kc-api.<domein>
    service: http://localhost:8000
  - service: http_status:404
```

DNS-records aanmaken:

```bash
cloudflared tunnel route dns kenniscapture kc-kennisbank.<domein>
cloudflared tunnel route dns kenniscapture kc-chat.<domein>
cloudflared tunnel route dns kenniscapture kc-api.<domein>
```

**Toegang afschermen (verplicht):** ga in het Cloudflare-dashboard naar
*Zero Trust → Access → Applications* en maak voor **alle drie** de hostnames
een Self-hosted application met een policy die alleen de e-mailadressen van
het team toelaat (login via eenmalige e-mailcode). Zonder deze stap is de
kennisbank publiek.

Tunnel starten (en als service installeren zodat hij herstarts overleeft):

```bash
cloudflared tunnel run kenniscapture          # test
cloudflared service install                    # als systemd/Windows-service
```

## 6. Services starten

```bash
./start.sh
```

Controle:
- `https://kc-kennisbank.<domein>` → Streamlit (upload + vragen + kennisbank)
- `https://kc-chat.<domein>` → chatbot; een chatvraag moet streamend antwoorden
- Documentbadges/links openen previews via `https://kc-api.<domein>/...`

## Kanttekeningen

- **Chatbot draait via de Vite dev-server.** Werkt prima achter de tunnel,
  maar voor een echte productieopstelling is `pnpm build` + een statische
  webserver (of `pnpm vite preview --host --port 5173`) netter. `VITE_API_BASE`
  wordt bij `build` ingebakken — zet hem vóór het builden in de omgeving.
- **Intern gebruik blijft werken** zoals voorheen via
  `http://192.168.4.105:8501` en `:5173`, mits `HOST=0.0.0.0` gezet is —
  intern verkeer gaat dan niet via Cloudflare. NB: de chatbot gebruikt dan wél
  `VITE_API_BASE` (de publieke API-URL); wie intern werkt zonder internet moet
  die variabele leeg laten.
- **Ollama-snelheid**: op een server zonder GPU blijft de analyse minuten per
  contract duren; de Claude-switch is daar de demo-oplossing voor.
