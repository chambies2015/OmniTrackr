"""Local, offline preview of Release Radar with fixture data.

    python -m tests.manual_release_radar_preview [--port 8011]

Uses a throwaway SQLite database and the JSON fixtures in tests/fixtures, with
"today" pinned to 2026-09-27 so the October / Fall 2026 fixtures are featured.
No network requests are made.
"""
import argparse
import os
import tempfile
from datetime import date

os.environ.setdefault("TESTING", "true")
os.environ["RELEASE_RADAR_CACHE_DIR"] = ""
if "DATABASE_URL" not in os.environ:
    _db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    os.environ["DATABASE_URL"] = f"sqlite:///{_db.name}"

from tests.release_radar_fixtures import install_fixture_providers  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    install_fixture_providers(today=date(2026, 9, 27))
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
