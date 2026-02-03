"""
Application configuration using pydantic-settings.
"""

import os
import tempfile
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # CORS
    allowed_origins: str = "*"
    
    # Turnstile (Cloudflare CAPTCHA)
    turnstile_secret_key: str = ""
    
    # S3 bucket for file downloads
    s3_bucket_name: str = "sat-data-viewer-downloads"
    s3_region: str = "eu-north-1"
    presigned_url_expiry: int = 600  # 10 minutes
    
    # File limits
    max_file_size_mb: int = 1500  # 1.5 GB max
    
    # Temporary storage (Lambda /tmp on Linux, system temp on Windows)
    tmp_dir: str = tempfile.gettempdir() if os.name == 'nt' else "/tmp"
    
    # Microsoft Planetary Computer
    mpc_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    
    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
