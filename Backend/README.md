## Voice Agent Backend

Single-file backend that can run as:

- **FastAPI server** (token generation, health endpoint)
- **LiveKit Agent worker** (voice pipeline with Cerebras LLM + Cartesia TTS)

### Setup

Create a virtual environment and install deps:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Note: the LiveKit agent/plugin wheels currently require **Python 3.12 or 3.13**. If you’re on Python 3.14, `pip` will refuse some packages with `Requires-Python <3.14`.

Copy env vars:

```bash
copy .env.example .env
```

Fill in values in `.env`.

### Run API

```bash
python voice_agent_backend.py api
```

Dev reload:

```bash
python voice_agent_backend.py api --reload
```

### Run Agent

Production:

```bash
python voice_agent_backend.py agent
```

If you get a Windows error like `WinError 10048` on port `8081`, set a different port in `.env`:

```text
AGENT_HTTP_PORT=18081
```

Dev hot reload:

```bash
python voice_agent_backend.py agent --dev
```

Console mode (local testing):

```bash
python voice_agent_backend.py agent --console
```

### Turn detector model (optional)

By default the agent runs **without** the turn detector (no extra model downloads).

To enable it:

1) Download model files:

```bash
python voice_agent_backend.py agent --download-files
```

2) Set in `.env`:

```text
USE_TURN_DETECTOR=1
```

