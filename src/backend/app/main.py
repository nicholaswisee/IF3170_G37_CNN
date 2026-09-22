from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.experiments import router as experiments_router
from app.api.health import router as health_router
from app.config import settings

app = FastAPI(title="Mejiro Express Optimization API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(experiments_router)
