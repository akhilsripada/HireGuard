"""Local mode (run.py): the SQLite store, the web server and the --share tunnel helper."""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from handlers import common, scan_handler
from local_mode.server import App, RateLimiter, make_server
from local_mode.store import LocalDatabase
from local_mode.tunnel import Tunnel, localhost_run_url

SCAM = (
    "Hi! Your resume was selected for a Remote Data Entry role at Amazon ($42/hr). Interviews are on Telegram. "
    "Once hired, buy your home-office kit ($450) from our approved vendor and you'll be reimbursed. Reply within 2 hours."
)


# ---------- store ----------

def test_store_keeps_data_on_disk_and_honours_ttl():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hg.db")
        db = LocalDatabase(path)
        db.table("REPORTS_TABLE").update_item(
            Key={"contactHash": "h1"}, UpdateExpression="ADD #c :one, #p :p SET #t = :t",
            ExpressionAttributeNames={"#c": "reportCount", "#p": "platforms", "#t": "contactType"},
            ExpressionAttributeValues={":one": 1, ":p": {"TEXT"}, ":t": "PHONE"}, ReturnValues="ALL_NEW")
        db.table("DOMAIN_CACHE_TABLE").put_item(Item={"domain": "old.example", "expiresAt": int(time.time()) - 1})
        db.close()

        again = LocalDatabase(path)
        item = again.table("REPORTS_TABLE").get_item(Key={"contactHash": "h1"})["Item"]
        assert item["reportCount"] == 1 and item["platforms"] == {"TEXT"}
        assert again.table("DOMAIN_CACHE_TABLE").get_item(Key={"domain": "old.example"}) == {}
        again.close()


def test_store_rejects_expressions_it_does_not_understand():
    db = LocalDatabase()
    try:
        db.table("REPORTS_TABLE").scan(FilterExpression="begins_with(#a, :b)",
                                       ExpressionAttributeNames={"#a": "x"}, ExpressionAttributeValues={":b": "y"})
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError")
    finally:
        db.close()


# ---------- server ----------

@contextmanager
def running(ai=False):
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        (site / "assets").mkdir(parents=True)
        (site / "index.html").write_text("<!doctype html><title>HireGuard</title>")
        (site / "assets" / "app.js").write_text("console.log('hi')")
        Path(tmp, "secret.txt").write_text("outside the site")
        db = LocalDatabase()
        saved_rdap = scan_handler.rdap_created_date
        scan_handler.rdap_created_date = lambda d, timeout: "2026-10-25"
        server = make_server(App(site, db, ai=ai, quiet=True), "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            server.server_close()
            scan_handler.rdap_created_date = saved_rdap
            common.use_tables(None)
            db.close()


def call(port, method, path, body=None, raw=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    conn.request(method, path, body=data, headers={"Content-Type": "application/json", **(headers or {})})
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    try:
        return resp.status, json.loads(payload), resp
    except ValueError:
        return resp.status, payload.decode(), resp


def test_server_serves_site_config_and_spa_routes():
    with running() as port:
        status, cfg, _ = call(port, "GET", "/config.json")
        assert status == 200 and cfg["local"] is True and cfg["apiUrl"] == "/api"
        status, page, resp = call(port, "GET", "/library")
        assert status == 200 and "HireGuard" in page and resp.getheader("X-Content-Type-Options") == "nosniff"
        status, _, resp = call(port, "GET", "/assets/app.js")
        assert status == 200 and "immutable" in resp.getheader("Cache-Control")
        assert call(port, "GET", "/assets/missing.js")[0] == 404
        assert call(port, "GET", "/..%2fsecret.txt")[0] == 404
        assert "outside" not in str(call(port, "GET", "/../secret.txt")[1])


def test_server_runs_the_real_api_end_to_end():
    with running() as port:
        status, out, _ = call(port, "POST", "/api/scan", {"message": SCAM, "senderEmail": "careers.amazon.hr@gmail.com"})
        assert status == 200 and out["label"] == "LIKELY_SCAM"
        flag_ids = [f["id"] for f in out["flags"]]

        report = {"contactType": "EMAIL", "contact": "careers.amazon.hr@gmail.com", "claimedCompany": "Amazon",
                  "share": {"message": SCAM, "label": out["label"], "score": out["score"], "flagIds": flag_ids}}
        status, rep, _ = call(port, "POST", "/api/report", report)
        assert status == 200 and rep == {"reportCount": 1, "sharedToLibrary": True}

        status, again, _ = call(port, "POST", "/api/scan", {"message": SCAM, "senderEmail": "careers.amazon.hr@gmail.com"})
        assert again["communityReports"] == 1

        status, lib, _ = call(port, "GET", "/api/library")
        assert status == 200 and len(lib["items"]) == 1 and "Telegram" in lib["items"][0]["text"]
        status, hit, _ = call(port, "POST", "/api/lookup", {"contactType": "EMAIL", "contact": "CAREERS.amazon.hr@gmail.com"})
        assert hit["reportCount"] == 1
        status, stats, _ = call(port, "GET", "/api/stats?range=week")
        assert status == 200 and stats["types"]
        assert call(port, "GET", "/api/library/sites")[1]["sites"] == []


def test_server_errors_and_limits():
    with running() as port:
        assert call(port, "POST", "/api/scan", {"message": "short"})[0] == 400
        assert call(port, "GET", "/api/nope")[0] == 404
        assert call(port, "DELETE", "/")[0] == 501  # http.server rejects unknown methods
        assert call(port, "POST", "/api/scan", raw=b"x" * (70 * 1024))[0] == 413
        status, out, _ = call(port, "POST", "/api/analyze", {"message": SCAM})
        assert status == 503 and "--ai" in out["error"]


def test_rate_limiter_mirrors_api_gateway_burst():
    limiter = RateLimiter({"analyze": (2, 4)})
    results = [limiter.allow("1.2.3.4", "analyze") for _ in range(6)]
    assert results == [True, True, True, True, False, False]
    assert limiter.allow("5.6.7.8", "analyze")  # other visitors are not affected


# ---------- --share ----------

def test_localhost_run_url_picks_the_tunnel_link():
    line = ("Open your tunnel at https://admin.localhost.run/ docs https://localhost.run/docs/ "
            "abc123.lhr.life tunneled with tls termination, https://abc123.lhr.life")
    assert localhost_run_url(line) == "https://abc123.lhr.life"
    assert localhost_run_url("welcome to https://localhost.run") is None


def test_tunnel_reports_link_and_stops():
    script = "import time; print('starting'); print('your url is: https://fake-name.trycloudflare.com', flush=True); time.sleep(30)"
    seen = []
    tunnel = Tunnel(8080, seen.append, say=lambda _msg: None,
                    provider_list=[("fake", [sys.executable, "-c", script], lambda line: "trycloudflare" in line and line.split()[-1])])
    assert tunnel.start()
    deadline = time.time() + 10
    while not seen and time.time() < deadline:
        time.sleep(0.05)
    tunnel.stop()
    assert seen == ["https://fake-name.trycloudflare.com"]


def test_tunnel_without_providers_explains_what_to_install():
    messages = []
    assert Tunnel(8080, print, say=messages.append, provider_list=[]).start() is False
    assert "cloudflared" in messages[0]
