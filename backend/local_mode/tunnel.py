"""--share: a temporary public https:// link to the HireGuard running on this computer.

Providers, no account needed for either:
  1. Cloudflare quick tunnel, if `cloudflared` is installed (brew install cloudflared). Most reliable.
  2. localhost.run over ssh (ssh ships with macOS, Linux and Windows 10+).

The link lives only while run.py runs. If the provider drops it, a new one is opened and printed.
"""
import re
import shutil
import subprocess
import threading
from typing import Callable

CLOUDFLARE_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
ANY_URL = re.compile(r"https://([a-z0-9-]+(?:\.[a-z0-9-]+)+)")


def localhost_run_url(line: str) -> str | None:
    """localhost.run prints several links (docs, admin); the tunnel is the one on a generated subdomain."""
    for m in ANY_URL.finditer(line):
        host = m.group(1)
        if host in ("localhost.run", "twitter.com") or host.startswith(("admin.", "www.", "docs.")):
            continue
        if host.endswith((".lhr.life", ".lhr.rocks", ".localhost.run")):
            return m.group(0)
    return None


def providers(port: int) -> list[tuple[str, list[str], Callable[[str], str | None]]]:
    found = []
    if shutil.which("cloudflared"):
        found.append(("Cloudflare", ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                      lambda line: (m := CLOUDFLARE_URL.search(line)) and m.group(0)))
    if shutil.which("ssh"):
        found.append(("localhost.run", [
            "ssh", "-T", "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3", "-o", "ExitOnForwardFailure=yes", "-o", "BatchMode=yes",
            "-R", f"80:127.0.0.1:{port}", "nokey@localhost.run",
        ], localhost_run_url))
    return found


class Tunnel:
    def __init__(self, port: int, on_url: Callable[[str], None], say: Callable[[str], None] = print,
                 provider_list=None, url_timeout: float = 30, retry_delay: float = 5):
        self.port, self.on_url, self.say = port, on_url, say
        self.providers = provider_list if provider_list is not None else providers(port)
        self.url_timeout, self.retry_delay = url_timeout, retry_delay
        self.proc: subprocess.Popen | None = None
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> bool:
        if not self.providers:
            self.say("--share needs cloudflared (brew install cloudflared) or ssh. Neither was found.")
            return False
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stopped.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _run_once(self, name: str, cmd: list[str], find_url) -> bool:
        """Start the provider, report its link, and block until it exits. True if a link was seen."""
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        got_url = threading.Event()
        done = threading.Event()

        def watchdog():
            # No link within url_timeout: give up on this attempt so the loop can retry.
            if not got_url.wait(self.url_timeout) and not done.is_set() and self.proc.poll() is None:
                self.proc.terminate()

        threading.Thread(target=watchdog, daemon=True).start()
        for line in self.proc.stdout:
            if not got_url.is_set() and (url := find_url(line)):
                got_url.set()
                self.on_url(url)
        self.proc.wait()
        done.set()
        return got_url.is_set()

    def _loop(self) -> None:
        index, failures = 0, 0
        while not self.stopped.is_set():
            name, cmd, find_url = self.providers[index]
            self.say(f"Opening a public link with {name}...")
            seen = False
            try:
                seen = self._run_once(name, cmd, find_url)
            except OSError as exc:
                self.say(f"{name} could not start: {exc}")
            if self.stopped.is_set():
                break
            failures = 0 if seen else failures + 1
            if failures >= 2 and len(self.providers) > 1:
                index, failures = (index + 1) % len(self.providers), 0
            self.say(f"The public link closed. Reconnecting in {int(self.retry_delay)}s (a new link will be printed)...")
            self.stopped.wait(self.retry_delay)
