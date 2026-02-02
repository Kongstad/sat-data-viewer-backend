"""
Simple startup script for local development
Run with: uv run python run_local.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv/*", "*.pyc", "__pycache__/*"],
        log_level="info"
    )
