#!/usr/bin/env python3
"""Run HireGuard on this computer. No AWS account and nothing to install, just Python 3.10+.

    python3 run.py                 # opens http://127.0.0.1:8080
    python3 run.py --share         # also prints a temporary public https:// link
    python3 run.py --port 9000     # another port
    python3 run.py --ai            # AI second opinion via Amazon Bedrock (needs boto3[crt] + AWS sign-in)

It runs the same detection engine and API code as the AWS version. Reports and the scam
library are saved in .local-data/hireguard.db. Press Ctrl+C to stop.
"""
import argparse
import os
import socket
import sys
import webbrowser
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"HireGuard needs Python 3.10 or newer (this is {sys.version.split()[0]}). "
             "On a Mac: brew install python, then run python3 run.py again.")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from local_mode.server import App, make_server  # noqa: E402
from local_mode.store import LocalDatabase  # noqa: E402
from local_mode.tunnel import Tunnel  # noqa: E402

SITES = [ROOT / "frontend" / "dist", ROOT / "frontend" / "prebuilt"]


def pick_site() -> Path:
    """The newest built website: a fresh `npm run build`, else the copy committed in frontend/prebuilt."""
    built = [d for d in SITES if (d / "index.html").is_file()]
    if not built:
        sys.exit("The website files are missing. Build them once with:\n"
                 "  cd frontend && npm install && npm run build && cd ..")
    return max(built, key=lambda d: (d / "index.html").stat().st_mtime)


def free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit(f"Ports {start}-{start + 19} are all busy. Try: python3 run.py --port 9000")


def ai_problem() -> str | None:
    """Why --ai can't run here, in plain words, or None if it can."""
    try:
        import boto3
    except ImportError:
        return 'boto3 is not installed. Run:  pip install "boto3[crt]"'
    try:
        creds = boto3.Session().get_credentials()
    except Exception as exc:  # noqa: BLE001 - e.g. `aws login` sessions need the crt extra
        if "crt" in str(exc):
            return 'your AWS sign-in (aws login) needs an extra package. Run:  pip install "boto3[crt]"'
        return f"AWS credentials could not be loaded ({type(exc).__name__})."
    if creds is None:
        return "no AWS sign-in found. Run:  aws login --profile hireguard"
    return None


def _has_profile(name: str) -> bool:
    config = Path(os.environ.get("AWS_CONFIG_FILE", Path.home() / ".aws" / "config"))
    try:
        return f"[profile {name}]" in config.read_text()
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HireGuard locally.")
    parser.add_argument("--share", action="store_true", help="print a temporary public https:// link (Cloudflare or localhost.run)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--ai", action="store_true", help="turn on the AI second opinion (Amazon Bedrock, your AWS credentials)")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    parser.add_argument("--db", default=str(ROOT / ".local-data" / "hireguard.db"), help="where to keep local data")
    parser.add_argument("--quiet", action="store_true", help="don't print each request")
    args = parser.parse_args()

    ai = args.ai
    if ai and not os.environ.get("AWS_PROFILE") and _has_profile("hireguard"):
        os.environ["AWS_PROFILE"] = "hireguard"  # same default as deploy.sh
    if ai and (problem := ai_problem()):
        print(f"--ai is off: {problem}")
        ai = False
    if ai:
        os.environ.setdefault("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-2"))

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = LocalDatabase(args.db)
    site = pick_site()
    port = free_port(args.port)
    server = make_server(App(site, db, ai=ai, quiet=args.quiet), "127.0.0.1", port)
    local_url = f"http://127.0.0.1:{port}"

    print()
    print(f"  HireGuard is running at {local_url}")
    print(f"  Website: {site.relative_to(ROOT)}   Data: {Path(args.db).resolve().relative_to(ROOT) if Path(args.db).resolve().is_relative_to(ROOT) else args.db}")
    print(f"  AI second opinion: {'on (Amazon Bedrock)' if ai else 'off (start with --ai to turn it on)'}")
    print("  Press Ctrl+C to stop.")
    print()

    tunnel = None
    if args.share:
        if ai:
            print("  Note: with --share and --ai, anyone with the link uses your AWS account for AI answers.")

        def announce(url: str) -> None:
            print()
            print(f"  Public link: {url}")
            print("  Anyone with this link can use your HireGuard while run.py is running.")
            if sys.platform == "darwin":
                print("  Tip: keep the Mac awake with  caffeinate -i python3 run.py --share")
            print()

        tunnel = Tunnel(port, announce)
        tunnel.start()

    if not args.no_browser:
        webbrowser.open(local_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping HireGuard...")
    finally:
        if tunnel:
            tunnel.stop()
        server.server_close()
        db.close()


if __name__ == "__main__":
    main()
