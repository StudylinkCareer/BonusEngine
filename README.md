# StudyLink Bonus Engine

Automated bonus calculation for StudyLink counsellors and case officers.

## Stack

| Layer    | Technology          | Platform |
|----------|---------------------|----------|
| Backend  | Python 3.11 / FastAPI | Railway |
| Database | PostgreSQL          | Railway  |
| Frontend | React / Vite        | Netlify  |

## Project Structure

```
BonusEngine/
├── backend/
│   ├── app/
│   │   ├── engine/          # Calculation logic (Python port of VBA engine)
│   │   │   ├── constants.py
│   │   │   ├── config.py
│   │   │   ├── input.py
│   │   │   ├── calc.py
│   │   │   └── output.py
│   │   ├── routers/         # FastAPI endpoints
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── database.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    └── src/
        ├── pages/
        ├── components/
        └── api/
```

## Local Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # Edit with your settings
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (min 32 chars) |
| `ALLOWED_ORIGINS` | Comma-separated frontend URLs |

## Deployment

- **Railway**: connects to GitHub, auto-deploys `backend/` on push to `main`
- **Netlify**: connects to GitHub, auto-deploys `frontend/` on push to `main`

Set `VITE_API_URL` in Netlify environment variables to your Railway backend URL.
