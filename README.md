# Initial Monorepo

Minimal monorepo with a FastAPI backend and a Vite React frontend.

## Structure

```text
.
├── backend/
├── frontend/
└── docs/
```

## Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

## Frontend

```bash
cd frontend
pnpm install
pnpm run dev
```

The frontend runs at `http://127.0.0.1:5173`.
