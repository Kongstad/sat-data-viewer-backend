"""
Satellite Data Viewer Backend
FastAPI application for downloading satellite imagery from Microsoft Planetary Computer.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.routes import router
from app.config import settings
from app.middleware import MonitoringMiddleware, tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print(f"Starting Satellite Data Viewer Backend")
    print(f"Max file size: {settings.max_file_size_mb} MB")
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="Satellite Data Viewer Backend",
    description="Download satellite imagery from Microsoft Planetary Computer",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS is handled by AWS Lambda Function URL configuration
# Do NOT add CORSMiddleware here to avoid duplicate headers

# Monitoring and rate limiting
app.add_middleware(MonitoringMiddleware)

# Include routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/stats")
async def usage_stats(request: Request):
    """Get usage statistics for the current client."""
    client_ip = request.client.host if request.client else "unknown"
    stats = tracker.get_stats(client_ip)
    return {
        "ip": client_ip,
        "usage": stats,
        "limits": {
            "requests_per_minute": 10,
            "mb_per_hour": 5000
        }
    }


# AWS Lambda handler with response streaming support
def handler(event, context):
    """
    Lambda handler that routes between HTTP requests and scheduled deletions.
    """
    # Check if this is a scheduled deletion event
    if isinstance(event, dict) and event.get('action') == 'delete_s3_object':
        from app.s3_utils import delete_from_s3
        bucket = event.get('bucket')
        key = event.get('key')
        if bucket and key:
            print(f"Scheduled deletion: {bucket}/{key}")
            delete_from_s3(key)
            return {'statusCode': 200, 'body': 'Deleted'}
    
    # Otherwise, handle as HTTP request
    return Mangum(app, lifespan="on")(event, context)
