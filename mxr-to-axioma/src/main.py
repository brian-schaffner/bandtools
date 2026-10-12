"""Main entry point for MXR-to-Axioma translator."""

import uvicorn

from .config import settings, ensure_directories
from .web_ui.app import create_app


def main():
    """Run the application."""
    ensure_directories()
    app = create_app()

    print(f"\n{'='*60}")
    print(f"  MXR-to-Axioma Preset Translator")
    print(f"  Version 0.1.0")
    print(f"{'='*60}")
    print(f"\n  Starting server at http://{settings.host}:{settings.port}")
    print(f"  Press Ctrl+C to stop\n")

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
