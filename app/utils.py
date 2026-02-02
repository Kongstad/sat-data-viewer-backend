"""
Utility functions for the backend.
"""

import os
from typing import Generator
from contextlib import contextmanager


def get_content_type(format: str) -> str:
    """Get MIME content type for a format."""
    content_types = {
        "geotiff": "image/tiff",
        "tif": "image/tiff",
        "png": "image/png",
    }
    return content_types.get(format.lower(), "application/octet-stream")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def generate_filename(
    collection: str,
    item_id: str,
    asset_key: str,
    format: str,
) -> str:
    """Generate a descriptive filename for download."""
    # Truncate item_id if too long
    if len(item_id) > 50:
        item_id = item_id[:50]
    
    extension = "tif" if format.lower() == "geotiff" else format.lower()
    return f"{collection}_{item_id}_{asset_key}.{extension}"


@contextmanager
def temporary_file(file_path: str) -> Generator[str, None, None]:
    """Context manager that ensures file cleanup."""
    try:
        yield file_path
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass  # Ignore cleanup errors in Lambda


def ensure_tmp_dir() -> str:
    """Ensure the tmp directory exists and return its path."""
    tmp_dir = os.environ.get("TMP_DIR", "/tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return tmp_dir
