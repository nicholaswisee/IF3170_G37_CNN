from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.experiments import router as experiments_router
from app.api.health import router as health_router
from app.api.limits import router as limits_router
from app.api.problems import router as problems_router
from app.api.request_limits import RunBodyLimitMiddleware
from app.config import settings

app = FastAPI(title="mejirowise Optimization API", version="0.1.0")
app.add_middleware(RunBodyLimitMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error_response(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    detail = [
        {key: error[key] for key in ("type", "loc", "msg")}
        for error in exception.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(limits_router)
app.include_router(problems_router)
app.include_router(experiments_router)
