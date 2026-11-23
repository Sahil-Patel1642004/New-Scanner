"""Fetch the deployed signing key and write config for the licensed desktop build."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def _api_base_url() -> str:
    configured = os.environ.get("SCANORA_LICENCE_API_URL") or os.environ.get("VITE_API_BASE_URL")
    if configured:
        return configured.strip().strip('"').strip("'").rstrip("/")

    env_file = Path(__file__).resolve().parents[1] / "admin-dashboard" / ".env.production"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "VITE_API_BASE_URL":
                return value.strip().strip('"').strip("'").rstrip("/")
    except OSError:
        pass
    return ""


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: prepare_licence_config.py <output-directory>", file=sys.stderr)
        return 2

    api_base_url = _api_base_url()
    if not api_base_url:
        print(
            "Set SCANORA_LICENCE_API_URL or VITE_API_BASE_URL to the deployed HTTPS API URL, ending in /api/v1.",
            file=sys.stderr,
        )
        return 2
    if not api_base_url.startswith("https://") or not api_base_url.endswith("/api/v1"):
        print("The configured API URL must use HTTPS and end with /api/v1.", file=sys.stderr)
        return 2

    request = Request(f"{api_base_url}/licence-config", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            config = json.loads(response.read().decode("utf-8"))
        public_key = config["public_key"]
        if len(base64.b64decode(public_key, validate=True)) != 32:
            raise ValueError("Unexpected signing key length")
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError, KeyError) as error:
        print(f"Could not retrieve the licence signing key from {api_base_url}: {error}", file=sys.stderr)
        print("Deploy the backend licence-config endpoint and retry the licensed build.", file=sys.stderr)
        return 1

    output_path = Path(sys.argv[1]) / "licence-config.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"api_base_url": api_base_url, "public_key": public_key}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote pinned API configuration to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
