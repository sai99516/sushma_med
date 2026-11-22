"""
End-to-end browser tests for MediFind (Playwright + pytest).

The session fixture builds a fresh SQLite copy (migrate + seed_data) in a temp
directory and starts `runserver` on port 8001 with DEBUG=True against it.
db.sqlite3 is never touched.

Every browser context gets a Monitor that records console errors, uncaught
page errors and failed/4xx/5xx network requests. Any of these fails the test,
unless the test marks the status/URL as expected with `monitor.allow(...)`.
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
E2E_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = E2E_DIR / "screenshots"
PORT = int(os.environ.get("E2E_PORT", "8001"))
BASE_URL = f"http://127.0.0.1:{PORT}"

# Optional local copies of system libraries Chromium needs (no-sudo setups).
_extra_libs = Path.home() / ".local/pwlibs/root/usr/lib/x86_64-linux-gnu"
if _extra_libs.is_dir():
    os.environ["LD_LIBRARY_PATH"] = f"{_extra_libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"

# ---------------------------------------------------------------------------
# Database copy + Django setup for the test process (used for fixtures only).
# ---------------------------------------------------------------------------
_TMP = Path(tempfile.mkdtemp(prefix="medifind_e2e_"))
DB_PATH = _TMP / "e2e.sqlite3"
SERVER_ENV = {
    **os.environ,
    "DEBUG": "True",
    "DATABASE_URL": f"sqlite:///{DB_PATH}",
    "PYTHONUNBUFFERED": "1",
}
os.environ.update({k: SERVER_ENV[k] for k in ("DEBUG", "DATABASE_URL")})
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Playwright's sync API runs an event loop; the ORM is only used from plain test code.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
sys.path.insert(0, str(ROOT))

PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable


def _manage(*args):
    subprocess.run([PY, "manage.py", *args], cwd=ROOT, env=SERVER_ENV, check=True,
                   stdout=subprocess.DEVNULL)


def _wait_for_port(port, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"runserver did not start on port {port}")


@pytest.fixture(scope="session", autouse=True)
def live_server():
    _manage("migrate", "--noinput")
    _manage("seed_data")
    log = open(_TMP / "server.log", "w")
    proc = subprocess.Popen(
        [PY, "manage.py", "runserver", f"127.0.0.1:{PORT}", "--noreload"],
        cwd=ROOT, env=SERVER_ENV, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_port(PORT)
        import django
        django.setup()
        yield BASE_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


@pytest.fixture(scope="session")
def server_log_path():
    return _TMP / "server.log"


# ---------------------------------------------------------------------------
# Console / network monitor
# ---------------------------------------------------------------------------
# OpenStreetMap tiles are replaced with a blank PNG: no load on the public tile
# server, and the tests do not depend on it.
_BLANK_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


class Monitor:
    def __init__(self):
        self.console_errors = []
        self.page_errors = []
        self.bad_responses = []
        self.failed_requests = []
        self._allowed = []  # (status or None, url regex)
        self.contexts = []

    def allow(self, status=None, url=r".*"):
        """Marks a 4xx/5xx (or failed request) as expected for this test."""
        self._allowed.append((status, re.compile(url)))

    def _is_allowed(self, status, url):
        return any((s is None or s == status) and r.search(url) for s, r in self._allowed)

    def attach(self, context):
        self.contexts.append(context)
        context.route(re.compile(r"https://[abc]?\.?tile\.openstreetmap\.org/.*"),
                      lambda route: route.fulfill(status=200, content_type="image/png", body=_BLANK_PNG))

        def on_console(msg):
            if msg.type == "error":
                text = msg.text
                loc = msg.location or {}
                url = loc.get("url", "")
                # A "Failed to load resource" console line for a response we already
                # allowed (e.g. an expected 404/405/429) is not a separate error.
                m = re.search(r"status of (\d{3})", text)
                if m and self._is_allowed(int(m.group(1)), url):
                    return
                self.console_errors.append(f"{text} @ {url}")

        def on_weberror(err):
            self.page_errors.append(str(err.error))

        def on_response(resp):
            if resp.status >= 400 and not self._is_allowed(resp.status, resp.url):
                self.bad_responses.append(f"{resp.status} {resp.request.method} {resp.url}")

        def on_failed(req):
            failure = req.failure or ""
            if "ERR_ABORTED" in failure:  # navigation away mid-load, not an app error
                return
            if not self._is_allowed(None, req.url):
                self.failed_requests.append(f"{failure} {req.method} {req.url}")

        context.on("console", on_console)
        context.on("weberror", on_weberror)
        context.on("response", on_response)
        context.on("requestfailed", on_failed)

    def problems(self):
        out = []
        out += [f"console.error: {e}" for e in self.console_errors]
        out += [f"page error: {e}" for e in self.page_errors]
        out += [f"HTTP {e}" for e in self.bad_responses]
        out += [f"request failed: {e}" for e in self.failed_requests]
        return out


@pytest.fixture
def monitor():
    return Monitor()


@pytest.fixture
def browser_context_args(browser_context_args, base_url):
    return {**browser_context_args, "base_url": base_url, "viewport": {"width": 1280, "height": 900}}


@pytest.fixture
def context(browser, browser_context_args, monitor):
    ctx = browser.new_context(**browser_context_args)
    ctx.set_default_timeout(10000)
    monitor.attach(ctx)
    yield ctx
    ctx.close()


@pytest.fixture
def new_context(browser, browser_context_args, monitor):
    """Factory for extra contexts (a second user, a phone viewport, geolocation...)."""
    made = []

    def _make(**overrides):
        ctx = browser.new_context(**{**browser_context_args, **overrides})
        ctx.set_default_timeout(10000)
        monitor.attach(ctx)
        made.append(ctx)
        return ctx

    yield _make
    for c in made:
        c.close()


@pytest.fixture
def page(context):
    return context.new_page()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """After the test body: fail on any recorded console/network problem."""
    try:
        result = yield
    except BaseException:
        _screenshot(item, "FAILED")
        raise
    mon = item.funcargs.get("monitor")
    if mon is not None and mon.problems():
        _screenshot(item, "FAILED")
        raise AssertionError("Browser console/network problems:\n  " + "\n  ".join(mon.problems()))
    return result


def _screenshot(item, tag):
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.nodeid.split("::", 1)[-1])
    shots = []
    mon = item.funcargs.get("monitor")
    pages = [pg for ctx in (mon.contexts if mon else []) for pg in ctx.pages]
    for i, pg in enumerate(pages):
        if True:
            path = SCREENSHOT_DIR / f"{tag}_{safe}_{i}.png"
            try:
                pg.screenshot(path=str(path), full_page=True)
                shots.append(path)
            except Exception:
                pass
    item.user_properties.append(("screenshots", [str(p.relative_to(ROOT)) for p in shots]))


def pytest_sessionfinish(session, exitstatus):
    log = _TMP / "server.log"
    if log.exists():
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        shutil.copy(log, SCREENSHOT_DIR / "server.log")
    if os.environ.get("E2E_KEEP_DB") != "1":
        shutil.rmtree(_TMP, ignore_errors=True)
