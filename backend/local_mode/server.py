"""Local web server for run.py: the website plus the same API the AWS stack serves.

/api/<route> calls the real Lambda handlers (handlers/*.py) with an API Gateway-style event,
backed by SQLite instead of DynamoDB. Everything else is the built website with an SPA
fallback to index.html. Standard library only.
"""
import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from handlers import common, library_handler, report_handler, scan_handler, stats_handler

from .store import LocalDatabase

MAX_BODY = 64 * 1024
LOCAL_USER = {"sub": "local-user"}  # local mode has no sign-in; reports count as one local user
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class RateLimiter:
    """Token bucket per client and bucket name, mirroring the API Gateway throttles."""

    def __init__(self, limits: dict[str, tuple[float, int]]):
        self.limits, self.state, self.lock = limits, {}, threading.Lock()

    def allow(self, client: str, bucket: str) -> bool:
        rate, burst = self.limits[bucket]
        now = time.monotonic()
        with self.lock:
            tokens, last = self.state.get((client, bucket), (float(burst), now))
            tokens = min(burst, tokens + (now - last) * rate)
            if tokens < 1:
                self.state[(client, bucket)] = (tokens, now)
                return False
            self.state[(client, bucket)] = (tokens - 1, now)
            if len(self.state) > 10_000:  # forget idle clients
                self.state = {k: v for k, v in self.state.items() if now - v[1] < 60}
            return True


class App:
    """Everything the request handler needs, so tests can build one without sockets."""

    def __init__(self, site_dir: Path, db: LocalDatabase, ai: bool = False, quiet: bool = False):
        self.site_dir = site_dir.resolve()
        self.db, self.ai, self.quiet = db, ai, quiet
        self.limiter = RateLimiter({"api": (10, 20), "analyze": (2, 4)})
        common.use_tables(db.table)
        self.routes = {
            "POST /scan": scan_handler.handler,
            "POST /report": self._report,
            "GET /stats": stats_handler.handler,
            "POST /analyze": self._analyze,
            "GET /library": library_handler.handler,
            "GET /library/sites": library_handler.handler,
            "POST /lookup": library_handler.handler,
        }

    def _report(self, event, ctx):
        event["requestContext"] = {"authorizer": {"jwt": {"claims": LOCAL_USER}}}
        return report_handler.handler(event, ctx)

    def _analyze(self, event, ctx):
        if not self.ai:
            return common.response(503, {"error": "AI analysis is off in local mode. Start with --ai to use Amazon Bedrock."})
        from handlers import analyze_handler  # needs boto3 and AWS credentials

        return analyze_handler.handler(event, ctx)

    def config(self) -> dict:
        return {"apiUrl": "/api", "local": True, "ai": self.ai, "region": "local", "stage": "local"}


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "HireGuard-local"
    sys_version = ""
    app: App  # set by make_server

    # ---- plumbing ----
    def log_message(self, fmt, *args):  # noqa: A003 - BaseHTTPRequestHandler API
        if not self.app.quiet:
            print(f"  {self.command} {urlsplit(self.path).path} -> {args[1] if len(args) > 1 else ''}")

    def _client(self) -> str:
        # Behind --share the tunnel connects from localhost and passes the visitor's address on.
        forwarded = self.headers.get("Cf-Connecting-Ip") or (self.headers.get("X-Forwarded-For") or "").split(",")[0]
        return forwarded.strip() or self.client_address[0]

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode(), "application/json", {"Cache-Control": "no-store"})

    # ---- methods ----
    def do_GET(self):  # noqa: N802
        self._dispatch()

    def do_HEAD(self):  # noqa: N802
        self._dispatch()

    def do_POST(self):  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        url = urlsplit(self.path)
        try:
            if url.path.startswith("/api/"):
                self._api(url)
            elif url.path == "/config.json":
                self._json(200, self.app.config())
            elif self.command in ("GET", "HEAD"):
                self._static(url.path)
            else:
                self._json(405, {"error": "Method not allowed."})
        except Exception:  # noqa: BLE001 - never crash the server on one bad request
            self._json(500, {"error": "Something went wrong on our side."})

    def _api(self, url) -> None:
        route = f"{'GET' if self.command == 'HEAD' else self.command} {url.path[len('/api'):]}"
        fn = self.app.routes.get(route)
        if fn is None:
            self._json(404, {"error": "Not found."})
            return
        bucket = "analyze" if route == "POST /analyze" else "api"
        if not self.app.limiter.allow(self._client(), bucket):
            self._json(429, {"error": "Too many requests. Please wait a minute."})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json(413, {"error": "Request is too large."})
            return
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        query = {k: v[0] for k, v in parse_qs(url.query).items()} or None
        event = {"routeKey": route, "rawPath": url.path, "body": body, "isBase64Encoded": False,
                 "queryStringParameters": query, "requestContext": {}}
        resp = fn(event, None)
        self._send(resp["statusCode"], resp["body"].encode(), "application/json", resp.get("headers"))

    def _static(self, path: str) -> None:
        site = self.app.site_dir
        target = (site / unquote(path).lstrip("/")).resolve()
        if site not in target.parents and target != site:
            self._json(404, {"error": "Not found."})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            if "." in Path(path).name:  # a missing asset, not a page
                self._send(404, b"Not found", "text/plain")
                return
            target = site / "index.html"  # SPA routes like /result, /library
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        cache = "public, max-age=31536000, immutable" if "/assets/" in path else "no-cache"
        self._send(200, target.read_bytes(), ctype, {"Cache-Control": cache})


def make_server(app: App, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (RequestHandler,), {"app": app})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server
