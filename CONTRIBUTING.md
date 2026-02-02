# Contributing

Thanks for your interest in contributing!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Kongstad/sat-data-viewer-backend.git
cd sat-data-viewer-backend

# Install dependencies
uv sync --link-mode=copy

# Run locally
uv run python run_local.py
```

## Pull Requests

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/thing`)
3. Make your changes
4. Test locally
5. Commit with clear messages
6. Push and open a PR

## Code Style

- Follow PEP 8
- Use type hints where helpful
- Keep functions focused and documented
- Add tests for new features

## Testing

Run tests before submitting:
```bash
uv run pytest tests/ -v
```

## Questions?

Open an issue or reach out via GitHub Discussions.
