## Frontend (Vite + React)

This frontend:
- Calls your backend `POST /api/token`
- Connects to LiveKit using the returned `server_url` + `participant_token`

### Setup

```bash
cd Frontend
copy .env.example .env
npm install
```

### Run

```bash
npm run dev
```

Then open the printed local URL (usually `http://localhost:5173`).

### Notes

- Backend default is `http://localhost:8000` (configurable via `VITE_BACKEND_URL`)
- Your current backend auth accepts any non-empty bearer token; frontend uses `VITE_DEMO_BEARER_TOKEN`

