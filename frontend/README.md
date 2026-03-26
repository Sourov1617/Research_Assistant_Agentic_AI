# Research Assistant Frontend

This frontend now talks directly to the FastAPI backend instead of the old
Streamlit flow.

## What it supports

- dynamic bootstrap from `GET /config`
- async research jobs through `POST /research/jobs`
- live progress via Server-Sent Events from
  `GET /research/jobs/{job_id}/events`
- stop requests through `POST /research/jobs/{job_id}/stop`
- fetch-more rounds using `fetch_round`
- memory session list/detail screens through `/memory/sessions`

## Local setup

1. Start the backend from the project root:

```bash
uv run python api.py
```

2. In this `frontend` folder, install and run:

```bash
npm install
npm run dev
```

3. Open `http://localhost:3000`

## Environment

Set the backend URL if needed:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

If not set, the frontend defaults to `http://localhost:8000`.

## Verification

- `npm run lint`
- `npm run build`
