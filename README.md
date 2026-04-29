# LiveKit Voice Agent

A full-stack real-time voice assistant that lets you speak with an AI in your browser.

**Stack:**
- **Frontend** — React + TypeScript + Vite
- **Backend** — Python + FastAPI
- **Voice Pipeline** — Deepgram (STT) → Cerebras LLM → Cartesia (TTS)
- **Real-time Transport** — LiveKit Cloud (WebRTC)

---

## How It Works

```
Browser (React)
    │
    ├─ POST /api/token ──► FastAPI Backend ──► LiveKit Cloud
    │                                               │
    └─ WebRTC connection ───────────────────────────┤
                                                    │
                                             Agent Worker (Python)
                                                    │
                                       ┌────────────┼────────────┐
                                    Deepgram      Cerebras    Cartesia
                                    (Speech       (LLM)       (Text to
                                    to Text)                   Speech)
```

1. User clicks **Connect** in the browser
2. Frontend calls `POST /api/token` on the FastAPI backend
3. Backend generates a LiveKit JWT and embeds an agent dispatch instruction
4. Frontend connects to LiveKit Cloud using the token
5. LiveKit Cloud dispatches the agent worker into the room
6. Agent greets the user and listens — Deepgram transcribes speech, Cerebras generates a reply, Cartesia speaks it back

---

## Prerequisites

- Python **3.12 or 3.13** (not 3.14 — LiveKit plugins don't support it yet)
- Node.js 18+
- Accounts and API keys for:
  - [LiveKit Cloud](https://cloud.livekit.io)
  - [Cerebras](https://cloud.cerebras.ai)
  - [Deepgram](https://deepgram.com) *(used via LiveKit plugin)*
  - [Cartesia](https://cartesia.ai) *(used via LiveKit Inference — no separate key needed by default)*

---

## Project Structure

```
Livekit/
├── Backend/
│   ├── voice_agent_backend.py   # Single-file backend (FastAPI + Agent worker)
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                     # Your secrets (not committed)
├── Frontend/
│   ├── src/
│   │   ├── ui/
│   │   │   ├── App.tsx          # Main UI + LiveKit room logic
│   │   │   ├── TokenForm.tsx    # Connect form
│   │   │   └── useVoiceToken.ts # Hook for token API call
│   │   ├── main.tsx
│   │   └── styles.css
│   ├── .env.example
│   └── .env                     # Your frontend config (not committed)
└── README.md
```

---

## Setup

### 1. Backend

```bash
cd Backend

# Create virtual environment (use Python 3.12 or 3.13)
py -3.12 -m venv .venv
.venv\Scripts\activate.bat      # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

Edit `Backend/.env` and fill in your keys:

```env
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_URL=wss://your-project.livekit.cloud

CEREBRAS_API_KEY=csk_xxx_your_key
CEREBRAS_MODEL=llama3.1-8b
```

### 2. Frontend

```bash
cd Frontend

npm install

copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

`Frontend/.env` defaults work out of the box if your backend runs on port 8000:

```env
VITE_BACKEND_URL=http://localhost:8000
VITE_DEMO_BEARER_TOKEN=demo
```

---

## Running Locally

You need **three terminals**:

**Terminal 1 — FastAPI backend (token generation)**
```bash
cd Backend
.venv\Scripts\activate.bat
python voice_agent_backend.py api
```

**Terminal 2 — Agent worker (voice pipeline)**
```bash
cd Backend
.venv\Scripts\activate.bat
python voice_agent_backend.py agent --dev
```

**Terminal 3 — Frontend**
```bash
cd Frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Usage

1. Enter your name and an optional room name, then click **Connect**
2. Allow microphone permission when the browser asks
3. Click **Unmute mic** to start speaking
4. The agent will greet you and respond to anything you say
5. Say `/help` to hear what the agent can assist with
6. Click **Disconnect** when done

---

## Common Issues

| Problem | Fix |
|---|---|
| `WinError 10048` on agent start | Port 8081 is in use. Set `AGENT_HTTP_PORT=18081` in `Backend/.env` |
| `Requires-Python <3.14` pip error | Use Python 3.12 or 3.13 to create the venv |
| Peers stays at 0 | Make sure the agent worker terminal shows `registered worker` |
| No audio from agent | Click **Unmute mic** and allow browser microphone permission |
| PowerShell won't activate venv | Run `.venv\Scripts\activate.bat` instead of the `.ps1` script |

---

## Environment Variables Reference

### Backend (`Backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `LIVEKIT_API_KEY` | Yes | LiveKit Cloud API key |
| `LIVEKIT_API_SECRET` | Yes | LiveKit Cloud API secret |
| `LIVEKIT_URL` | Yes | LiveKit Cloud WebSocket URL |
| `CEREBRAS_API_KEY` | Yes | Cerebras API key |
| `CEREBRAS_MODEL` | No | LLM model (default: `llama3.1-8b`) |
| `CEREBRAS_TEMPERATURE` | No | Sampling temperature (default: `0.7`) |
| `AGENT_HTTP_PORT` | No | Agent health check port (default: `8081`) |
| `USE_TURN_DETECTOR` | No | Enable turn detection model (default: `0`) |
| `CORS_ORIGINS` | No | Allowed CORS origins (default: `*`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Frontend (`Frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_BACKEND_URL` | Backend URL (default: `http://localhost:8000`) |
| `VITE_DEMO_BEARER_TOKEN` | Auth token sent to backend (default: `demo`) |
