"""MedGuard AI - FastAPI Backend Application."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from dotenv import load_dotenv
from routes import analyze, patient_safety, dashboard
from services.mongo import connect_to_mongo, close_mongo_connection

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Multi-provider AI architecture initialization
# Works in local OCR-first mode without provider keys.
# Optional cloud providers: OPENAI_API_KEY, GOOGLE_API_KEY, GROQ_API_KEY, OCR_SPACE_API_KEY
# See .env.example for configuration details

# Create FastAPI app
app = FastAPI(
    title="MedGuard AI API",
    description="Intelligent Fake Medicine & Patient Safety System",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "https://localhost",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "medguard-backend",
        "version": "1.0.0"
    }


# Include routers under a single API root.
# Each router already has its own functional prefix (e.g. /analyze),
# so mounting at /api avoids duplicated paths like /api/analyze/analyze.
app.include_router(analyze.router, prefix="/api")
app.include_router(patient_safety.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.on_event("startup")
async def _on_startup():
    logger.info("Starting up application; connecting to MongoDB if configured")
    await connect_to_mongo(app)


@app.on_event("shutdown")
async def _on_shutdown():
    logger.info("Shutting down application; closing MongoDB connection")
    await close_mongo_connection(app)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler."""
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "details": str(exc) if os.getenv("DEBUG") else "An unexpected error occurred",
            "path": str(request.url),
        },
    )


# Root endpoint
@app.get("/", tags=["info"])
async def root():
    """API information endpoint."""
    return {
        "name": "MedGuard AI API",
        "description": "Intelligent Fake Medicine & Patient Safety System",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/analyze",
            "patient_safety": "/api/patient-safety",
            "dashboard": "/api/dashboard",
            "docs": "/api/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting MedGuard AI API on port {port}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
