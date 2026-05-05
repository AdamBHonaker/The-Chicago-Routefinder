"""
Download and install MaxMind's GeoLite2-City database for local development.

Reads MAXMIND_LICENSE_KEY from backend/.env (free key from
https://www.maxmind.com/en/accounts/current/license-key) and fetches the
GeoLite2-City tar.gz from MaxMind's direct-download endpoint, then extracts
the .mmdb to backend/GeoLite2-City.mmdb where geography.py looks for it by
default. The same env var is consumed by the Dockerfile build step in
production — local dev and prod share one credential.

Usage:
    python backend/scripts/fetch_geolite.py
"""

import os
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH    = BACKEND_DIR / ".env"
TARGET_PATH = BACKEND_DIR / "GeoLite2-City.mmdb"

DOWNLOAD_URL_TEMPLATE = (
    "https://download.maxmind.com/app/geoip_download"
    "?edition_id=GeoLite2-City&license_key={key}&suffix=tar.gz"
)


def _read_env_var(name: str) -> "str | None":
    """Read a key=value line from backend/.env without pulling in python-dotenv."""
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            # Strip inline comments and surrounding quotes
            value = value.split("#", 1)[0].strip().strip('"').strip("'")
            return value or None
    return None


def main() -> int:
    license_key = os.getenv("MAXMIND_LICENSE_KEY") or _read_env_var("MAXMIND_LICENSE_KEY")
    if not license_key:
        print("[fetch_geolite] MAXMIND_LICENSE_KEY not set in env or backend/.env", file=sys.stderr)
        print("                Generate a free key at https://www.maxmind.com/en/accounts/current/license-key", file=sys.stderr)
        return 1

    url = DOWNLOAD_URL_TEMPLATE.format(key=urllib.parse.quote(license_key, safe=""))
    print(f"[fetch_geolite] downloading GeoLite2-City archive...")
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "geolite.tar.gz"
        try:
            urllib.request.urlretrieve(url, archive_path)
        except Exception as e:
            print(f"[fetch_geolite] download failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 2

        size_mb = archive_path.stat().st_size / (1024 * 1024)
        print(f"[fetch_geolite] downloaded {size_mb:.1f} MB; extracting...")

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                mmdb_member = next(
                    (m for m in tar.getmembers() if m.name.endswith("GeoLite2-City.mmdb")),
                    None,
                )
                if mmdb_member is None:
                    print("[fetch_geolite] archive did not contain GeoLite2-City.mmdb", file=sys.stderr)
                    return 3
                # Extract the single .mmdb file directly to the backend dir, flattening
                # the dated subdirectory MaxMind nests it under.
                src = tar.extractfile(mmdb_member)
                if src is None:
                    print("[fetch_geolite] failed to read .mmdb from archive", file=sys.stderr)
                    return 4
                TARGET_PATH.write_bytes(src.read())
        except tarfile.TarError as e:
            print(f"[fetch_geolite] extract failed: {e}", file=sys.stderr)
            return 5

    final_mb = TARGET_PATH.stat().st_size / (1024 * 1024)
    print(f"[fetch_geolite] installed → {TARGET_PATH} ({final_mb:.1f} MB)")
    print("[fetch_geolite] restart the backend to pick up the new DB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
