import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limit import check_rate_limit, get_client_ip

logger = logging.getLogger("proctoring.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Initialize Sentry Error Tracking if DSN configured
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.2,
        )
        logger.info("Sentry monitoring telemetry active.")
    except ImportError:
        logger.warning("sentry-sdk not installed; SENTRY_DSN was provided but skipping Sentry init.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode...")
    yield
    # Shutdown actions
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Online Exam Proctoring & Assessment Engine - Phase 1 Foundation API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Request latency & error monitoring middleware
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(process_time)
        return response
    except Exception as exc:
        process_time = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            f"Unhandled server error on {request.method} {request.url.path} after {process_time}ms: {exc}",
            exc_info=True,
        )
        raise exc

# Tiered Rate Limiting Middleware
@app.middleware("http")
async def tiered_rate_limiting_middleware(request: Request, call_next):
    # Allow CORS preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path

    # Endpoints with dedicated auth/session rate limiting or open docs
    if path.startswith(f"{settings.API_V1_STR}/auth"):
        return await call_next(request)
    if path in ("/docs", "/redoc", f"{settings.API_V1_STR}/openapi.json"):
        return await call_next(request)

    client_ip = get_client_ip(request)
    auth_header = request.headers.get("authorization")

    try:
        if auth_header and auth_header.lower().startswith("bearer "):
            # Authenticated tier: looser limit per token identifier
            token_key = auth_header[7:].strip()[-16:]
            check_rate_limit(
                key=token_key,
                action="auth_general_tier",
                max_requests=settings.RATE_LIMIT_AUTHENTICATED_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS,
                error_message="Too many requests. Please slow down your interactions.",
            )
        else:
            # Public / Unauthenticated tier: moderate limit per IP
            check_rate_limit(
                key=client_ip,
                action="public_tier",
                max_requests=settings.RATE_LIMIT_PUBLIC_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_PUBLIC_WINDOW_SECONDS,
                error_message="Too many requests from this network. Please wait before retrying.",
            )
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )

    return await call_next(request)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    return {
        "title": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
