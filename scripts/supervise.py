"""Tiny process supervisor for the all-in-one Docker image.

Runs uvicorn (:8000) and the Next standalone server (:3000), forwards SIGTERM/SIGINT
to both, and exits as soon as either one dies so the container restarts cleanly.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

API_PORT = os.environ.get("NOVEL_OS_API_PORT", "8000")
WEB_PORT = os.environ.get("PORT", "3000")

CMDS = {
    "api": ([sys.executable, "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", API_PORT,
             "--proxy-headers"], "/app"),
    "web": (["node", "server.js"], "/app/web"),
}


def main() -> int:
    env = {**os.environ, "HOSTNAME": "0.0.0.0", "PORT": WEB_PORT}
    procs = {name: subprocess.Popen(cmd, cwd=cwd, env=env) for name, (cmd, cwd) in CMDS.items()}
    stopping = False

    def shutdown(*_):
        nonlocal stopping
        stopping = True
        for p in procs.values():
            if p.poll() is None:
                p.terminate()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    code = 0
    while not stopping:
        for name, p in procs.items():
            if p.poll() is not None:
                print(f"[supervise] {name} exited with {p.returncode}; stopping", flush=True)
                code = p.returncode or 1
                shutdown()
                break
        time.sleep(0.5)
    deadline = time.time() + 10
    for p in procs.values():
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
    return code


if __name__ == "__main__":
    sys.exit(main())
