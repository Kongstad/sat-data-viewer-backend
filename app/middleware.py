"""
Middleware for request tracking, rate limiting, and monitoring.
"""

import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestTracker:
    """Track requests for monitoring and rate limiting."""
    
    def __init__(self):
        self.requests = defaultdict(list)  # IP -> list of timestamps
        self.downloads = defaultdict(list)  # IP -> list of (timestamp, size_mb)
    
    def check_rate_limit(self, ip: str, max_requests: int = 10, window_minutes: int = 1) -> bool:
        """Check if IP is within rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=window_minutes)
        
        # Clean old requests
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]
        
        # Check limit
        if len(self.requests[ip]) >= max_requests:
            return False
        
        self.requests[ip].append(now)
        return True
    
    def check_download_quota(self, ip: str, max_mb_per_hour: int = 5000) -> bool:
        """Check if IP is within download quota."""
        now = datetime.now()
        cutoff = now - timedelta(hours=1)
        
        # Clean old downloads
        self.downloads[ip] = [(ts, size) for ts, size in self.downloads[ip] if ts > cutoff]
        
        # Calculate total MB downloaded in last hour
        total_mb = sum(size for _, size in self.downloads[ip])
        
        return total_mb < max_mb_per_hour
    
    def record_download(self, ip: str, size_bytes: int):
        """Record a download for quota tracking."""
        size_mb = size_bytes / (1024 * 1024)
        self.downloads[ip].append((datetime.now(), size_mb))
    
    def get_stats(self, ip: str) -> dict:
        """Get usage stats for an IP."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        recent_downloads = [(ts, size) for ts, size in self.downloads[ip] if ts > hour_ago]
        total_mb = sum(size for _, size in recent_downloads)
        
        return {
            "downloads_last_hour": len(recent_downloads),
            "mb_downloaded_last_hour": round(total_mb, 2),
            "requests_last_minute": len([ts for ts in self.requests[ip] if ts > now - timedelta(minutes=1)])
        }


# Global tracker instance
tracker = RequestTracker()


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging and monitoring."""
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip health checks from logging
        if request.url.path == "/health":
            return await call_next(request)
        
        # Rate limiting for download endpoints
        if request.url.path.startswith("/download"):
            if not tracker.check_rate_limit(client_ip, max_requests=10, window_minutes=1):
                logger.warning(f"[RATE_LIMIT] IP {client_ip} exceeded rate limit")
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a minute and try again."
                )
            
            if not tracker.check_download_quota(client_ip, max_mb_per_hour=5000):
                logger.warning(f"[QUOTA] IP {client_ip} exceeded download quota")
                raise HTTPException(
                    status_code=429,
                    detail="Download quota exceeded. Please wait an hour and try again."
                )
        
        # Log request start
        start_time = time.time()
        logger.info(f"[REQUEST] {request.method} {request.url.path} from {client_ip}")
        
        # Process request
        response = await call_next(request)
        
        # Log request completion with timing
        duration = time.time() - start_time
        logger.info(
            f"[RESPONSE] {request.method} {request.url.path} "
            f"status={response.status_code} duration={duration:.2f}s"
        )
        
        # Add custom headers for monitoring
        response.headers["X-Request-Duration"] = f"{duration:.3f}"
        response.headers["X-Request-ID"] = str(int(start_time * 1000))
        
        return response
