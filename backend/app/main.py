# =============================================================================
# main.py
# FastAPI application entry point.
# =============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .config_settings import settings
from .routers import upload, cases, calculate, reports, auth, reference

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="StudyLink Bonus Engine",
    description="Automated bonus calculation for StudyLink counsellors and COs.",
    version="1.0.1",
)

# CORS — allows the Netlify frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bonusengine.netlify.app", "https://bonusengine.up.railway.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(upload.router,    prefix="/api/upload",    tags=["Upload"])
app.include_router(cases.router,     prefix="/api/cases",     tags=["Cases"])
app.include_router(calculate.router, prefix="/api/calculate", tags=["Calculate"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["Reports"])
app.include_router(reference.router, prefix="/api/reference", tags=["Reference"])


@app.get("/")
def root():
    return {"status": "ok", "service": "StudyLink Bonus Engine"}


@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
