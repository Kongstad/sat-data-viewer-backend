"""
Cloudflare Turnstile verification for bot protection.
"""

import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile_token(token: str, client_ip: str = None) -> bool:
    """
    Verify a Turnstile token with Cloudflare's API.
    
    Args:
        token: The Turnstile token from the frontend
        client_ip: Optional client IP for additional verification
        
    Returns:
        True if verification passed, False otherwise
    """
    if not settings.turnstile_secret_key:
        logger.warning("Turnstile secret key not configured, skipping verification")
        return True  # Allow if not configured (for development)
    
    if not token:
        logger.warning("No Turnstile token provided")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "secret": settings.turnstile_secret_key,
                "response": token,
            }
            
            if client_ip:
                payload["remoteip"] = client_ip
            
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data=payload,
                timeout=10.0
            )
            
            result = response.json()
            
            if result.get("success"):
                logger.info("Turnstile verification passed")
                return True
            else:
                error_codes = result.get("error-codes", [])
                logger.warning(f"Turnstile verification failed: {error_codes}")
                return False
                
    except Exception as e:
        logger.error(f"Turnstile verification error: {e}")
        # On error, fail closed (deny request) for security
        return False
