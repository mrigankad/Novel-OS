"""One-command start for Novel OS, on Windows, macOS and Linux.

    python -m novel_os                 # API on :8000 + studio on :3000, opens the browser
    python -m novel_os --api-port 8101 --web-port 3101 --no-browser
    python -m novel_os mcp [args...]   # passthrough to `python -m server.mcp_server`

Streams both logs with [api]/[web] prefixes and stops both on Ctrl+C.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import __version__

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
IS_WIN = os.name == "nt"
REQUIRED_MODULES = ("fastapi", "uvicorn", "sqlmodel", "alembic", "httpx", "multipart", "dotenv")
_print_lock = threading.Lock()


def say(msg: str) -> None:
    with _print_lock:
        print(f"[novel-os] {msg}", flush=True)


def fail(msg: str) -> "None":
    say(msg)
    sys.exit(1)


# ---- prerequisites --------------------------------------------------------------------

def check_python() -> None:
    if sys.version_info < (3, 10):
        fail(f"Python 3.10+ is required (this is {sys.version.split()[0]}).")
    missing = [m for m in REQUIRED_MODULES if importlib.util.find_spec(m) is None]
    if missing:
        fail("Missing Python packages: " + ", ".join(missing)
             + f"\n  Install them with:  {Path(sys.executable).name} -m pip install -r requirements.txt")


def find_npm() -> str:
    if shutil.which("node") is None:
        fail("Node.js was not found on PATH. Install Node 20 or newer from https://nodejs.org.")
    npm = shutil.which("npm.cmd" if IS_WIN else "npm") or shutil.which("npm")
    if npm is None:
        fail("npm was not found on PATH (it ships with Node.js).")
    return npm


def ensure_node_modules(npm: str, assume_yes: bool) -> None:
    if (WEB / "node_modules" / "next").is_dir():
        return
    say("The studio's dependencies are not installed (web/node_modules is missing).")
    if not assume_yes:
        if not sys.stdin.isatty():
            fail("Run `npm install` in web/, or pass --yes to let the launcher do it.")
        answer = input("[novel-os] Run `npm install` in web/ now? [Y/n] ").strip().lower()
        if answer not in ("", "y", "yes"):
            fail("Skipped. Run `npm install` in web/ and try again.")
    say("npm install (this takes a minute the first time)...")
    if subprocess.call([npm, "install"], cwd=WEB) != 0:
        fail("npm install failed; see the output above.")


# ---- processes ------------------------------------------------------------------------

def spawn(name: str, cmd: list[str], cwd: Path, env: dict) -> subprocess.Popen:
    kwargs: dict = {}
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, bufsize=1, text=True, encoding="utf-8",
                            errors="replace", **kwargs)

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            with _print_lock:
                print(f"[{name}] {line.rstrip()}", flush=True)

    threading.Thread(target=pump, daemon=True).start()
    return proc


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if IS_WIN:
            # npm/next spawn grandchildren; taskkill /T takes the whole tree down.
            subprocess.call(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        try:
            if not IS_WIN:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


def wait_http(url: str, timeout: float, procs: list[subprocess.Popen]) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if any(p.poll() is not None for p in procs):
            return False
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def run_dev(args: argparse.Namespace) -> int:
    check_python()
    npm = find_npm()
    ensure_node_modules(npm, args.yes)

    api_url = f"http://127.0.0.1:{args.api_port}"
    web_url = f"http://localhost:{args.web_port}"
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["NOVEL_OS_API_URL"] = api_url  # read by web/next.config.ts for the /api rewrite
    origins = env.get("NOVEL_OS_CORS_ORIGINS", "")
    if web_url not in origins:
        env["NOVEL_OS_CORS_ORIGINS"] = ",".join(o for o in (origins, web_url) if o)

    api_cmd = [sys.executable, "-m", "uvicorn", "server.main:app", "--host", args.host,
               "--port", str(args.api_port)]
    if args.reload:
        api_cmd += ["--reload", "--reload-dir", "server", "--reload-dir", "core"]
    # Call next directly (not `npm run dev`) so the port flag is ours, not the script's.
    web_cmd = [npm, "exec", "--", "next", "dev", "--turbopack", "-p", str(args.web_port)]

    def _interrupt(*_):
        raise KeyboardInterrupt

    # Treat terminal close / Ctrl+Break (Windows) and SIGTERM like Ctrl+C: stop both children.
    for sig in ("SIGTERM", "SIGBREAK", "SIGHUP"):
        if hasattr(signal, sig):
            try:
                signal.signal(getattr(signal, sig), _interrupt)
            except (ValueError, OSError):
                pass

    say(f"Novel OS {__version__}: API {api_url}, studio {web_url}  (Ctrl+C stops both)")
    procs: list[subprocess.Popen] = []
    try:
        procs.append(spawn("api", api_cmd, ROOT, env))
        procs.append(spawn("web", web_cmd, WEB, env))
        if wait_http(f"{api_url}/api/health", 90, procs) and wait_http(web_url, 180, procs):
            say(f"Ready: {web_url}")
            if not args.no_browser:
                webbrowser.open(web_url)
        else:
            say("One of the servers did not come up; see the log above.")
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        dead = next(p for p in procs if p.poll() is not None)
        say(f"{'api' if dead is procs[0] else 'web'} exited with code {dead.returncode}; stopping.")
        return dead.returncode or 1
    except KeyboardInterrupt:
        say("Stopping...")
        return 0
    finally:
        for p in procs:
            stop(p)


def run_mcp(extra: list[str]) -> int:
    return subprocess.call([sys.executable, "-m", "server.mcp_server", *extra], cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    # Next prints symbols a cp1252 Windows console can't encode; never let that kill the log pump.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["mcp"]:
        return run_mcp(argv[1:])
    p = argparse.ArgumentParser(prog="novel-os", description="Start the Novel OS API and studio together.",
                                epilog="Subcommand: `novel-os mcp [args]` runs the MCP server.")
    p.add_argument("--api-port", type=int, default=int(os.environ.get("NOVEL_OS_API_PORT", 8000)))
    p.add_argument("--web-port", type=int, default=int(os.environ.get("NOVEL_OS_WEB_PORT", 3000)))
    p.add_argument("--host", default="127.0.0.1", help="interface uvicorn binds to")
    p.add_argument("--no-browser", action="store_true", help="don't open the studio in a browser")
    p.add_argument("--reload", action="store_true", help="restart the API when server/ or core/ changes")
    p.add_argument("-y", "--yes", action="store_true", help="run `npm install` without asking if needed")
    p.add_argument("--version", action="version", version=__version__)
    args = p.parse_args(argv)
    os.chdir(ROOT)
    return run_dev(args)


if __name__ == "__main__":
    sys.exit(main())
